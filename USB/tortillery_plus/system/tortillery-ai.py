#!/usr/bin/env python3
"""tortillery-ai.py (Tortillery+): vigila la impresión con la cámara y una IA de visión.

Cada `intervalo` segundos, mientras imprime, manda una foto de la webcam a la IA configurada en
~/printer_data/config/tortillery_ai.cfg (se edita desde Mainsail). Si la IA ve un fallo (espagueti, pieza
despegada, atasco/sin extruir) en `confirmaciones` fotos seguidas: PAUSE (o solo aviso), aviso por Telegram
con la foto (si está configurado con telegram_setup.sh) y línea en el historial de errores de la pantalla.
Sin proveedor o sin clave configurada no hace nada. Solo librería estándar (corre con el python3 del sistema).
"""
import base64
import configparser
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

PD = '/home/mks/printer_data'
CFG = PD + '/config/tortillery_ai.cfg'
TEMPLATE = '/usr/local/share/tortillery/tortillery_ai.cfg'
SECRETS = PD + '/moonraker.secrets'
ERRORS = PD + '/tortillery_errors.log'
MOON = 'http://127.0.0.1:7125'
SNAPSHOT = 'http://127.0.0.1/webcam/?action=snapshot'

PROMPT = (
    "You are monitoring a 3D printer (FDM) through a webcam snapshot taken during a print. "
    "The camera can be anywhere (above, at the side, close or far) and the photo may also show the room, the "
    "printer frame, cables, fans and the print head: first find the build plate and the part being printed, and "
    "judge only them. "
    "Decide if the print has clearly FAILED in one of these ways: 'espagueti' (tangled loose filament, "
    "spaghetti), 'despegada' (part or first layer lifting, curling up, dragged by the nozzle or detached / "
    "knocked over on the bed), 'atasco' (nozzle moving but no filament coming out, under-extruded gaps), "
    "'bola' (a blob or clump of plastic growing around the nozzle / heater block, which can wrap the hotend), "
    "'desplazada' (layer shift: the upper layers are offset sideways from the lower ones, a visible step on a wall "
    "that should be straight or smooth). "
    "A thin, flat, partially printed first layer is normal. A normal print is NOT a failure. "
    "Webcams near the bed are often close-up, partly blurry or overexposed by the printer light: still judge "
    "what you can see (plastic dragged or piled around the nozzle, the part moved or lifted from the bed); only "
    "an image where the print area cannot be seen at all is NOT a failure. Also give where you see the part being "
    "printed ('pieza') and, if there is a failure, the failure itself ('zona'), as [left, top, right, bottom] "
    "percentages (0-100) of the image, or null. Answer ONLY with JSON: "
    '{"fallo": true|false, "tipo": "espagueti|despegada|atasco|bola|desplazada|ninguno", "confianza": 0.0-1.0, '
    '"motivo": "short reason in Spanish (max 12 words)", "pieza": [l, t, r, b] | null, "zona": [l, t, r, b] | null}'
)
# con una foto anterior de la misma impresión: lo que cambia delata el fallo (vale para cualquier cámara)
PAIR = (" You get TWO photos of the same print from the same camera: the FIRST one was taken about %d minutes "
        "ago, the SECOND one is now. Judge the SECOND photo and use the first one to see what changed: a part that "
        "moved, disappeared, tipped over or lifted, or a tangle of filament that appeared or grew, is a strong sign "
        "of failure. The part simply getting taller, or the print head and bed being in another position, is "
        "normal.")
# al empezar cada impresión: dónde está la cama, para mandar solo esa zona ampliada (cualquier cámara)
BED_PROMPT = ("Find the 3D printer's build plate (the flat bed the part is printed on) in this webcam photo. "
              'Answer ONLY with JSON: {"cama": [left, top, right, bottom]} with its edges as percentages (0-100) '
              'of the image width and height, or {"cama": null} if you cannot see it.')
BED_MARGIN = 15   # % alrededor de la cama: en las X4 la cama se mueve adelante y atrás
OPENAI_BASES = {'openai': 'https://api.openai.com/v1', 'nvidia': 'https://integrate.api.nvidia.com/v1'}


def openai_base(s):
    """URL base de una API compatible con OpenAI. Acepta también la dirección completa que dan las webs de los
    proveedores (.../v1/chat/completions): antes se le añadía otra vez /chat/completions y contestaban 404."""
    default = OPENAI_BASES.get(s.get('proveedor'), '')
    base = re.sub(r'/(chat/completions|completions|models)$', '', (s.get('url') or default).strip().rstrip('/'))
    if default and base == default.rsplit('/', 1)[0]:   # solo el dominio (sin /v1): también daba 404
        return default
    return base
# Claude: modelos que admiten el reintento en el servidor si la petición se rechaza (fallbacks)
CLAUDE_FALLBACK = ('claude-opus-5-5', 'claude-opus-5', 'claude-sonnet-5-5', 'claude-fable-5-2', 'claude-fable-5-1')


def log(msg):
    print(time.strftime('%H:%M:%S'), msg, flush=True)


def http(url, body=None, headers=None, timeout=90, raw=False):
    data = body if raw or body is None else json.dumps(body).encode()
    h = {} if raw else {'Content-Type': 'application/json'}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_cfg():
    if not os.path.exists(CFG) and os.path.exists(TEMPLATE):
        shutil.copy(TEMPLATE, CFG)   # imagen recién grabada: la plantilla aparece en Mainsail para rellenarla
    c = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
    c.read(CFG, encoding='utf-8')
    s = dict(c['ia']) if c.has_section('ia') else {}
    s['proveedor'] = s.get('proveedor', '').strip().lower()
    return s


def ready(s):
    p = s['proveedor']
    if p not in ('anthropic', 'openai', 'nvidia', 'google', 'ollama', 'openai_compatible'):
        return False
    if p == 'ollama':
        return bool(s.get('url'))
    if p in ('openai', 'nvidia', 'openai_compatible') and not s.get('modelo'):
        return False
    return bool(s.get('api_key'))


def ask(s, jpg, ctx='', prev=None, prompt=None):
    """-> texto de la IA (None si la rechaza). ctx: minutos y capa, para que sepa en qué fase va.
    prev: (minutos, foto) anterior de la misma impresión para comparar. prompt: otro enunciado (buscar la cama)."""
    p, key, model = s['proveedor'], s.get('api_key', ''), s.get('modelo', '')
    if prompt is None:
        prompt = PROMPT + (PAIR % prev[0] if prev else '') + (' ' + ctx if ctx else '')
        if s.get('camara'):   # lo que el usuario describe de su cámara (qué se ve, qué es parte de la impresora)
            prompt += ' Notes about this camera from the owner: ' + s['camara']
    imgs = [base64.b64encode(x).decode() for x in ([prev[1]] if prev else []) + [jpg]]   # la anterior, primero
    if p == 'anthropic':
        model = model or 'claude-opus-5-5'
        body = {'model': model, 'max_tokens': 2000, 'output_config': {'effort': 'low'},
                'messages': [{'role': 'user', 'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b}}
                    for b in imgs] + [{'type': 'text', 'text': prompt}]}]}
        h = {'x-api-key': key, 'anthropic-version': '2026-10-21'}
        if model in CLAUDE_FALLBACK:
            body['fallbacks'] = 'default'
            h['anthropic-beta'] = 'server-side-fallback-2026-07-01'
        r = json.loads(http('https://api.anthropic.com/v1/messages', body, h))
        if r.get('stop_reason') == 'refusal':
            return None
        return ''.join(b.get('text', '') for b in r.get('content', []) if b.get('type') == 'text')
    if p == 'google':
        model = model or 'gemini-2.5-flash'
        body = {'contents': [{'parts': [{'text': prompt}] +
                              [{'inline_data': {'mime_type': 'image/jpeg', 'data': b}} for b in imgs]}]}
        r = json.loads(http('https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent'
                            % urllib.parse.quote(model), body, {'x-goog-api-key': key}))
        return ''.join(x.get('text', '') for x in r['candidates'][0]['content']['parts'])
    if p == 'ollama':
        body = {'model': model or 'qwen2.5vl', 'stream': False, 'format': 'json',
                'messages': [{'role': 'user', 'content': prompt, 'images': imgs}]}
        r = json.loads(http(s['url'].rstrip('/') + '/api/chat', body, timeout=300))
        return r['message']['content']
    # openai / nvidia / cualquier API compatible con OpenAI (LM Studio, etc.)
    base = openai_base(s)
    if p == 'nvidia' and '/' not in model:
        model = 'nvidia/' + model   # build.nvidia.com usa ids con dueño: nvidia/..., meta/..., qwen/...
    # 2000: los modelos que razonan (Nemotron super, o-series...) gastan tokens pensando antes de contestar
    body = {'model': model, 'max_tokens': 2000, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': prompt}] + [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b}} for b in imgs]}]}
    r = json.loads(http(base + '/chat/completions', body, {'Authorization': 'Bearer ' + key}))
    c = r['choices'][0]
    if not c['message'].get('content'):
        raise ValueError('respuesta vacia (finish_reason=%s)' % c.get('finish_reason'))
    return c['message']['content']


SINGLE = set()   # (proveedor, modelo) que no aceptan dos fotos en una consulta


def ask_print(s, jpg, ctx, prev):
    """Consulta de vigilancia: con la foto anterior si el modelo la acepta; si la rechaza (400/413/422), con una."""
    k = (s['proveedor'], s.get('modelo', ''))
    if prev and k not in SINGLE:
        try:
            return ask(s, jpg, ctx, prev)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 413, 422):
                raise
            SINGLE.add(k)
            log('IA: %s no acepta dos fotos (%s): sigue con una' % (k[1] or k[0], e.code))
    return ask(s, jpg, ctx)


def bed_box(text):
    """Respuesta a BED_PROMPT -> recorte 'izq,arriba,der,abajo' en % con margen; '' si no hay cama clara."""
    text = re.sub(r'<think>.*?(</think>|$)', '', text or '', flags=re.S)
    try:
        v = json.loads(re.findall(r'\{[^{}]*"cama"[^{}]*\}', text)[-1])['cama']
        l, t, r, b = (float(x) for x in v)
    except (IndexError, ValueError, TypeError, KeyError):
        return ''
    if max(l, t, r, b) <= 1:   # algunos modelos contestan en fracciones (0-1)
        l, t, r, b = l * 100, t * 100, r * 100, b * 100
    if not (0 <= l < r <= 100 and 0 <= t < b <= 100) or r - l < 10 or b - t < 10:
        return ''
    l, t, r, b = max(0, l - BED_MARGIN), max(0, t - BED_MARGIN), min(100, r + BED_MARGIN), min(100, b + BED_MARGIN)
    if (r - l) * (b - t) > 8500:   # la cama ya llena casi toda la foto: no merece recortar
        return ''
    return '%d,%d,%d,%d' % (l, t, r, b)


def find_bed(s, jpg):
    """recorte de tortillery_ai.cfg; vacío o 'auto': la IA busca la cama (una consulta por impresión); 'no': nada."""
    r = s.get('recorte', '').strip().lower()
    if r in ('no', 'off', '0'):
        return ''
    if r not in ('', 'auto'):
        return r
    box = bed_box(ask(s, jpg, prompt=BED_PROMPT))
    log('IA: cama en la foto: %s' % (box or 'no encontrada, uso la foto entera'))
    return box


def verdict(text):
    """Texto de la IA -> (fallo, confianza, tipo, motivo). Tolera texto alrededor del JSON y el razonamiento
    <think>...</think> de los modelos que piensan (Nemotron, Qwen, DeepSeek...): vale el último JSON con "fallo"."""
    text = re.sub(r'<think>.*?(</think>|$)', '', text or '', flags=re.S)
    found = re.findall(r'\{[^{}]*"fallo"[^{}]*\}', text)
    if not found:
        log('IA: respuesta sin JSON valido: %r' % text[:160])
        return False, 0.0, 'ninguno', ''
    try:
        v = json.loads(found[-1])
    except ValueError:
        log('IA: JSON no valido: %r' % found[-1][:160])
        return False, 0.0, 'ninguno', ''
    fallo = v.get('fallo') in (True, 'true', 'True', 1)
    try:
        conf = float(v.get('confianza', 0))
    except (TypeError, ValueError):
        conf = 0.0
    return fallo, conf, str(v.get('tipo', '')), str(v.get('motivo', ''))[:80]


def print_stats():
    r = json.loads(http(MOON + '/printer/objects/query?print_stats', timeout=10))
    return r['result']['status']['print_stats']


def gcode(script, timeout=30):
    http(MOON + '/printer/gcode/script?script=' + urllib.parse.quote(script), b'', timeout=timeout, raw=True)


def tg_creds():
    """(token, chat) del bot activado (url tgram://TOKEN/CHAT en moonraker.secrets) o None."""
    c = configparser.ConfigParser(interpolation=None)
    try:
        c.read(SECRETS, encoding='utf-8')
        token, chat = c['telegram']['url'].replace('tgram://', '').split('/')[:2]
    except (KeyError, ValueError, configparser.Error):
        return None
    return (token, chat) if token and chat else None


# botones del aviso de fallo (callback_data -> lo atiende bot_loop)
BUTTONS = {'inline_keyboard': [[{'text': '▶️ Reanudar', 'callback_data': 'resume'},
                                {'text': '⏹ Cancelar', 'callback_data': 'cancel'}],
                               [{'text': '📷 Otra foto', 'callback_data': 'foto'}]]}
# botones del aviso de sin filamento (la boquilla y la cama no se enfrían solas: Enfriar apaga la boquilla)
RUNOUT_BUTTONS = {'inline_keyboard': [[{'text': '🧊 Enfriar', 'callback_data': 'cool'}],
                                      [{'text': '▶️ Reanudar', 'callback_data': 'resume'},
                                       {'text': '⏹ Cancelar', 'callback_data': 'cancel'}]]}
# botones del aviso de corte de luz
PLR_BUTTONS = {'inline_keyboard': [[{'text': '▶️ Continuar', 'callback_data': 'plr_resume'},
                                    {'text': '🗑 Descartar', 'callback_data': 'plr_discard'}]]}


def telegram(text, jpg, buttons=False):
    """Texto (jpg None) o foto con texto al chat del bot; buttons True = Reanudar/Cancelar/Otra foto, o un teclado."""
    cred = tg_creds()
    if not cred:
        return
    token, chat = cred
    if jpg is None:
        body = {'chat_id': chat, 'text': text}
        if buttons:
            body['reply_markup'] = BUTTONS if buttons is True else buttons
        http('https://api.telegram.org/bot%s/sendMessage' % token, body, timeout=30)
        return
    tg_file(token, chat, 'sendPhoto', 'photo', 'foto.jpg', 'image/jpeg', jpg, text, buttons)


def tg_file(token, chat, method, field, fname, ctype, data, text, buttons=False, timeout=30):
    bound = uuid.uuid4().hex
    parts = []
    markup = BUTTONS if buttons is True else buttons
    fields = [('chat_id', chat), ('caption', text)] + ([('reply_markup', json.dumps(markup))] if markup else [])
    for name, value in fields:
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                      % (bound, name, value)).encode())
    parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"\r\n'
                  'Content-Type: %s\r\n\r\n' % (bound, field, fname, ctype)).encode() + data + b'\r\n')
    parts.append(('--%s--\r\n' % bound).encode())
    http('https://api.telegram.org/bot%s/%s' % (token, method), b''.join(parts),
         {'Content-Type': 'multipart/form-data; boundary=' + bound}, timeout=timeout, raw=True)


TG_CFG = PD + '/config/telegram.cfg'
SHARE = '/usr/local/share/tortillery/'
_tg_failed = set()


def telegram_sync():
    """config/telegram.cfg (Mainsail) -> moonraker.secrets + notifier de Moonraker. Solo actúa si cambia."""
    if not os.path.exists(TG_CFG) and os.path.exists(SHARE + 'telegram.cfg'):
        shutil.copy(SHARE + 'telegram.cfg', TG_CFG)
    c = configparser.ConfigParser(inline_comment_prefixes=('#', ';'), interpolation=None)
    c.read(TG_CFG, encoding='utf-8')
    token = c.get('telegram', 'token', fallback='').strip()
    chat = c.get('telegram', 'chat_id', fallback='').strip()
    sec = configparser.ConfigParser(interpolation=None)
    sec.read(SECRETS, encoding='utf-8')
    cur = sec.get('telegram', 'url', fallback='')
    if not token or (token, chat) in _tg_failed or \
            (cur.startswith('tgram://%s/' % token) and (not chat or cur.endswith('/' + chat))):
        return
    api = 'https://api.telegram.org/bot' + token
    try:
        if not chat:
            ids = [u[k]['chat']['id'] for u in json.loads(http(api + '/getUpdates', timeout=15)).get('result', [])
                   for k in ('message', 'channel_post', 'my_chat_member') if k in u]
            if not ids:
                return   # aún no le han escrito al bot: se reintenta al minuto
            chat = str(ids[-1])
        http(api + '/sendMessage', {'chat_id': chat, 'text': '✅ Tortillery+: avisos de impresión activados'},
             timeout=15)
    except urllib.error.HTTPError as e:
        _tg_failed.add((token, c.get('telegram', 'chat_id', fallback='').strip()))
        log('Telegram rechazó el token o el chat (%s): revisa telegram.cfg' % e.code)
        return
    if not sec.has_section('telegram'):
        sec.add_section('telegram')
    sec.set('telegram', 'url', 'tgram://%s/%s' % (token, chat))
    with open(SECRETS, 'w', encoding='utf-8') as f:
        sec.write(f)
    os.chmod(SECRETS, 0o600)
    if os.path.exists(SHARE + 'telegram.conf'):
        shutil.copy(SHARE + 'telegram.conf', PD + '/config/telegram.conf')
    with open(PD + '/config/moonraker.conf', 'r+', encoding='utf-8') as f:
        if '[include telegram.conf]' not in f.read():
            f.write('\n[include telegram.conf]\n')
    http(MOON + '/machine/services/restart?service=moonraker', b'', timeout=30, raw=True)
    log('Telegram activado (chat %s)' % chat)


def error_log(msg):
    try:
        with open(ERRORS, 'a', encoding='utf-8') as f:
            f.write('%s  %s\n' % (time.strftime('%d/%m %H:%M'), msg))
    except OSError:
        pass


def act(s, tipo, motivo, jpg):
    accion = s.get('accion', 'pausar').strip().lower()
    msg = 'IA: posible fallo (%s) - %s' % (tipo, motivo)
    log(msg + ' -> ' + accion)
    error_log(msg)
    try:
        gcode('RESPOND TYPE=error MSG="%s"' % msg.replace('"', "'"))   # consola de Mainsail
    except (urllib.error.URLError, OSError):
        pass   # sin [respond] en printer.cfg: no impide pausar
    try:
        if accion == 'pausar':
            AI_PAUSED[0] = time.time()   # events_loop no manda otro aviso de pausa
            gcode('PAUSE')
        elif accion == 'cancelar':
            gcode('CANCEL_PRINT')
    except (urllib.error.URLError, OSError) as e:
        log('no se pudo %s: %s' % (accion, e))
    try:
        telegram('%s\nAccion: %s' % (msg, accion), jpg, buttons=accion == 'pausar')
    except (urllib.error.URLError, OSError) as e:
        log('Telegram: %s' % e)


def warn(msg):
    """Aviso sin foto: la vigilancia no está funcionando (que no se crea vigilado sin estarlo)."""
    log(msg)
    error_log(msg)
    try:
        telegram(msg, None)
    except (urllib.error.URLError, OSError) as e:
        log('Telegram: %s' % e)


STATUS = PD + '/tortillery_ai.status'   # lo lee KlipperLCD para la página "Vigilancia IA"


def status(estado, detalle=''):
    try:
        with open(STATUS, 'w', encoding='utf-8') as f:
            json.dump({'estado': estado, 'detalle': detalle[:60], 'hora': time.strftime('%H:%M')}, f)
    except OSError:
        pass


def crop(jpg, spec, min_side=0):
    """recorte 'izq,arriba,der,abajo' en % de la foto -> solo esa zona (la cama), para que la IA la vea grande;
    min_side amplía el recorte si su lado corto es menor. Sin recorte, mal escrito o sin Pillow: la foto entera."""
    try:
        l, t, r, b = (float(v) for v in spec.split(','))
        assert 0 <= l < r <= 100 and 0 <= t < b <= 100
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(jpg))
        w, h = im.size
        out = io.BytesIO()
        im = im.crop((int(w * l / 100), int(h * t / 100), int(w * r / 100), int(h * b / 100))).convert('RGB')
        k = min_side / min(im.size)
        if k > 1:   # los fallos pequeños (capa desplazada) se ven mejor ampliados
            im = im.resize((int(im.size[0] * k), int(im.size[1] * k)), Image.LANCZOS)
        im.save(out, 'JPEG', quality=90)
        return out.getvalue()
    except Exception:
        return jpg


def thumb(jpg):
    """Foto -> miniatura gris 64x48 (bytes) para comparar; None sin Pillow o si la foto no se lee."""
    try:
        import io
        from PIL import Image
        return Image.open(io.BytesIO(jpg)).convert('L').resize((64, 48)).tobytes()
    except Exception:
        return None


DARK = 35   # gris medio (0-255) por debajo del cual la foto no sirve: de noche ningún modelo acierta


def dark(th):
    """¿Foto demasiado oscura? (miniatura de thumb; sin miniatura: no)"""
    return th is not None and sum(th) / len(th) < DARK


def lit_snapshot():
    """Foto con la luz del cabezal en blanco a tope y vuelta a la luz que tenía (solo si la foto sale oscura)."""
    try:
        gcode('_LUZ_FOTO')
        time.sleep(1.5)
        return http(SNAPSHOT, timeout=15)
    finally:
        try:
            gcode('_LUZ_LED_APLICAR')
        except (urllib.error.URLError, OSError):
            pass


PART_MARGIN, PART_MIN = 0.5, 40   # margen alrededor de la pieza (fracción de su tamaño) y lado mínimo (%)


def to_outer(zone, b):
    """Caja b (en % de la foto recortada a zone) -> % de la foto de fuera."""
    l, t, r, bt = zone or (0, 0, 100, 100)
    return (l + b[0] * (r - l) / 100, t + b[1] * (bt - t) / 100, l + b[2] * (r - l) / 100, t + b[3] * (bt - t) / 100)


def inside(a, z):
    return z is not None and z[0] <= a[0] and z[1] <= a[1] and a[2] <= z[2] and a[3] <= z[3]


def grow(b):
    """Caja de la pieza -> zona a recortar: con margen (más por arriba, la pieza crece) y un tamaño mínimo."""
    l, t, r, bt = b
    w, h = r - l, bt - t
    l, r, t, bt = l - w * PART_MARGIN, r + w * PART_MARGIN, t - h * PART_MARGIN * 2, bt + h * PART_MARGIN
    box = [l, t, r, bt]
    for a, c in ((0, 2), (1, 3)):   # lado mínimo, centrado
        if box[c] - box[a] < PART_MIN:
            m = (box[a] + box[c]) / 2
            box[a], box[c] = m - PART_MIN / 2, m + PART_MIN / 2
        if box[a] < 0:
            box[a], box[c] = 0, min(100, box[c] - box[a])
        if box[c] > 100:
            box[a], box[c] = max(0, box[a] - (box[c] - 100)), 100
    return tuple(round(v, 1) for v in box)


def next_zone(zone, cand, pieza):
    """Zona de recorte de la pieza (en % de la foto de la cama) tras una respuesta -> (zona, candidata).
    Se fija cuando dos respuestas seguidas ven la pieza en el mismo sitio (no fiarse de una sola) y solo crece."""
    if pieza is None:
        return zone, cand
    p = to_outer(zone, pieza)
    if zone is not None:
        return (zone if inside(p, zone) else grow((min(p[0], zone[0]), min(p[1], zone[1]),
                                                   max(p[2], zone[2]), max(p[3], zone[3])))), None
    cx, cy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2
    if cand and cand[0] <= cx <= cand[2] and cand[1] <= cy <= cand[3]:
        return grow((min(p[0], cand[0]), min(p[1], cand[1]), max(p[2], cand[2]), max(p[3], cand[3]))), None
    return None, p


def changed(a, b, limit=3.0):
    """¿Cambió la imagen? Diferencia media de gris (0-255). Sin miniaturas que comparar: sí."""
    if a is None or b is None or len(a) != len(b):
        return True
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a) >= limit


def boxes(text):
    """Respuesta de vigilancia -> {'pieza': (izq, arriba, der, abajo), 'zona': ...} en % (solo las válidas)."""
    text = re.sub(r'<think>.*?(</think>|$)', '', text or '', flags=re.S)
    found = re.findall(r'\{[^{}]*"fallo"[^{}]*\}', text)
    try:
        v = json.loads(found[-1])
    except (IndexError, ValueError):
        return {}
    out = {}
    for k in ('pieza', 'zona'):
        try:
            l, t, r, b = (float(x) for x in v.get(k) or ())
        except (TypeError, ValueError):
            continue
        if max(l, t, r, b) <= 1:   # algunos modelos contestan en fracciones (0-1)
            l, t, r, b = l * 100, t * 100, r * 100, b * 100
        if 0 <= l < r <= 100 and 0 <= t < b <= 100:
            out[k] = (l, t, r, b)
    return out


VISTA = PD + '/logs/ia_vista.jpg'   # Mainsail, cámara "IA" (moonraker.conf [webcam ia]): lo último que miró la IA


def vista(jpg, v, cajas, path=VISTA):
    """Foto que miró la IA con lo que ha visto: la pieza en verde, el fallo en rojo y el veredicto arriba."""
    fallo, conf, tipo, motivo = v
    try:
        import io
        import unicodedata
        from PIL import Image, ImageDraw, ImageFont
        im = Image.open(io.BytesIO(jpg)).convert('RGB')
        w, h = im.size
        d = ImageDraw.Draw(im)
        lw = max(2, w // 200)
        for k, (l, t, r, b) in cajas.items():
            d.rectangle((w * l / 100, h * t / 100, w * r / 100, h * b / 100), width=lw,
                        outline=(230, 30, 30) if k == 'zona' else (40, 200, 60))
        size = max(12, h // 22)
        try:
            font = ImageFont.truetype('DejaVuSans.ttf', size)   # Armbian (Pillow 9.4 no tiene letra escalable)
        except OSError:
            try:
                font = ImageFont.load_default(size=size)
            except TypeError:   # Pillow < 10.1: letra fija pequeña
                font = ImageFont.load_default()
        txt = time.strftime('%H:%M  ') + ('POSIBLE %s (%.0f%%): %s' % (tipo.upper(), conf * 100, motivo) if fallo
                                          else 'Todo bien' + (': ' + motivo if motivo else ''))
        txt = unicodedata.normalize('NFKD', txt).encode('ascii', 'ignore').decode()   # la letra básica no lleva tildes
        d.rectangle((0, 0, w, size + 2 * lw + 4), fill=(0, 0, 0))
        d.text((lw + 2, lw + 2), txt, fill=(255, 80, 80) if fallo else (255, 255, 255), font=font)
        tmp = path + '.tmp'
        im.save(tmp, 'JPEG', quality=85)
        os.replace(tmp, path)   # Mainsail nunca lee una imagen a medias
    except Exception as e:
        log('IA: vista no guardada: %s' % e)


def estado_text():
    q = 'print_stats&display_status&extruder&heater_bed'
    r = json.loads(http(MOON + '/printer/objects/query?' + q, timeout=10))['result']['status']
    ps, info = r['print_stats'], r['print_stats'].get('info') or {}
    lines = ['Estado: %s' % ps.get('state'),
             'Boquilla %.0f/%.0f °C, cama %.0f/%.0f °C' % (r['extruder']['temperature'], r['extruder']['target'],
                                                         r['heater_bed']['temperature'], r['heater_bed']['target'])]
    if ps.get('state') in ('printing', 'paused'):
        lines.insert(1, '%s: %d %%, %d min' % (ps.get('filename'), r['display_status'].get('progress', 0) * 100,
                                             ps.get('print_duration', 0) // 60))
        if info.get('current_layer'):
            lines.insert(2, 'Capa %s de %s' % (info['current_layer'], info.get('total_layer') or '?'))
    return '\n'.join(lines)


# menú "/" del bot: bot_loop lo registra en Telegram (setMyCommands) al arrancar y si cambia el token
COMMANDS = [('foto', 'Foto de la cámara y estado'), ('estado', 'Cómo va la impresión'),
            ('reanudar', 'Reanudar la impresión en pausa'), ('cancelar', 'Cancelar la impresión'),
            ('enfriar', 'Apagar la boquilla (en pausa, sin filamento)'),
            ('continuar', 'Seguir la impresión tras un corte de luz'),
            ('descartar', 'Descartar la impresión cortada por la luz'), ('ayuda', 'Lista de órdenes')]


def set_commands(token):
    http('https://api.telegram.org/bot%s/setMyCommands' % token,
         {'commands': [{'command': c, 'description': d} for c, d in COMMANDS]}, timeout=15)


def handle_update(u, chat):
    """Una actualización de Telegram. Solo obedece al chat configurado."""
    cb = u.get('callback_query')
    msg = u.get('message') or {}
    who = str((cb or {}).get('message', {}).get('chat', {}).get('id') if cb else msg.get('chat', {}).get('id'))
    if who != chat:
        return
    if cb:
        cred = tg_creds()
        http('https://api.telegram.org/bot%s/answerCallbackQuery' % cred[0], {'callback_query_id': cb['id']},
             timeout=15)
        cmd = {'resume': '/reanudar', 'cancel': '/cancelar', 'foto': '/foto', 'plr_resume': '/continuar',
               'plr_discard': '/descartar', 'cool': '/enfriar'}.get(cb.get('data'), '')
    else:
        cmd = (msg.get('text') or '').split('@')[0].strip().lower()
    if cmd == '/foto':
        telegram(estado_text(), http(SNAPSHOT, timeout=15))
    elif cmd == '/estado':
        telegram(estado_text(), None)
    elif cmd == '/reanudar':
        if print_stats().get('state') == 'paused':
            try:
                gcode('RESUME')
                telegram('▶️ Reanudando', None)
            except urllib.error.HTTPError:   # RESUME se niega sin filamento en el sensor
                telegram('🧵 Sin filamento: carga el nuevo en la pantalla (Aceptar) y luego reanuda', None)
        else:
            telegram('No está en pausa', None)
    elif cmd == '/enfriar':
        if print_stats().get('state') == 'paused':
            gcode('_ENFRIAR')
            telegram('🧊 Boquilla apagada; la cama sigue caliente. Al reanudar se vuelve a calentar.', None)
        else:
            telegram('No está en pausa', None)
    elif cmd == '/cancelar':
        if print_stats().get('state') in ('printing', 'paused'):
            gcode('CANCEL_PRINT')
            telegram('⏹ Impresión cancelada', None)
        else:
            telegram('No hay ninguna impresión', None)
    elif cmd == '/continuar':
        plr, ps = plr_status()
        if not plr.get('pending'):
            telegram('No hay ninguna impresión interrumpida', None)
        elif ps.get('state') in ('printing', 'paused') or PLR_BUSY.is_set():
            telegram('Ya está imprimiendo', None)
        elif not plr.get('file_exists'):
            telegram('No encuentro %s: mete el USB con el archivo y vuelve a pulsar Continuar' % plr.get('file'), None)
        else:
            PLR_BUSY.set()
            telegram('▶️ Continuando %s: calienta, vuelve a su sitio y sigue (unos minutos)' % plr.get('file'), None)
            threading.Thread(target=plr_resume, daemon=True).start()
    elif cmd == '/descartar':
        plr, ps = plr_status()
        if plr.get('pending') and ps.get('state') not in ('printing', 'paused') and not PLR_BUSY.is_set():
            gcode('PLR_CLEAR')
            telegram('🗑 Impresión interrumpida descartada', None)
        else:
            telegram('No hay nada que descartar', None)
    elif cmd in ('/start', '/ayuda', '/help'):
        telegram('Órdenes:' + ''.join('\n/%s  %s' % c for c in COMMANDS), None)


# ---- corte de luz: la impresora no puede avisar sin corriente; avisa al volver (plr_state.json pendiente)
PLR_FILE = PD + '/plr_state.json'      # lo escribe plr.py cada 5 s mientras imprime
PLR_SENT = PD + '/.plr_avisado'        # el corte ya avisado (para no repetirlo si se reinicia el servicio)
PLR_BUSY = threading.Event()           # RESUME_INTERRUPTED en marcha desde Telegram


def plr_status():
    r = json.loads(http(MOON + '/printer/objects/query?plr&print_stats', timeout=10))['result']['status']
    return r.get('plr') or {}, r['print_stats']


def plr_resume():
    """RESUME_INTERRUPTED tarda minutos (calentar): la respuesta de Moonraker llega al acabar o con el error."""
    try:
        gcode('RESUME_INTERRUPTED', timeout=1800)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read())['error']['message']
        except (ValueError, KeyError, TypeError):
            msg = str(e)
        telegram('⚠️ No se pudo continuar: %s' % msg, None)
    except (urllib.error.URLError, OSError) as e:
        log('PLR continuar: %s' % e)
    finally:
        PLR_BUSY.clear()


def boot_time():
    with open('/proc/uptime') as f:
        return time.time() - float(f.read().split()[0])


def hhmm(t, ref):
    lt = time.localtime(t)
    return time.strftime('%H:%M' if lt[:3] == time.localtime(ref)[:3] else '%d/%m %H:%M', lt)


def plr_text(plr, cut, back, size=0):
    """Texto del aviso. cut: último guardado (≈ el corte), back: arranque."""
    mins = max(0, int((back - cut) // 60))
    lines = ['⚡ Corte de luz durante la impresión de %s' % plr.get('file', '?'),
             'Se apagó hacia las %s y volvió a las %s (%s sin corriente).' % (
                 hhmm(cut, back), hhmm(back, back), '%d h %d min' % (mins // 60, mins % 60) if mins >= 60
                 else '%d min' % mins)]
    pos = 'Iba por Z %.2f mm' % plr.get('z', 0)
    if size:
        pos += ' (%d %% del archivo)' % (100 * plr.get('position', 0) // size)
    lines.append(pos + '.')
    if not plr.get('file_exists', True):
        lines.append('No encuentro el archivo: mete el USB antes de continuar.')
    lines.append('Comprueba que la pieza sigue pegada. ¿Continuar? (también desde la pantalla)')
    return '\n'.join(lines)


def power_loss_check(tries=60):
    """Al arrancar: si hay una impresión interrumpida, un aviso con Continuar/Descartar (una vez por corte)."""
    for _ in range(tries):   # Klipper tarda en estar listo tras el arranque
        try:
            plr, ps = plr_status()
            break
        except (urllib.error.URLError, OSError, KeyError, ValueError):
            time.sleep(10)
    else:
        return
    if not plr.get('pending') or ps.get('state') in ('printing', 'paused') or not tg_creds():
        return
    try:
        cut = os.path.getmtime(PLR_FILE)
    except OSError:
        cut = time.time()
    key = '%s %d' % (plr.get('file'), cut)
    try:
        with open(PLR_SENT) as f:
            if f.read().strip() == key:
                return
    except OSError:
        pass
    back = boot_time()
    try:
        meta = json.loads(http(MOON + '/server/files/metadata?filename=' + urllib.parse.quote(plr.get('file', '')),
                               timeout=10))['result']
        size = meta.get('size', 0)
    except (urllib.error.URLError, OSError, KeyError, ValueError):
        size = 0
    telegram(plr_text(plr, cut, back, size), None, PLR_BUTTONS)
    with open(PLR_SENT, 'w') as f:
        f.write(key)


def bot_loop():
    """Escucha a Telegram (long polling): botones del aviso y órdenes /foto /estado /reanudar /cancelar."""
    offset, menu = 0, None
    while True:
        cred = tg_creds()
        if not cred:
            time.sleep(60)
            continue
        if menu != cred[0]:
            try:
                set_commands(cred[0])
                menu = cred[0]
            except (urllib.error.URLError, OSError) as e:   # sin internet: se reintenta en la siguiente vuelta
                log('Telegram menú de órdenes: %s' % e)
        try:
            r = json.loads(http('https://api.telegram.org/bot%s/getUpdates?timeout=50&offset=%d' % (cred[0], offset),
                                timeout=65))
            for u in r.get('result', []):
                offset = u['update_id'] + 1
                try:
                    handle_update(u, cred[1])
                except (urllib.error.URLError, OSError, KeyError, ValueError, TypeError) as e:
                    log('Telegram orden: %s' % e)
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 409:
                # 409: otro programa lee este mismo bot (otra impresora, un webhook de n8n...): los botones y las
                # órdenes no llegan aquí; los avisos sí se envían
                desc = e.read().decode('utf-8', 'replace')
                e = '409, otro programa usa este bot (%s). Usa un bot propio para esta impresora' % (
                    'tiene un webhook: getWebhookInfo' if 'webhook' in desc else 'otro getUpdates a la vez')
            log('Telegram escucha: %s' % e)
            time.sleep(30)


AI_PAUSED = [0.0]
TIMELAPSE = PD + '/timelapse'
MAINT_FILE = PD + '/tortillery_maintenance'   # el mismo contador que la pantalla y MANTENIMIENTO_HECHO
MARCAS = PD + '/config/ia_marcas.json'   # lo guarda la web http://tortilleryplus.local/ia


def solve(a, b):
    """Sistema lineal pequeño (Gauss con pivote) -> solución; None si no tiene una sola."""
    n = len(a)
    m = [list(r) + [v] for r, v in zip(a, b)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-9:
            return None
        m[c], m[p] = m[p], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[r][n] / m[r][r] for r in range(n)]


def homography(src, dst):
    """4 puntos src -> 4 puntos dst: los 8 coeficientes de la homografía (h33 = 1); None si están alineados."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    return solve(a, b)


def project(h, x, y):
    w = h[6] * x + h[7] * y + 1
    return (h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w


def marks_model(cal):
    """Marcas de la web (una foto por posición: boquilla y las 4 esquinas de la cama, en % de la foto) -> cómo se
    mueve en la foto cada punto con cada eje: [u, v] = base + jx*X + jy*Y + jz*Z (mínimos cuadrados). Vale con la
    cámara en el marco, en la cama o en el cabezal: lo que se mueve con cada eje lo dicen las propias fotos."""
    rows = [[1.0] + [float(v) for v in f['pos'][:3]] for f in cal['fotos']]
    ata = [[sum(r[i] * r[j] for r in rows) for j in range(4)] for i in range(4)]

    def fit(pts):
        out = [solve(ata, [sum(r[i] * float(p[k]) for r, p in zip(rows, pts)) for i in range(4)]) for k in (0, 1)]
        if None in out:
            raise ValueError('posiciones de las fotos sin un eje distinto cada una')
        return out
    return fit([f['boquilla'] for f in cal['fotos']]), [fit([f['cama'][i] for f in cal['fotos']]) for i in range(4)]


def at(c, pos):
    return tuple(c[k][0] + sum(c[k][i + 1] * pos[i] for i in range(3)) for k in (0, 1))


def marked_zone(cal, pos, polys):
    """Zona a recortar (en % de la foto) con la impresora en pos (X, Y, Z): las piezas (polígonos de las etiquetas
    de objetos, en mm) desde la cama hasta la altura actual, con margen; sin etiquetas, la cama entera."""
    noz, corners = marks_model(cal)
    w, d = (float(v) for v in cal['cama_mm'])
    bed = [(0, 0), (w, 0), (w, d), (0, d)]   # esquinas: delante izq., delante der., detrás der., detrás izq.
    up = [noz[k][3] - sum(c[k][3] for c in corners) / 4 for k in (0, 1)]   # % de foto por mm sobre la cama
    # origen: en la primera foto la boquilla está casi tocando la cama, justo encima de su X, Y
    f0 = cal['fotos'][0]['pos']
    inv = homography([at(c, f0) for c in corners], bed)
    h = homography(bed, [at(c, pos) for c in corners])
    if not (inv and h):
        return None
    n0 = at(noz, f0)
    bx, by = project(inv, n0[0] - up[0] * f0[2], n0[1] - up[1] * f0[2])
    ox, oy = bx - f0[0], by - f0[1]
    pts = [p for poly in polys for p in poly] or [(x - ox, y - oy) for x, y in bed]
    img = []
    for x, y in pts:
        u, v = project(h, x + ox, y + oy)
        img += [(u, v), (u + up[0] * pos[2], v + up[1] * pos[2])]   # base y altura ya impresa
    box = (min(p[0] for p in img), min(p[1] for p in img), max(p[0] for p in img), max(p[1] for p in img))
    if polys:
        return grow(box)
    l, t, r, b = (max(0, box[0] - 3), max(0, box[1] - 3), min(100, box[2] + 3), min(100, box[3] + 3))
    return (l, t, r, b) if r - l > 5 and b - t > 5 else None


def load_marks():
    try:
        with open(MARCAS) as f:
            cal = json.load(f)
        marks_model(cal)
        return cal
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


def toolhead_objects():
    """-> (posición X, Y, Z de la boquilla, polígonos de las etiquetas de objetos)."""
    r = json.loads(http(MOON + '/printer/objects/query?toolhead=position&exclude_object=objects', timeout=10))
    st = r['result']['status']
    return st['toolhead']['position'][:3], [o['polygon'] for o in st['exclude_object'].get('objects') or []
                                            if o.get('polygon')]


MAINT_EVERY = 200
VIDEO_MAX = 50 * 1024 * 1024   # límite de los bots de Telegram


def snapshot():
    try:
        return http(SNAPSHOT, timeout=15)
    except (urllib.error.URLError, OSError):
        return None   # sin cámara: el aviso va sin foto


def maintenance_text():
    try:
        with open(MAINT_FILE) as f:
            base = float(f.read().strip() or 0)
    except (OSError, ValueError):
        return None   # la pantalla crea el contador al arrancar
    t = json.loads(http(MOON + '/server/history/totals', timeout=10))['result']['job_totals']['total_print_time']
    h = (t - base) / 3600
    if h >= MAINT_EVERY:
        return ('🔧 Mantenimiento: %d h de impresión desde el último (engrasar husillos, revisar correas). '
                'Al terminar, MANTENIMIENTO_HECHO en Mainsail o en la pantalla.' % h)


def send_timelapse(t0, wait=900):
    """El vídeo del timelapse se renderiza al acabar: espera a que aparezca un .mp4 nuevo y no crezca."""
    if not os.path.isdir(TIMELAPSE):
        return
    size = -1
    for _ in range(wait // 20):
        time.sleep(20)
        new = [os.path.join(TIMELAPSE, f) for f in os.listdir(TIMELAPSE) if f.endswith('.mp4')]
        new = [f for f in new if os.path.getmtime(f) >= t0 - 60]
        if not new:
            continue
        f = max(new, key=os.path.getmtime)
        if os.path.getsize(f) != size:
            size = os.path.getsize(f)
            continue
        cred = tg_creds()
        if not cred:
            return
        if size > VIDEO_MAX:
            telegram('🎬 Timelapse listo (%d MB, demasiado grande para Telegram): en Mainsail > Timelapse'
                     % (size >> 20), None)
        else:
            with open(f, 'rb') as v:
                tg_file(cred[0], cred[1], 'sendVideo', 'video', os.path.basename(f), 'video/mp4', v.read(),
                        '🎬 Timelapse', timeout=300)
        return


def runout():
    """La pausa es porque el sensor se quedó sin filamento (_SIN_FILAMENTO en artillery_X4_*.cfg)."""
    try:
        r = json.loads(http(MOON + '/printer/objects/query?gcode_macro%20_SIN_FILAMENTO', timeout=10))
        return bool(r['result']['status']['gcode_macro _SIN_FILAMENTO'].get('activo'))
    except (urllib.error.URLError, OSError, KeyError, ValueError):
        return False


def on_event(prev, state, st):
    name = st.get('filename', '')
    if state == 'paused':
        time.sleep(6)   # el sensor pausa y 5 s después (pause_delay) marca _SIN_FILAMENTO
    if state == 'paused' and runout():
        telegram('🧵 Sin filamento: %s. En pausa con la boquilla y la cama calientes (no se enfrían solas). '
                 'Carga el nuevo en la pantalla: Aceptar aparta el cabezal.' % name, snapshot(), buttons=RUNOUT_BUTTONS)
    elif state == 'paused' and time.time() - AI_PAUSED[0] > 120:   # pausa de la IA: ya avisó act()
        telegram('⏸️ En pausa: %s' % name, snapshot(), buttons=True)
    elif state == 'complete':
        d = int(st.get('print_duration', 0))
        telegram('✅ Terminada: %s (%d h %d min)' % (name, d // 3600, d % 3600 // 60), snapshot())
        threading.Thread(target=send_timelapse, args=(time.time(),), daemon=True).start()
        m = maintenance_text()
        if m:
            telegram(m, None)


def events_loop():
    """Avisos que no da Moonraker: corte de luz, pausa con foto y botones, fin con foto, timelapse, mantenimiento."""
    try:
        power_loss_check()
    except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
        log('Telegram corte de luz: %s' % e)
    prev = None
    while True:
        time.sleep(20)
        try:
            st = print_stats() if tg_creds() else {}
            state = st.get('state')
            if prev and state and state != prev:
                on_event(prev, state, st)
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            log('Telegram aviso: %s' % e)
            continue
        prev = state


def main():
    strikes = fails = skipped = 0
    last = None   # miniatura de la última foto que miró la IA
    box = None    # recorte de la cama en esta impresión (None: aún sin buscar)
    zone = cand = None   # recorte de la pieza dentro de la cama (next_zone) y su candidata
    dark_warned = False
    hist = []     # (hora, foto recortada) de esta impresión, para comparar con una de hace unos minutos
    while True:
        try:
            telegram_sync()
        except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
            log('Telegram: %s' % e)
        s = load_cfg()
        if not ready(s):
            status('apagada', 'configura tortillery_ai.cfg')
            time.sleep(60)
            continue
        interval = max(30, int(s.get('intervalo', 120)))
        try:
            st = print_stats()
        except (urllib.error.URLError, OSError, KeyError, ValueError):
            time.sleep(30)
            continue
        dur = st.get('print_duration', 0)
        if st.get('state') != 'printing' or dur < int(s.get('espera_inicio', 60)):
            strikes = fails = skipped = 0
            last = box = zone = cand = None
            hist = []
            dark_warned = False
            status('esperando', 'vigila al imprimir')
            time.sleep(15)
            continue
        if dur < 600:
            interval = min(interval, 60)   # primeros 10 min: la primera capa es cuando más se despega
        info = st.get('info') or {}
        ctx = 'The print has been running %d minutes' % (dur // 60)
        if info.get('current_layer'):
            ctx += ', layer %s of %s' % (info['current_layer'], info.get('total_layer') or '?')
            if info['current_layer'] == 2:
                ctx += '. The first layer has just finished: check it carefully for lifted or curled corners, '                        'lines not stuck to the bed or dragged filament'
        try:
            jpg = http(SNAPSHOT, timeout=15)
            th = thumb(jpg)
            if dark(th):   # de noche: luz del cabezal a tope para la foto; si aún no se ve, no se paga la consulta
                jpg = lit_snapshot()
                th = thumb(jpg)
                if dark(th):
                    log('foto demasiado oscura: no se consulta a la IA')
                    status('vigilando', 'foto demasiado oscura')
                    if not dark_warned:
                        warn('IA: la foto de la cámara está demasiado oscura para vigilar: pon luz sobre la cama')
                        dark_warned = True
                    time.sleep(interval)
                    continue
            # misma imagen que la última revisada: no se paga otra consulta (pero como mucho 2 veces seguidas)
            if not strikes and skipped < 2 and not changed(th, last):
                skipped += 1
                time.sleep(interval)
                continue
            skipped = 0
            auto = s.get('recorte', '').strip().lower() in ('', 'auto')
            cal = load_marks() if auto else None
            mz = marked_zone(cal, *toolhead_objects()) if cal else None
            if mz:   # marcas de la web /ia: la pieza en la foto, esté donde esté la cama, sin preguntar a la IA
                seen = crop(jpg, ','.join(str(v) for v in mz), 640)
            else:
                if box is None:
                    box = find_bed(s, jpg)
                seen = crop(jpg, box)   # lo que mira la IA (Telegram recibe la foto entera)
                if zone:   # y dentro de la cama, solo la pieza ampliada: los fallos pequeños se pierden en la foto
                    seen = crop(seen, ','.join(str(v) for v in zone), 640)
            now = time.time()
            old = [(now - h, j) for h, j in hist if now - h >= 180]   # la más reciente de hace 3 min o más
            prev = (int(old[-1][0] // 60), old[-1][1]) if old else None
            text = ask_print(s, seen, ctx + '.', prev)
            fallo, conf, tipo, motivo = verdict(text)
            log('IA (%s): fallo=%s %s %.2f %s' % (ctx, fallo, tipo, conf, motivo))   # cada foto, para comprobarla
            vista(seen, (fallo, conf, tipo, motivo), boxes(text))
            if fallo and conf >= float(s.get('umbral', 0.7)) and s.get('modelo_confirmar'):
                f2, c2, t2, m2 = verdict(ask_print(dict(s, modelo=s['modelo_confirmar']), seen, ctx + '.', prev))
                if not (f2 and c2 >= float(s.get('umbral', 0.7))):
                    log('descartado por %s: %s' % (s['modelo_confirmar'], motivo))
                    fallo = False
            last = th
            hist = [(h, j) for h, j in hist if now - h < 900] + [(now, seen)]   # 15 min como mucho
            if auto and not mz:
                z, cand = next_zone(zone, cand, boxes(text).get('pieza'))
                if z != zone:
                    log('IA: recorte de la pieza: %s' % (z,))
                    zone, hist = z, []   # otro recorte: las fotos anteriores ya no se pueden comparar
            fails = 0
            status('vigilando', ('posible %s' % tipo) if fallo else 'todo bien')
        except (urllib.error.URLError, OSError, KeyError, IndexError, ValueError) as e:
            if isinstance(e, urllib.error.HTTPError):
                e = '%s %s' % (e, e.read()[:300])
            log('sin respuesta (%s)' % e)   # cámara o IA caídas: nunca se pausa por esto, pero se avisa
            fails += 1
            status('sin respuesta', str(e)[:60])
            if fails == 3:
                warn('IA: sin vigilancia, 3 fotos seguidas sin respuesta (%s)' % str(e)[:120])
            time.sleep(interval)
            continue
        if fallo and conf >= float(s.get('umbral', 0.7)):
            strikes += 1
            log('fallo %d/%s: %s %.2f %s' % (strikes, s.get('confirmaciones', 2), tipo, conf, motivo))
        else:
            strikes = 0
        if strikes >= int(s.get('confirmaciones', 2)):
            act(s, tipo, motivo, jpg)
            strikes = 0
            while True:   # no repetir el aviso hasta que se reanude o acabe esta impresión
                time.sleep(30)
                try:
                    if print_stats().get('state') != 'printing':
                        break
                except (urllib.error.URLError, OSError, KeyError, ValueError):
                    pass
            while True:
                time.sleep(30)
                try:
                    if print_stats().get('state') != 'paused':
                        break
                except (urllib.error.URLError, OSError, KeyError, ValueError):
                    pass
        time.sleep(interval)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--test']:   # prueba manual sin pausar nada: la cámara ahora, o --test foto.jpg
        s = load_cfg()
        if not ready(s):
            sys.exit('Configura proveedor, modelo y api_key en ' + CFG)
        try:
            if len(sys.argv) > 2:
                with open(sys.argv[2], 'rb') as f:
                    jpg = f.read()
            else:
                jpg = http(SNAPSHOT, timeout=15)
            print('Proveedor %s, modelo %s' % (s['proveedor'], s.get('modelo')))
            box = find_bed(s, jpg)
            print('Recorte de la cama: %s' % (box or 'ninguno (foto entera)'))
            jpg = crop(jpg, box)
            with open(PD + '/config/ia_prueba.jpg', 'wb') as f:   # Mainsail > Máquina: lo que ha visto la IA
                f.write(jpg)
            text = ask(s, jpg)
        except ValueError as e:   # HTTPError no es ValueError
            sys.exit('La IA no ha contestado: %s. Prueba otro modelo.' % e)
        except urllib.error.HTTPError as e:
            print('Error %s de %s:\n%s' % (e.code, e.url, e.read().decode('utf-8', 'replace')[:600]))
            if e.code == 404 and s['proveedor'] not in ('anthropic', 'google', 'ollama'):
                base = openai_base(s)
                try:
                    ids = [m['id'] for m in json.loads(http(base + '/models', headers={
                        'Authorization': 'Bearer ' + s.get('api_key', '')}, timeout=30))['data']]
                    vis = [i for i in ids if re.search(r'vl|vision|multimodal|llava|vila', i, re.I)]
                    print('Modelo no encontrado. Modelos con vision disponibles:\n  ' + '\n  '.join(vis or ids))
                except (urllib.error.URLError, OSError, KeyError, ValueError):
                    pass
            sys.exit(1)
        except (TimeoutError, OSError) as e:   # URLError y SSLError son OSError
            sys.exit('La IA no ha contestado a tiempo (%s). Revisa la url o prueba un modelo con vision '
                     'mas rapido.' % e)
        print(text)
        print('->', verdict(text))
        vista(jpg, verdict(text), boxes(text), PD + '/config/ia_prueba.jpg')   # con la pieza y el fallo marcados
    else:
        threading.Thread(target=bot_loop, daemon=True).start()
        threading.Thread(target=events_loop, daemon=True).start()
        main()
