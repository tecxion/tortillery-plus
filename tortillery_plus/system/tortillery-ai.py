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
    "Decide if the print has clearly FAILED in one of these ways: 'espagueti' (tangled loose filament, "
    "spaghetti), 'despegada' (part or first layer lifting, curling up, dragged by the nozzle or detached / "
    "knocked over on the bed), 'atasco' (nozzle moving but no filament coming out, or a blob of plastic stuck "
    "to the nozzle). A thin, flat, partially printed first layer is normal. A normal print, a dark/blurry "
    "image or an unclear view is NOT a failure. Answer ONLY with JSON: "
    '{"fallo": true|false, "tipo": "espagueti|despegada|atasco|ninguno", "confianza": 0.0-1.0, '
    '"motivo": "short reason in Spanish (max 12 words)"}'
)
OPENAI_BASES = {'openai': 'https://api.openai.com/v1', 'nvidia': 'https://integrate.api.nvidia.com/v1'}
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


def ask(s, jpg, ctx=''):
    """-> texto de la IA (None si la rechaza). ctx: minutos y capa, para que sepa en qué fase va."""
    p, key, model = s['proveedor'], s.get('api_key', ''), s.get('modelo', '')
    prompt = PROMPT + (' ' + ctx if ctx else '')
    b64 = base64.b64encode(jpg).decode()
    if p == 'anthropic':
        model = model or 'claude-opus-5-5'
        body = {'model': model, 'max_tokens': 2000, 'output_config': {'effort': 'low'},
                'messages': [{'role': 'user', 'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
                    {'type': 'text', 'text': prompt}]}]}
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
        body = {'contents': [{'parts': [{'text': prompt},
                                        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64}}]}]}
        r = json.loads(http('https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent'
                            % urllib.parse.quote(model), body, {'x-goog-api-key': key}))
        return ''.join(x.get('text', '') for x in r['candidates'][0]['content']['parts'])
    if p == 'ollama':
        body = {'model': model or 'qwen2.5vl', 'stream': False, 'format': 'json',
                'messages': [{'role': 'user', 'content': prompt, 'images': [b64]}]}
        r = json.loads(http(s['url'].rstrip('/') + '/api/chat', body, timeout=300))
        return r['message']['content']
    # openai / nvidia / cualquier API compatible con OpenAI (LM Studio, etc.)
    base = (s.get('url') or OPENAI_BASES.get(p, '')).rstrip('/')
    if p == 'nvidia' and '/' not in model:
        model = 'nvidia/' + model   # build.nvidia.com usa ids con dueño: nvidia/..., meta/..., qwen/...
    # 2000: los modelos que razonan (Nemotron super, o-series...) gastan tokens pensando antes de contestar
    body = {'model': model, 'max_tokens': 2000, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': prompt},
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b64}}]}]}
    r = json.loads(http(base + '/chat/completions', body, {'Authorization': 'Bearer ' + key}))
    c = r['choices'][0]
    if not c['message'].get('content'):
        raise ValueError('respuesta vacia (finish_reason=%s)' % c.get('finish_reason'))
    return c['message']['content']


def verdict(text):
    """Texto de la IA -> (fallo, confianza, tipo, motivo). Tolera texto alrededor del JSON."""
    m = re.search(r'\{.*\}', text or '', re.S)
    if not m:
        return False, 0.0, 'ninguno', ''
    try:
        v = json.loads(m.group(0))
    except ValueError:
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


def gcode(script):
    http(MOON + '/printer/gcode/script?script=' + urllib.parse.quote(script), b'', timeout=30, raw=True)


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


def telegram(text, jpg, buttons=False):
    """Texto (jpg None) o foto con texto al chat del bot; con buttons, Reanudar/Cancelar/Otra foto."""
    cred = tg_creds()
    if not cred:
        return
    token, chat = cred
    if jpg is None:
        body = {'chat_id': chat, 'text': text}
        if buttons:
            body['reply_markup'] = BUTTONS
        http('https://api.telegram.org/bot%s/sendMessage' % token, body, timeout=30)
        return
    tg_file(token, chat, 'sendPhoto', 'photo', 'foto.jpg', 'image/jpeg', jpg, text, buttons)


def tg_file(token, chat, method, field, fname, ctype, data, text, buttons=False, timeout=30):
    bound = uuid.uuid4().hex
    parts = []
    fields = [('chat_id', chat), ('caption', text)] + ([('reply_markup', json.dumps(BUTTONS))] if buttons else [])
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


def thumb(jpg):
    """Foto -> miniatura gris 64x48 (bytes) para comparar; None sin Pillow o si la foto no se lee."""
    try:
        import io
        from PIL import Image
        return Image.open(io.BytesIO(jpg)).convert('L').resize((64, 48)).tobytes()
    except Exception:
        return None


def changed(a, b, limit=3.0):
    """¿Cambió la imagen? Diferencia media de gris (0-255). Sin miniaturas que comparar: sí."""
    if a is None or b is None or len(a) != len(b):
        return True
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a) >= limit


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
        cmd = {'resume': '/reanudar', 'cancel': '/cancelar', 'foto': '/foto'}.get(cb.get('data'), '')
    else:
        cmd = (msg.get('text') or '').split('@')[0].strip().lower()
    if cmd == '/foto':
        telegram(estado_text(), http(SNAPSHOT, timeout=15))
    elif cmd == '/estado':
        telegram(estado_text(), None)
    elif cmd == '/reanudar':
        if print_stats().get('state') == 'paused':
            gcode('RESUME')
            telegram('▶️ Reanudando', None)
        else:
            telegram('No está en pausa', None)
    elif cmd == '/cancelar':
        if print_stats().get('state') in ('printing', 'paused'):
            gcode('CANCEL_PRINT')
            telegram('⏹ Impresión cancelada', None)
        else:
            telegram('No hay ninguna impresión', None)
    elif cmd in ('/start', '/ayuda', '/help'):
        telegram('Órdenes: /foto /estado /reanudar /cancelar', None)


def bot_loop():
    """Escucha a Telegram (long polling): botones del aviso y órdenes /foto /estado /reanudar /cancelar."""
    offset = 0
    while True:
        cred = tg_creds()
        if not cred:
            time.sleep(60)
            continue
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
            log('Telegram escucha: %s' % e)
            time.sleep(30)


AI_PAUSED = [0.0]
TIMELAPSE = PD + '/timelapse'
MAINT_FILE = PD + '/tortillery_maintenance'   # el mismo contador que la pantalla y MANTENIMIENTO_HECHO
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


def on_event(prev, state, st):
    name = st.get('filename', '')
    if state == 'paused' and time.time() - AI_PAUSED[0] > 120:   # pausa de la IA: ya avisó act()
        telegram('⏸️ En pausa: %s' % name, snapshot(), buttons=True)
    elif state == 'complete':
        d = int(st.get('print_duration', 0))
        telegram('✅ Terminada: %s (%d h %d min)' % (name, d // 3600, d % 3600 // 60), snapshot())
        threading.Thread(target=send_timelapse, args=(time.time(),), daemon=True).start()
        m = maintenance_text()
        if m:
            telegram(m, None)


def events_loop():
    """Avisos que no da Moonraker: pausa con foto y botones, fin con foto, vídeo del timelapse, mantenimiento."""
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
            last = None
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
            # misma imagen que la última revisada: no se paga otra consulta (pero como mucho 2 veces seguidas)
            if not strikes and skipped < 2 and not changed(th, last):
                skipped += 1
                time.sleep(interval)
                continue
            skipped = 0
            fallo, conf, tipo, motivo = verdict(ask(s, jpg, ctx + '.'))
            if fallo and conf >= float(s.get('umbral', 0.7)) and s.get('modelo_confirmar'):
                f2, c2, t2, m2 = verdict(ask(dict(s, modelo=s['modelo_confirmar']), jpg, ctx + '.'))
                if not (f2 and c2 >= float(s.get('umbral', 0.7))):
                    log('descartado por %s: %s' % (s['modelo_confirmar'], motivo))
                    fallo = False
            last = th
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
    if sys.argv[1:] == ['--test']:   # prueba manual: una foto ahora mismo, sin pausar nada
        s = load_cfg()
        if not ready(s):
            sys.exit('Configura proveedor, modelo y api_key en ' + CFG)
        try:
            text = ask(s, http(SNAPSHOT, timeout=15))
        except ValueError as e:   # HTTPError no es ValueError
            sys.exit('La IA no ha contestado: %s. Prueba otro modelo.' % e)
        except urllib.error.HTTPError as e:
            print('Error %s de %s:\n%s' % (e.code, e.url, e.read().decode('utf-8', 'replace')[:600]))
            if e.code == 404 and s['proveedor'] not in ('anthropic', 'google', 'ollama'):
                base = (s.get('url') or OPENAI_BASES.get(s['proveedor'], '')).rstrip('/')
                try:
                    ids = [m['id'] for m in json.loads(http(base + '/models', headers={
                        'Authorization': 'Bearer ' + s.get('api_key', '')}, timeout=30))['data']]
                    vis = [i for i in ids if re.search(r'vl|vision|multimodal|llava|vila', i, re.I)]
                    print('Modelo no encontrado. Modelos con vision disponibles:\n  ' + '\n  '.join(vis or ids))
                except (urllib.error.URLError, OSError, KeyError, ValueError):
                    pass
            sys.exit(1)
        print(text)
        print('->', verdict(text))
    else:
        threading.Thread(target=bot_loop, daemon=True).start()
        threading.Thread(target=events_loop, daemon=True).start()
        main()
