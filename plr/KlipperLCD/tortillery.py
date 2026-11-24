# Tortillery+ helpers for KlipperLCD (pure functions, no serial/screen access)
import os
import re
import socket
import time

MAINTENANCE_FILE = os.path.expanduser('~/printer_data/tortillery_maintenance')
MAINTENANCE_HOURS = 200   # reminder interval: grease lead screws, check belts

# Macros that have their own button/flow or are G-code commands: not shown in the screen list
_HIDDEN_MACROS = {'PRINT_START', 'PRINT_END', 'PAUSE', 'RESUME', 'CANCEL_PRINT',
                  'RESUME_INTERRUPTED', 'NEOPIXEL_DISPLAY', 'DRAW_LINE_ONLY'}


def screen_macros(names):
    """User-facing macros only (before: M109, M190, T600, NEOPIXEL_DISPLAY... could be run with no params)."""
    return [n for n in names
            if n.upper() not in _HIDDEN_MACROS and not re.match(r'^[GMT]\d+$', n, re.I)]


def remaining_time(estimated, duration, percent):
    """Seconds left. Slicer estimate when known (accurate from the start); after 5 %
    averaged with the progress-based estimate, which follows speed changes (M220)."""
    by_progress = duration / (percent / 100.) - duration if percent > 0 else 0
    if not estimated:
        return max(by_progress, 0)
    by_slicer = max(estimated - duration, 0)
    if percent < 5:
        return by_slicer
    return max((by_slicer + by_progress) / 2, 0)


# Klipper's (English) stop reasons -> short Spanish text. The screen field holds 60 chars and
# main.py shows "Reiniciar? Klipper parado: <text>", so <text> must stay <= 33 chars.
# Most specific first: many messages also contain "MCU" or "shutdown".
_ERRORS = [
    (('unable to open config file',), 'falta printer.cfg (elige modelo)'),   # imagen recién grabada
    (('adc out of range',), 'Temp. fuera de rango (termistor?)'),   # also max_temp exceeded
    (('not heating at expected rate', 'heater_bed'), 'La cama no calienta'),
    (('not heating at expected rate',), 'La boquilla no calienta'),
    (('lost communication with mcu',), 'Sin comunicacion con la placa'),
    (('unable to connect',), 'No se puede conectar con la placa'),
    (('timer too close',), 'Placa saturada (Timer too close)'),
    (('move out of range',), 'Movimiento fuera de limites'),
    (('emergency stop',), 'Parada de emergencia'),
    (('option',), 'Error en printer.cfg'),
    (('section',), 'Error en printer.cfg'),
]


def klippy_alert(info):
    """Short message for the screen when Klipper is stopped (shutdown/error), else None."""
    if not info or info.get('state') not in ('shutdown', 'error'):
        return None
    raw = info.get('state_message') or ''
    low = raw.lower()
    for words, text in _ERRORS:
        if all(w in low for w in words):
            return 'Klipper parado: %s' % text
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    return 'Klipper parado: %s' % (lines[0] if lines else info['state'])


def maintenance_hours(total_print_seconds, path=MAINTENANCE_FILE):
    """Print hours since the last MANTENIMIENTO_HECHO. First run starts counting now."""
    try:
        with open(path) as f:
            base = float(f.read().strip() or 0)
    except (OSError, ValueError):
        with open(path, 'w') as f:
            f.write('%d\n' % total_print_seconds)
        return 0.
    return max(total_print_seconds - base, 0) / 3600.


# ---- WiFi desde la pantalla
WIFI_ROWS = 5
WIFI_SCRIPT = '/usr/local/bin/tortillery-wifi.sh'   # root, vía sudo (regla de install.sh)


def _split_nmcli(line):
    """nmcli -t separa con ':' y escapa ':' y '\\' dentro de los campos."""
    out, cur, esc = [], '', False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == '\\':
            esc = True
        elif ch == ':':
            out.append(cur)
            cur = ''
        else:
            cur += ch
    out.append(cur)
    return out


def parse_wifi_list(text):
    """Salida de 'nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list' -> redes únicas, la activa primero
    y luego por señal."""
    nets = {}
    for line in text.splitlines():
        f = _split_nmcli(line)
        if len(f) < 4 or not f[1]:
            continue
        try:
            sig = int(f[2])
        except ValueError:
            sig = 0
        n = {'ssid': f[1], 'signal': sig, 'secure': f[3] not in ('', '--'), 'active': f[0] == '*'}
        old = nets.get(n['ssid'])
        if old is None or n['active'] or (sig > old['signal'] and not old['active']):
            nets[n['ssid']] = n
    return sorted(nets.values(), key=lambda n: (not n['active'], -n['signal']))


def signal_bars(signal):
    return 4 if signal >= 75 else 3 if signal >= 50 else 2 if signal >= 30 else 1 if signal > 0 else 0


def lcd_text(s):
    """Texto seguro dentro de "..." en un comando de la pantalla."""
    return (s or '').replace('\\', '/').replace('"', "'")[:40]


def wifi_error(msg):
    low = (msg or '').lower()
    if 'password is required' in low or 'sudo' in low:
        return 'Falta el permiso de WiFi: vuelve a instalar Tortillery+ (install.sh)'
    if 'secrets were required' in low or 'psk' in low or 'password' in low:
        return 'Contraseña incorrecta'
    if 'no network with ssid' in low:
        return 'La red ya no se ve. Acércate al router y vuelve a buscar'
    if 'timeout' in low:
        return 'El router no responde (tiempo agotado)'
    return (msg or 'Error desconocido').strip()[:120]


def wifi_run(args, stdin=None, timeout=60):
    """Ejecuta el script de WiFi como root. -> (ok, última línea de salida)"""
    import subprocess
    try:
        r = subprocess.run(['sudo', '-n', WIFI_SCRIPT] + list(args), input=(stdin or '') + '\n', text=True,
                           capture_output=True, timeout=timeout)
    except Exception as e:
        return False, str(e)
    out = (r.stdout.strip() or r.stderr.strip()).splitlines()
    return r.returncode == 0, out[-1] if out else ''


def wifi_list():
    import subprocess
    try:
        r = subprocess.run(['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'],
                           text=True, capture_output=True, timeout=20)
    except Exception:
        return []
    return parse_wifi_list(r.stdout)


# ---- Luz LED (Neopixel) y mallas
NEOPIXEL_LED = 'my_neopixel'
NEOPIXEL_COLORS = [(1, 1, 1), (1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0.55, 0), (0, 0, 0)]  # orden de la pantalla
LED_MODES = {'auto': 0, 'extruder_temp': 2, 'bed_temp': 3}  # LUZ_LED MODO= (1 = color fijo)
MESH_ROWS = 4
MESH_POINTS = [5, 6, 7, 9]   # malla automática: puntos por lado (códigos 0x1060 20-23 de la pantalla)


def neopixel_gcode(kind, value):
    """('color', índice) | ('rgb', (r, g, b) en %) -> color fijo; ('modo', 'auto'|'extruder_temp'|'bed_temp').
    LUZ_LED (utilidades.cfg) lo guarda en tortillery_vars.cfg: se mantiene al imprimir y al reiniciar."""
    if kind == 'color':
        r, g, b = NEOPIXEL_COLORS[value]
    elif kind == 'rgb':
        r, g, b = (round(max(0, min(100, v)) / 100, 2) for v in value)
    else:
        return 'LUZ_LED MODO=%d' % LED_MODES[value]
    return 'LUZ_LED MODO=1 R=%s G=%s B=%s' % (r, g, b)


def auto_mesh_gcode(points, homed):
    """Malla automática como printer.AutoBedMesh, con points x points puntos (0 = los de printer.cfg)."""
    count = ' PROBE_COUNT=%d,%d' % (points, points) if points else ''
    return (['M140 S60', 'M104 S150'] + ([] if homed else ['G28']) +
            ['M190 S60', 'M109 S150', 'BED_MESH_CALIBRATE PROFILE="default"' + count, 'SAVE_CONFIG'])


def next_mesh_name(existing):
    n = 1
    while 'malla_%d' % n in existing:
        n += 1
    return 'malla_%d' % n


def mesh_rows(names, selected, rows=MESH_ROWS):
    """Textos de las filas de la página mallas: la elegida marcada con '>'."""
    out = []
    for i in range(rows):
        if i < len(names):
            out.append('      %s %s' % ('>' if i == selected else ' ', names[i]))
        else:
            out.append('')
    return out


# ---- Asistente de primer arranque (imagen sellada con tortillery-seal.sh)
SETUP_PENDING = os.path.expanduser('~/printer_data/tortillery_setup.pending')   # lo crea tortillery-seal.sh
MODEL_SCRIPT = '/usr/local/bin/tortillery-model.sh'   # root, vía sudo (regla de install.sh)


def needs_model(info):
    """Klipper parado porque no hay printer.cfg (imagen recién grabada): hay que elegir PRO/PLUS."""
    return bool(info) and info.get('state') == 'error' and         'unable to open config file' in (info.get('state_message') or '').lower()


def set_model(model):
    """-> (ok, mensaje). Escribe printer.cfg/macros.cfg del modelo y reinicia Klipper."""
    import subprocess
    try:
        r = subprocess.run(['sudo', '-n', MODEL_SCRIPT, model, '--restart'], text=True, capture_output=True,
                           timeout=60)
    except Exception as e:
        return False, str(e)
    out = (r.stdout.strip() or r.stderr.strip()).splitlines()
    return r.returncode == 0, out[-1] if out else ''


# ---- Explorador de archivos, datos del archivo e historial de errores
ERROR_ROWS = 5          # filas de la página errores
MAX_FILES = 25          # 5 páginas file1..file5 de 5 filas
ERRORS_FILE = os.path.expanduser('~/printer_data/tortillery_errors.log')
_HIDDEN_DIRS = {'System Volume Information', '.thumbs', 'thumbs'}


def file_entries(cwd, dirs, files):
    """Contenido de una carpeta de gcodes (respuesta de /server/files/directory) -> filas de la pantalla:
    [{'name', 'path', 'dir', 'label'}]. Primero '..' (si no es la raíz), luego carpetas y luego archivos,
    los más nuevos primero. Como mucho MAX_FILES."""
    cwd = cwd.strip('/')
    join = lambda n: (cwd + '/' + n) if cwd else n
    out = []
    if cwd:
        parent = cwd.rsplit('/', 1)[0] if '/' in cwd else ''
        out.append({'name': '..', 'path': parent, 'dir': True, 'label': '< Atras', 'icon': 'none'})
    for d in sorted((d['dirname'] for d in dirs), key=str.lower):
        if d.startswith('.') or d in _HIDDEN_DIRS:
            continue
        # con icono (TFT 2.0) el nombre va sin corchetes; el USB montado lleva el suyo
        out.append({'name': d, 'path': join(d), 'dir': True, 'label': d,
                    'icon': 'usb' if not cwd and d == 'USB' else 'dir'})
    gcode = [f for f in files if f['filename'].lower().endswith(('.gcode', '.gco', '.g')) and
             not f['filename'].startswith('.')]
    for f in sorted(gcode, key=lambda f: f.get('modified', 0), reverse=True):
        out.append({'name': f['filename'], 'path': join(f['filename']), 'dir': False, 'label': f['filename'],
                    'icon': 'file'})
    return out[:MAX_FILES]


def file_info_text(meta):
    """Metadatos de Moonraker (/server/files/metadata) -> 2 líneas para askprint.t1 (fuente de 24 px, 251 px de
    ancho: ~20 caracteres por línea). '' si el laminador no dejó datos."""
    if not meta:
        return ''
    lines = []
    t = meta.get('estimated_time')
    if t:
        h, m = int(t // 3600), int(t % 3600 // 60)
        lines.append('%d h %d min' % (h, m) if h else '%d min' % m)
    mm, g, kind = meta.get('filament_total'), meta.get('filament_weight_total'), meta.get('filament_type')
    fil = ['%.1f m' % (mm / 1000)] if mm else []
    if g:
        fil.append('%d g' % round(g))
    if kind:
        fil.append(str(kind).split(';')[0][:6])
    if fil:
        lines.append(' - '.join(fil))
    return '\\r'.join(lines)   # salto de línea del TJC: barra + r literal dentro del txt


def log_error(msg, path=ERRORS_FILE, keep=50):
    import time
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write('%s  %s\n' % (time.strftime('%d/%m %H:%M'), msg.replace('\n', ' ')))
        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) > keep:
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(lines[-keep:])
    except OSError:
        pass


# ---- Calibración guiada (Tortillery+ 2.0). Los valores se guardan con SAVE_VARIABLE (config/calibracion.cfg)
_FITTED = re.compile(r"suggested max_accel <= (\d+)")
_SMOOTH = re.compile(r"smoothing with '(\w+)'")
_RECOMMENDED = re.compile(r"Recommended shaper_type_([xy]) = (\w+), shaper_freq_\1 = ([\d.]+)")


def parse_shaper(messages):
    """Mensajes de SHAPER_CALIBRATE (en orden) -> {'x': (tipo, Hz, max_accel), 'y': ...}. Klipper escribe para cada
    eje la aceleración máxima sugerida de cada tipo y al final el recomendado; se toma la de ese tipo."""
    out, accel = {}, {}
    for m in messages:
        f, s = _FITTED.search(m), _SMOOTH.search(m)
        if f and s:
            accel[s.group(1)] = int(f.group(1))
        r = _RECOMMENDED.search(m)
        if r:
            out[r.group(1)] = (r.group(2), float(r.group(3)), accel.get(r.group(2)))
            accel = {}
    return out


def shaper_text(res):
    """Resultado para la pantalla y la aceleración a guardar (la menor de los dos ejes, redondeada a 100)."""
    lines = ['%s: %s %.1f Hz' % (a.upper(), res[a][0], res[a][1]) for a in ('x', 'y') if a in res]
    acc = [res[a][2] for a in res if res[a][2]]
    max_accel = min(acc) // 100 * 100 if acc else None
    if max_accel:
        lines.append('Acel. maxima: %d' % max_accel)
    return '\\r'.join(lines), max_accel


PA_START, PA_STEP, PA_LINES = 0.0, 0.005, 21   # direct drive (X4): 0 a 0,10


def pa_value(line):
    """Línea elegida (1 = la de delante) -> pressure advance."""
    return round(PA_START + (line - 1) * PA_STEP, 4)


def pa_gcode(nozzle, bed, x0=60, y0=60):
    """Patrón de pressure advance (método de líneas): cada línea, lenta-rápida-lenta con un PA mayor que la
    anterior; la buena es la de grosor uniforme, sin bulto ni hueco al cambiar de velocidad. Una marca a la derecha
    cada 5 líneas (1, 6, 11, 16, 21) para contarlas."""
    h, w = 0.25, 0.5
    e = w * h / (3.14159 * 0.875 ** 2)   # mm de filamento de 1,75 por mm de línea
    g = ['; Tortillery+ patron de pressure advance: %d lineas, PA %.3f a %.3f (linea 1 delante)'
         % (PA_LINES, PA_START, pa_value(PA_LINES)),
         'PRINT_START BED=%d EXTRUDER=%d' % (bed, nozzle), 'G90', 'M83', 'G1 Z%.2f F600' % h]
    for i in range(PA_LINES):
        y = y0 + 5 * i
        g += ['SET_PRESSURE_ADVANCE ADVANCE=%.4f' % pa_value(i + 1),
              'G1 X%d Y%d F9000' % (x0, y), 'G11']
        for x, f in ((x0 + 20, 1200), (x0 + 60, 6000), (x0 + 80, 1200)):
            g.append('G1 X%d E%.4f F%d' % (x, 20 * e if f == 1200 else 40 * e, f))
        if i % 5 == 0:
            g.append('G1 X%d E%.4f F1200' % (x0 + 86, 6 * e))
        g.append('G10')
    g += ['SET_PRESSURE_ADVANCE ADVANCE=0', 'PRINT_END', '']
    return '\n'.join(g)


def rotation_distance(current, remaining, marked=120, asked=100):
    """Extrusor: se marcó a `marked` mm, se pidieron `asked` mm y quedan `remaining` mm hasta la marca.
    -> nueva rotation_distance, o None si la medida no tiene sentido (más de un 20 % de diferencia)."""
    moved = marked - remaining
    if not 0.8 * asked <= moved <= 1.2 * asked:
        return None
    return round(current * moved / asked, 4)


# ---- Barra de estado, vigilancia con IA y Telegram (los escribe tortillery-ai.service)
AI_STATUS = os.path.expanduser('~/printer_data/tortillery_ai.status')
SECRETS = os.path.expanduser('~/printer_data/moonraker.secrets')
CAMERAS = '/dev/v4l/by-id/*-video-index0'


def ai_status(path=AI_STATUS):
    """-> {'estado', 'detalle', 'hora'}; servicio sin arrancar (o 2.0 sin instalar): estado 'apagada'."""
    import json
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'estado': 'apagada', 'detalle': 'configura tortillery_ai.cfg', 'hora': ''}


def telegram_token(path=SECRETS):
    import configparser
    c = configparser.ConfigParser(interpolation=None)
    try:
        c.read(path, encoding='utf-8')
        return c['telegram']['url'].replace('tgram://', '').split('/')[0] or None
    except (KeyError, configparser.Error, OSError):
        return None


def status_flags(ip, ai_path=AI_STATUS, secrets=SECRETS, cameras=CAMERAS):
    """(WiFi/red, cámara, IA, Telegram) para la barra del menú principal."""
    import glob
    return (ip not in ('', '0.0.0.0'), bool(glob.glob(cameras)),
            ai_status(ai_path).get('estado') in ('vigilando', 'esperando'), bool(telegram_token(secrets)))


def last_errors(n=5, path=ERRORS_FILE):
    try:
        with open(path, encoding='utf-8') as f:
            return [l.strip() for l in f.readlines()[-n:]][::-1]   # el más reciente primero
    except OSError:
        return []


# ---- watchdog de systemd (KlipperLCD.service: WatchdogSec + NotifyAccess=all, de install.sh)
LAST_TICK = None   # lo pone periodic_update en cada vuelta; None = aún arrancando (asistente, esperando a Klipper)


def sd_notify(msg, addr=None):
    addr = addr or os.environ.get('NOTIFY_SOCKET')
    if not addr:
        return False   # sin systemd (pruebas, a mano): nada
    if addr[0] == '@':
        addr = '\0' + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(addr)
            s.sendall(msg.encode())
        return True
    except OSError:
        return False


def alive(now=None, tick=None, limit=60):
    """Vivo si aún arranca o si el refresco dio una vuelta hace menos de `limit` s."""
    tick = LAST_TICK if tick is None else tick
    return tick is None or (now or time.time()) - tick < limit


def watchdog_loop():
    while True:
        if alive():
            sd_notify('WATCHDOG=1')   # si el refresco se cuelga o muere, systemd reinicia KlipperLCD
        time.sleep(20)
