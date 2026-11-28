# -*- coding: latin-1 -*-
# TO USE WITH KlipperLCD_Tortillery_v0.4.4
# Based on KlipperLCD by joakimtoe (Apache-2.0, see LICENSE). Modified for Tortillery+:
# power-loss recovery prompt, Klipper error dialog, slicer time estimate, macro list filter,
# maintenance reminder, version on the information page.

import getopt
import os
import sys
import time
import base64
import socket
from threading import Thread
from datetime import timedelta

from urllib.parse import quote

import requests

from printer import PrinterData
from lcd import LCD, _printerData
import tortillery as tp

DEBUG:bool = False

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "0.0.0.0"
    finally:
        s.close()
    return ip


class KlipperLCD ():
    def __init__(self):
        print('KlipperLCD starting...')
        self.Debug = DEBUG
        self.lcd = LCD("/dev/ttyS1", callback=self.lcd_callback,debug=DEBUG) 
        self.lcd.start() 
        # sin clave API: Moonraker confía en 127.0.0.1 (trusted_clients); antes iba una clave fija de otra máquina
        self.printer = PrinterData('', URL=("127.0.0.1"), klippy_sock='/home/mks/printer_data/comms/klippy.sock', callback=self.printer_callback,debug=DEBUG)
        # las órdenes de la pantalla, fuera del bucle de printer.py: una orden larga ya no congela la pantalla
        op = self.printer.op
        self.printer.postREST = tp.GcodeSender(
            lambda path, js: requests.post(op.base_address + path, json=js, headers=dict(op.s.headers), timeout=3600))
        self.running = False
        self.wait_probe = False
        self.thumbnail_inprogress = False
        self.previous_state = None
        self.klippy_alerted = None
        self.layer_text = None
        self.wifi_nets = []    # [{'ssid', 'signal', 'secure', 'active'}]
        self.wifi_page = 0
        self.wifi_ssid = None
        self.meshes, self.mesh_active, self.mesh_sel = [], None, 0
        self.estimates = {}   # filename -> slicer estimated_time (or None)

        progress_bar = 1
        model_asked = False
        while not self.update_printer():
            tp.LAST_TICK = time.time()   # esperar a Klipper (o al modelo) es normal; colgarse aquí no: el watchdog lo ve
            if getattr(self, 'rebooting', False):   # modelo elegido: no pisar el aviso de reinicio
                time.sleep(1)
                continue
            progress_bar += 5
            # Si Klipper no arranca (p. ej. imagen recién grabada sin printer.cfg), decir por qué y la IP para SSH
            text = "Starting Klipper..."
            if progress_bar > 30:
                try:
                    info = (self.printer.getREST('/printer/info') or {}).get('result')
                except Exception:
                    info = None
                msg = tp.klippy_alert(info)
                if tp.needs_model(info) and not model_asked:
                    model_asked = True   # imagen recién grabada: elegir PRO/PLUS en la pantalla (asistente)
                    self.lcd.write('page modelo')
                if msg:
                    text = "IP %s - %s" % (get_ip(), msg.replace('Klipper parado: ', ''))
            self.lcd.boot_progress(progress_bar, text)
            time.sleep(1)

        # el hilo del socket de Klipper muere si se suscribió antes de estar listo (respuestas vacías del estado de
        # error/arranque, p. ej. sin printer.cfg): suscripciones nuevas ahora que Klipper está listo
        self.printer.ks.klippyExit()
        self.printer.ks.webhook_socket.close()
        self.printer.klippy_start()
        self.printer.init_Webservices()
        gcode_store = self.printer.get_gcode_store()
        self.lcd.write_gcode_store(gcode_store)

        macros = tp.screen_macros(self.printer.get_macros())
        self.lcd.write_macros(macros)

        print(self.printer.MACHINE_SIZE)
        print(self.printer.SHORT_BUILD_VERSION)
        self.lcd.write("information.size.txt=\"%s\"" % self.printer.MACHINE_SIZE)
        try:
            with open('/etc/tortillery-release') as f:
                release = f.read().strip()
        except OSError:
            release = ''
        self.lcd.write("information.sversion.txt=\"%s\"" % (
            '%s %s' % (release, self.printer.SHORT_BUILD_VERSION) if release else self.printer.SHORT_BUILD_VERSION))
        if not os.path.exists(tp.SETUP_PENDING):
            self.lcd.write("asist=0")
            self.lcd.write("page main")
        else:
            self.lcd.write("asist=1")   # los botones de volver de WiFi y Nivelación regresan a la bienvenida
            self.lcd.write('asistente.ip.txt="IP %s"' % get_ip())
            self.lcd.write("page asistente")
        time.sleep(3)
        model_val = 0  # Por defecto
        for intento in range(3):
            try:
                volume = self.printer.toolhead.get("axis_maximum", None)
                if volume and len(volume) >= 3:
                    zmax = volume[2]
                    print("Volumen detectado:", volume)
                    if zmax < 290:
                        model_val = 1
                    elif zmax > 291:
                        model_val = 2
                    break
            except Exception as e:
                print("Intento", intento+1, "- error detectando modelo:", e)
            time.sleep(1)
        print("Valor que se enviará a main.va0.val:", model_val)
        self.lcd.write("main.va0.val=%d" % model_val)
        if not self.check_power_loss():
            self.check_maintenance()

    def check_power_loss(self):
        # Offer to continue a print interrupted by a power cut (klippy extra plr.py)
        try:
            plr = self.printer.getREST('/printer/objects/query?plr')['result']['status'].get('plr', {})
        except Exception as e:
            print("PLR: query failed:", e)
            return False
        if plr.get('pending') and self.printer.getState() == "standby":
            print("PLR: interrupted print found:", plr.get('file'))
            self.lcd.ask_plr(plr.get('file', ''))
            return True
        return False

    def check_maintenance(self):
        try:
            total = self.printer.getREST('/server/history/totals')['result']['job_totals']['total_print_time']
        except Exception as e:
            print("Maintenance: query failed:", e)
            return
        hours = tp.maintenance_hours(total)
        if hours >= tp.MAINTENANCE_HOURS:
            self.lcd.ask_confirm(self.lcd.evt.MAINTENANCE_DONE,
                                 "Mantenimiento %d h: engrasa husillos y correas. Hecho?" % hours)

    def update_layer(self):
        # Contador de capas (printpause.layer del TFT Tortillery+); el laminador debe enviar SET_PRINT_STATS_INFO
        try:
            info = self.printer.getREST('/printer/objects/query?print_stats=info')['result']['status']['print_stats']['info']
        except Exception:
            return
        cur, total = info.get('current_layer'), info.get('total_layer')
        text = "Capa %s/%s" % (cur, total) if cur is not None and total else ""
        if text != self.layer_text:
            self.layer_text = text
            self.lcd.write('printpause.layer.txt="%s"' % text)

    # ---- WiFi desde la pantalla (páginas wifi / wifi_pass / wifi_wait / wifi_res del TFT Tortillery+)
    def wifi_scan(self):
        self.lcd.write('wifi.msg.txt="Buscando redes..."')
        tp.wifi_run(['rescan'])
        time.sleep(2)
        self.wifi_nets = tp.wifi_list()
        self.wifi_page = 0
        cur = next((n['ssid'] for n in self.wifi_nets if n['active']), None)
        self.lcd.write('wifi.cur.txt="%s"' % tp.lcd_text(cur or 'Sin conexion WiFi'))
        self.lcd.write('wifi.ip.txt="IP %s"' % get_ip())
        self.wifi_render()

    def wifi_render(self):
        rows = tp.WIFI_ROWS
        nets = self.wifi_nets[self.wifi_page * rows:(self.wifi_page + 1) * rows]
        for i in range(rows):
            if i < len(nets):
                n = nets[i]
                name = ('* ' if n['active'] else '') + n['ssid']
                self.lcd.write('wifi.r%d.txt="       %s"' % (i, tp.lcd_text(name)))
                self.lcd.write('wifi.s%d.pic=wifi.sig0.val+%d' % (i, tp.signal_bars(n['signal'])))
                self.lcd.write('wifi.k%d.pic=wifi.%s.val' % (i, 'lock' if n['secure'] else 'nolock'))
            for obj in ('r', 's', 'k'):
                self.lcd.write('vis %s%d,%d' % (obj, i, 1 if i < len(nets) else 0))
        pages = max(1, -(-len(self.wifi_nets) // rows))
        self.lcd.write('wifi.pg.txt="%d/%d"' % (self.wifi_page + 1, pages))
        self.lcd.write('wifi.msg.txt="%s"' % ('%d redes' % len(self.wifi_nets) if self.wifi_nets
                                               else 'No se ven redes: pulsa buscar'))

    def wifi_select(self, row):
        idx = self.wifi_page * tp.WIFI_ROWS + row
        if idx >= len(self.wifi_nets):
            return
        self.wifi_ssid = self.wifi_nets[idx]['ssid']
        self.lcd.write('wifi_pass.ssid.txt="%s"' % tp.lcd_text(self.wifi_ssid))
        self.lcd.write('wifi_pass.pwd.txt=""')
        self.lcd.write('page wifi_pass')

    def wifi_connect(self, password):
        if not self.wifi_ssid:
            return
        self.lcd.write('wifi_wait.msg.txt="Conectando a %s..."' % tp.lcd_text(self.wifi_ssid))
        ok, msg = tp.wifi_run(['connect', self.wifi_ssid], password)
        if ok:
            time.sleep(2)
            title, text, ico = 'Conectado', '%s\\rIP %s' % (tp.lcd_text(self.wifi_ssid), get_ip()), 'vok'
        else:
            title, text, ico = 'No se pudo conectar', tp.lcd_text(tp.wifi_error(msg)), 'vko'
        self.lcd.write('wifi_res.ico.pic=wifi_res.%s.val' % ico)
        self.lcd.write('wifi_res.t0.txt="%s"' % title)
        self.lcd.write('wifi_res.t1.txt="%s"' % text)
        self.lcd.write('page wifi_res')
        if ok:
            Thread(target=self.wifi_scan, daemon=True).start()

    def setup_model(self, model):
        self.lcd.boot_progress(50, 'Configurando X4 %s...' % model)
        ok, msg = tp.set_model(model)
        if ok:
            self.rebooting = True
            self.lcd.boot_progress(99, 'X4 %s listo: reiniciando la impresora...' % model)
        else:
            self.lcd.write('page modelo')
            self.lcd.show_alert('No se pudo configurar el modelo: %s' % tp.lcd_text(msg), 1)

    def wifi_forget(self):
        if not self.wifi_ssid:
            return
        ok, msg = tp.wifi_run(['forget', self.wifi_ssid])
        title = 'Red olvidada' if ok else 'No se pudo olvidar'
        self.lcd.write('wifi_res.ico.pic=wifi_res.%s.val' % ('vok' if ok else 'vko'))
        self.lcd.write('wifi_res.t0.txt="%s"' % title)
        self.lcd.write('wifi_res.t1.txt="%s"' % tp.lcd_text(self.wifi_ssid if ok else msg))
        self.lcd.write('page wifi_res')
        Thread(target=self.wifi_scan, daemon=True).start()

    def error_log(self):
        rows = tp.last_errors(tp.ERROR_ROWS)
        for i in range(tp.ERROR_ROWS):
            text = rows[i] if i < len(rows) else ('Sin errores guardados' if i == 0 else '')
            self.lcd.write('errores.e%d.txt="%s"' % (i, text.replace('"', "'")[:120]))
        self.lcd.write('page errores')

    def maintenance_status(self):
        try:
            total = self.printer.getREST('/server/history/totals')['result']['job_totals']['total_print_time']
        except Exception as e:
            self.lcd.show_alert("No se pudo leer el historial: %s" % e, self.lcd.PAGE_UTILIDADES)
            return
        hours = tp.maintenance_hours(total)
        self.lcd.write('mant.hrs.txt="%d h"' % hours)
        self.lcd.write('mant.t1.txt="de impresion. Aviso cada %d h"' % tp.MAINTENANCE_HOURS)
        self.lcd.write('page mant')

    # ---- Ventilador de capa, luz LED y mallas (páginas ventilador / neopixel / mallas del TFT Tortillery+)
    def fan_part(self, pct):
        if pct is None:
            try:
                speed = self.printer.getREST('/printer/objects/query?fan')['result']['status']['fan']['speed']
                pct = int(round(speed * 100))
            except Exception:
                pct = 0
            self.lcd.write('ventilador.v.txt="%d %%"' % pct)
            self.lcd.write('page ventilador')
            return
        self.printer.sendGCode('M106 S%d' % round(pct * 2.55))
        self.lcd.write('ventilador.v.txt="%d %%"' % pct)

    def mesh(self, action, row):
        if action in ('abrir', 'cargar', 'guardar', 'borrar'):
            try:
                bm = self.printer.getREST('/printer/objects/query?bed_mesh')['result']['status']['bed_mesh']
                self.meshes = sorted(bm.get('profiles', {}))
                self.mesh_active = bm.get('profile_name') or None
            except Exception:
                self.meshes, self.mesh_active = [], None
            if action == 'abrir':
                self.mesh_sel = self.meshes.index(self.mesh_active) if self.mesh_active in self.meshes else 0
        if action == 'elegir':
            if row < len(self.meshes):
                self.mesh_sel = row
        elif action in ('cargar', 'borrar') and self.mesh_sel < len(self.meshes):
            name = self.meshes[self.mesh_sel]
            if action == 'cargar':
                self.printer.sendGCode('BED_MESH_PROFILE LOAD="%s"' % name)
                self.mesh_active = name
            else:
                self.printer.sendGCode('BED_MESH_PROFILE REMOVE="%s"\nSAVE_CONFIG' % name)
                self.lcd.show_alert('Malla "%s" borrada. Klipper se reinicia.' % tp.lcd_text(name), 1)
                return
        elif action == 'guardar':
            if not self.mesh_active:
                self.lcd.show_alert('No hay malla cargada para guardar.', 1)
                return
            name = tp.next_mesh_name(self.meshes)
            self.printer.sendGCode('BED_MESH_PROFILE SAVE="%s"\nSAVE_CONFIG' % name)
            self.lcd.show_alert('Guardada como "%s". Klipper se reinicia.' % name, 1)
            return
        for i, text in enumerate(tp.mesh_rows(self.meshes, self.mesh_sel, tp.MESH_ROWS)):
            self.lcd.write('mallas.r%d.txt="%s"' % (i, tp.lcd_text(text)))
        self.lcd.write('mallas.cur.txt="%s"' % tp.lcd_text(
            'Activa: %s' % self.mesh_active if self.mesh_active else 'Ninguna malla cargada'))
        if action == 'abrir':
            self.lcd.write('page mallas')

    def filament_material(self, temp, length, feedrate):
        self.lcd.write("page autohome")
        self.lcd.write('autohome.t1.txt="Calentando a %d C..."' % temp)
        gcode = ['M109 S%d' % temp, 'M83']
        if length < 0:
            gcode.append('G1 E5 F%d' % feedrate)  # empuja un poco antes de sacar: no deja el filamento enganchado
        gcode.append('G1 E%d F%d' % (length, feedrate))
        self.printer.sendGCode('\n'.join(gcode))
        self.lcd.write("page prefilament")

    # ---- Calibración guiada (Tortillery+ 2.0): páginas calib, cal_res, pa, pa_pick, extrusor y twist
    def responses(self, since):
        """Respuestas de Klipper en la consola desde `since` (las órdenes enviadas no cuentan)."""
        try:
            store = self.printer.getREST('/server/gcode_store?count=300')['result']['gcode_store']
        except Exception:
            return []
        return [e['message'] for e in store if e['time'] >= since and e.get('type') == 'response']

    def wait_response(self, text, since, timeout):
        """True cuando Klipper responde `text`; False si da error (!!) o se acaba el tiempo."""
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(2)
            msgs = self.responses(since)
            if any(text in m for m in msgs):
                return True
            if any(m.startswith('!!') for m in msgs):
                return False
        return False

    def cal_result(self, text, save_code=0):
        self.lcd.write('cal_res.va0.val=%d' % save_code)
        self.lcd.write('page cal_res')
        self.lcd.write('cal_res.t0.txt="%s"' % text.replace('"', "'"))

    def cal_busy(self, text):
        self.lcd.write('page autohome')
        self.lcd.write('autohome.t1.txt="%s"' % text)

    def saved_variables(self):
        try:
            r = self.printer.getREST('/printer/objects/query?save_variables&configfile=settings')['result']['status']
        except Exception:
            return {}, {}
        return r.get('save_variables', {}).get('variables', {}), r.get('configfile', {}).get('settings', {})

    def calib_shaper(self):
        self.cal_busy('Midiendo vibraciones de X e Y...')
        since = time.time() - 1
        self.printer.sendGCode(('' if self.printer.ishomed() else 'G28\n') + 'SHAPER_CALIBRATE')
        res, end = {}, time.time() + 900
        while time.time() < end and len(res) < 2:
            time.sleep(3)
            msgs = self.responses(since)
            res = tp.parse_shaper(msgs)
            if any(m.startswith('!!') for m in msgs):
                break
        if len(res) < 2:
            self.cal_result('No se pudo medir. ¿Está conectado el acelerómetro? Mira la consola de Mainsail.')
            return
        text, self.pending_accel = tp.shaper_text(res)
        self.cal_result(text + '\\rGuardar reinicia Klipper.', 0x81)

    def z_state(self):
        """-> (offset de G-code en Z, Z de la calibración manual o None si no está activa, Z pedida por G-code)."""
        try:
            st = self.printer.getREST('/printer/objects/query?gcode_move=homing_origin,gcode_position&manual_probe'
                                      )['result']['status']
            mp, gm = st.get('manual_probe', {}), st['gcode_move']
            return (gm['homing_origin'][2], mp.get('z_position') if mp.get('is_active') else None,
                    gm['gcode_position'][2])
        except Exception:
            return 0.0, None, None

    def show_z_offset(self):
        """Pantalla del Z-offset: el valor real tras moverse (calibración manual activa: su Z; si no, el offset)."""
        time.sleep(0.8)
        offset, probe_z, _ = self.z_state()
        val = round((probe_z if probe_z is not None else offset) * 100)
        self.lcd.write('params.z_offset.val=%d' % val)
        self.lcd.write('levelmenu_z.z_offset.val=%d' % val)
        self.lcd.write('adjustzoffset.z_offset.val=%d' % val)

    def auto_mesh(self, points):
        """Nivelación automática: la pantalla de espera se queda hasta que Klipper acaba la malla (antes volvía al menú
        en cuanto veía mandado el SAVE_CONFIG) y luego un aviso con el desnivel; OK vuelve a Nivelación (o a la
        bienvenida del primer arranque)."""
        self.cal_busy('Nivelando la cama: espera a que termine...')
        since = time.time() - 1
        start, total = (20.0, 20.0), points * points
        try:
            bm = self.printer.getREST('/printer/objects/query?configfile=settings')['result']['status'][
                'configfile']['settings']['bed_mesh']
            start = tuple(float(v) for v in str(bm['mesh_min']).strip('[]() ').split(','))
            if not points:
                c = [int(v) for v in str(bm['probe_count']).strip('[]() ').split(',')]
                total = c[0] * c[-1]
        except Exception:
            pass
        self.printer.sendGCode('\n'.join(tp.auto_mesh_gcode(points, self.printer.ishomed())))
        ok, end, shown = False, time.time() + 3600, -1
        while time.time() < end:   # como wait_response, pero contando los puntos medidos
            time.sleep(2)
            msgs = self.responses(since)
            if any(tp.MESH_DONE in m for m in msgs):
                ok = True
                break
            if any(m.startswith('!!') for m in msgs):
                break
            done = tp.mesh_progress(msgs, start)
            if done != shown and done:
                shown = done
                self.lcd.write('autohome.t1.txt="Nivelando la cama: punto %d de %s"'
                               % (min(done, total) if total else done, total or '?'))
        back = tp.PAGE_ASISTENTE if os.path.exists(tp.SETUP_PENDING) else tp.PAGE_LEVELMENU
        if not ok:
            self.lcd.show_alert('La nivelacion no ha terminado. Mira la consola de Mainsail.', back)
            return
        try:
            matrix = self.printer.getREST('/printer/objects/query?bed_mesh')['result']['status']['bed_mesh'][
                'probed_matrix']
        except Exception:
            matrix = None
        self.printer.sendGCode('SAVE_CONFIG')   # guarda la malla "default" (Klipper se reinicia)
        self.lcd.write("levelmenu_z.va1.val=1")
        self.lcd.show_alert(tp.mesh_summary(matrix), back, ok=True)

    def calib_ext_push(self, temp):
        self.cal_busy('Calentando a %d C y empujando 100 mm...' % temp)
        since = time.time() - 1
        self.printer.sendGCode('M109 S%d\nM83\nG1 E100 F60\nM400\nRESPOND MSG="tortillery_ext_ok"' % temp)
        self.wait_response('tortillery_ext_ok', since, 600)
        self.lcd.write('page extrusor')

    def calib_twist_accept(self):
        self.printer.sendGCode('ACCEPT')
        self.twist_point += 1
        time.sleep(3)
        try:
            active = self.printer.getREST('/printer/objects/query?manual_probe')['result']['status'][
                'manual_probe']['is_active']
        except Exception:
            active = False
        self.lcd.z_offset_unit = tp.TWIST_STEP
        self.lcd.write('twist.t1.txt="%s"' % (tp.twist_text(self.twist_point) if active else 'Terminado: pulsa Guardar'))

    def calib(self, action, data):
        if action == 'z_park':
            if self.printer.getState() not in ('printing', 'paused'):
                self.printer.sendGCode(tp.z_park_gcode(self.printer.ishomed(), self.printer.X_MAX_POS * 0.5,
                                                       self.printer.Y_MAX_POS * 0.5))
                Thread(target=self.show_z_offset, daemon=True).start()
        elif action == 'shaper':
            Thread(target=self.calib_shaper, daemon=True).start()
        elif action == 'shaper_save':
            acc = getattr(self, 'pending_accel', None)
            if acc:
                self.printer.sendGCode('SAVE_VARIABLE VARIABLE=max_accel VALUE=%d' % acc)
            self.printer.sendGCode('SAVE_CONFIG')
        elif action == 'pa_print':
            nozzle, bed = data[:2]
            self.pa_material = data[2] if len(data) > 2 else None   # pa_save guarda también el de ese material
            name = 'tortillery_pa.gcode'
            path = os.path.join(self.printer.file_path or os.path.expanduser('~/printer_data/gcodes'), name)
            try:
                with open(path, 'w') as f:
                    f.write(tp.pa_gcode(nozzle, bed))
            except OSError as e:
                self.cal_result('No se pudo crear el patrón: %s' % e)
                return
            self.printer.sendGCode('SDCARD_PRINT_FILE FILENAME="%s"' % name)
        elif action == 'pa_save':
            line = max(1, min(tp.PA_LINES, data or 1))
            pa = tp.pa_value(line)
            mat = getattr(self, 'pa_material', None)
            self.printer.sendGCode('SAVE_VARIABLE VARIABLE=pressure_advance VALUE=%.4f\n' % pa +
                                   ('SAVE_VARIABLE VARIABLE=pa_%s VALUE=%.4f\n' % (mat, pa) if mat else '') +
                                   'SET_PRESSURE_ADVANCE ADVANCE=%.4f' % pa)
            self.cal_result('Línea %d: pressure advance %.3f guardado%s.' % (
                line, pa, ' para %s' % mat.upper() if mat else ''))
        elif action == 'ext_push':
            Thread(target=self.calib_ext_push, args=(data,), daemon=True).start()
        elif action == 'ext_save':
            saved, settings = self.saved_variables()
            cur = saved.get('rotation_distance') or settings.get('extruder', {}).get('rotation_distance')
            rd = tp.rotation_distance(float(cur), (data or 0) / 10.) if cur else None
            if not rd:
                self.cal_result('Medida fuera de rango (debería quedar cerca de 20 mm). Repite la prueba.')
                return
            self.printer.sendGCode('SAVE_VARIABLE VARIABLE=rotation_distance VALUE=%.4f\n'
                                   'SET_EXTRUDER_ROTATION_DISTANCE EXTRUDER=extruder DISTANCE=%.4f' % (rd, rd))
            self.cal_result('rotation_distance: %.4f -> %.4f\\rGuardado. Se aplica en cada arranque.' % (float(cur), rd))
        elif action == 'twist_start':
            self.twist_point = 1
            # paso fijo: Z+/Z- usaban el último elegido en otra página (hasta 0.005 mm) y, como TESTZ sube 0.5 mm y vuelve
            # a bajar en cada pulsación, parecía que no se acercaba a la cama
            self.lcd.z_offset_unit = tp.TWIST_STEP
            self.printer.sendGCode(('' if self.printer.ishomed() else 'G28\n') + 'AXIS_TWIST_COMPENSATION_CALIBRATE')
            self.lcd.write('twist.t1.txt="%s"' % tp.twist_text(1))
        elif action == 'twist_accept':
            Thread(target=self.calib_twist_accept, daemon=True).start()
        elif action == 'twist_save':
            self.printer.sendGCode('SAVE_CONFIG')
            self.lcd.write('page main')

    def ai_page(self):
        st = tp.ai_status()
        names = {'vigilando': 'Vigilando', 'esperando': 'Activa (sin imprimir)', 'apagada': 'Apagada',
                 'sin respuesta': 'Sin respuesta'}
        self.lcd.write('ia.estado.txt="%s"' % names.get(st.get('estado'), st.get('estado', '')))
        self.lcd.write('ia.detalle.txt="%s"' % tp.lcd_text(st.get('detalle', '')))
        self.lcd.write('ia.hora.txt="%s"' % ('Última revisión %s' % st['hora'] if st.get('hora') else ''))
        self.lcd.write('page ia')

    def telegram_qr(self):
        token = tp.telegram_token()
        if not token:
            self.lcd.show_alert('Telegram sin configurar: pon el token de tu bot en telegram.cfg (Mainsail).', 1)
            return
        try:
            import json, urllib.request
            with urllib.request.urlopen('https://api.telegram.org/bot%s/getMe' % token, timeout=15) as r:
                user = json.load(r)['result']['username']
        except Exception as e:
            self.lcd.show_alert('No se pudo contactar con Telegram: %s' % tp.lcd_text(str(e)), 1)
            return
        self.lcd.show_qr('https://t.me/%s' % user, 'Telegram')

    def update_status_bar(self):
        flags = tp.status_flags(get_ip())
        if flags != getattr(self, 'status_shown', None):
            self.status_shown = flags
            for i, on in enumerate(flags):
                self.lcd.write('main.s%d.picc=params.st_%s.val' % (i, 'on' if on else 'off'))

    def check_klippy(self):
        # Klipper stopped (thermal error, MCU lost, bad config...): say why and offer a restart
        try:
            info = (self.printer.getREST('/printer/info') or {}).get('result')
        except Exception:
            return
        msg = tp.klippy_alert(info)
        if msg and msg != self.klippy_alerted:
            print(msg)
            tp.log_error(msg)
            self.klippy_alerted = msg
            self.lcd.show_klipper_err(msg)
        elif info and not msg:
            self.klippy_alerted = None

    def estimated_time(self, file_name):
        if not file_name:
            return None
        if file_name not in self.estimates:
            try:
                meta = self.printer.getREST('/server/files/metadata?filename=' + quote(file_name))
                self.estimates[file_name] = meta['result'].get('estimated_time')
            except Exception:
                self.estimates[file_name] = None
        return self.estimates[file_name]

    def show_file_info(self):
        # tiempo, filamento y altura de capa en la confirmación (askprint) antes de imprimir
        try:
            path = self.lcd.files[self.lcd.selected_file]
            meta = self.printer.getREST('/server/files/metadata?filename=' + quote(path))['result']
        except Exception:
            return
        text = tp.file_info_text(meta)
        if text:
            self.lcd.write('askprint.t1.txt="%s"' % text.replace('"', "'"))

    def start(self):
        print("KlipperLCD start")
        try:   # pieza de la escuadra X/Y (CALIBRAR_ESCUADRA)
            tp.write_skew_file(os.path.expanduser('~/printer_data/gcodes'))
        except OSError as e:
            print('escuadra: %s' % e)
        self.running = True
        #self.lcd.start()
        Thread(target=self.periodic_update).start()

    def update_printer(self):
        # Klipper en error (p. ej. sin printer.cfg) da los objetos vacíos y printer.update_variable lanza KeyError:
        # sin esto el arranque se congelaba en "Starting Klipper..." y el refresco periódico moría.
        # SystemExit: printer.py hace exit(-1) si al reconectar aún no existe klippy.sock (Klipper reiniciándose)
        try:
            return self.printer.update_variable()
        except (KeyError, TypeError, IndexError, SystemExit):
            time.sleep(1)
            return False

    def update_ip_loop(self):
        while True:
            ip = get_ip()
            self.lcd.write('set.t3.txt="%s"' % ip)
            self.lcd.write('wifi.ip.txt="IP %s"' % ip)
            time.sleep(2)
    
    def periodic_update(self):
        while self.running:
            if self.wait_probe:
                print("Zpos=%f, Zoff=%f" % (self.printer.current_position.z, self.printer.BABY_Z_VAR))
                if self.printer.ishomed():
                        self.wait_probe = False
                        print("IsHomed")
                        self.lcd.probe_mode_start()

            self.update_printer()
            self.check_klippy()
            tp.LAST_TICK = time.time()
            ticks = getattr(self, 'ticks', 0) + 1
            self.ticks = ticks
            if ticks % 5 == 1:   # cada ~10 s
                try:
                    self.update_status_bar()
                except Exception as e:
                    print('status bar: %s' % e)
            data = _printerData()
            data.hotend_target = self.printer.thermalManager['temp_hotend'][0]['target']
            data.hotend        = self.printer.thermalManager['temp_hotend'][0]['celsius']
            data.bed_target    = self.printer.thermalManager['temp_bed']['target']
            data.bed           = self.printer.thermalManager['temp_bed']['celsius']
            data.state         = self.printer.getState()
            data.percent       = self.printer.getPercent()
            data.duration      = self.printer.duration()
            data.remaining     = tp.remaining_time(self.estimated_time(self.printer.file_name),
                                               data.duration, data.percent)
            data.feedrate      = self.printer.print_speed
            data.flowrate      = self.printer.flow_percentage
            data.fan           = self.printer.thermalManager['fan_speed'][0]
            data.x_pos         = self.printer.current_position.x
            data.y_pos         = self.printer.current_position.y
            data.z_pos         = self.printer.current_position.z
            offset, probe_z, _ = self.z_state()   # en la calibración manual, la Z que va bajando con Z+/Z-
            data.z_offset      = probe_z if probe_z is not None else offset
            data.file_name     = self.printer.file_name
            data.max_velocity           = self.printer.max_velocity          
            data.max_accel              = self.printer.max_accel             
            data.minimum_cruise_ratio     = self.printer.minimum_cruise_ratio    
            data.square_corner_velocity = self.printer.square_corner_velocity

            if self.previous_state in ["printing", "paused"] and data.state == "standby":
                print("Transición standby sin 'complete' → forzar pantalla main")
                self.lcd.write("page main")
                self.lcd.write("page main")

            self.lcd.data_update(data)
            if data.state in ("printing", "paused"):
                self.update_layer()
            self.previous_state = data.state
                
            time.sleep(2)
        print("periodic_update End")


    def printer_callback(self, data, data_type):
        if 'Tortillery: sin filamento' in str(data):
            # el sensor se quedó sin filamento (ya en pausa): aviso con Aceptar -> cabezal a un lado y página cargar
            self.lcd.write("page sinfil")
        if 'cambio de filamento (M600)' in str(data):
            # M600 (laminador o Utilidades): ya en pausa y aparcado; la página de Sin filamento, a la temperatura de la
            # impresión (la de Filamento calentaría a la del material elegido)
            self.lcd.write("page cargar")
        decided = tp.plr_decided(str(data))
        if decided and self.lcd.confirm_action == self.lcd.evt.PLR_RESUME:
            self.lcd.plr_done(decided == 'resumed')
        msg = self.lcd.format_console_data(data, data_type)
        if msg:
            self.lcd.write_console(msg)

    def show_thumbnail(self):
        if self.printer.file_path and (self.printer.file_name or self.lcd.files[self.lcd.selected_file]):
            file_name = ""
            if self.lcd.files:
                file_name = self.lcd.files[self.lcd.selected_file]
            elif self.printer.file_name:
                file_name = self.printer.file_name
            else:
                print("ERROR: gcode file not known")
            
            file = self.printer.file_path + "/" + file_name

            # Reading file
            print(file)
            f = open(file, "r")
            if not f:
                f.close()
                print("File could not be opened: %s" % file)
                return
            buf = f.readlines()
            if not f:
                f.close()
                print("File could not be read")
                return

            f.close()
            thumbnail_found = False
            b64 = ""

            for line in buf:
                if 'thumbnail begin' in line:
                    thumbnail_found = True
                elif 'thumbnail end' in line:
                    thumbnail_found = False
                    break
                elif thumbnail_found:
                    b64 += line.strip(' \t\n\r;')
        
            if len(b64):
                # Decode Base64
                img = base64.b64decode(b64)        
                
                # Write thumbnail to LCD
                self.lcd.write_thumbnail(img)
            else:
                self.lcd.clear_thumbnail()
                print("Aborting thumbnail, no image found")
        else:
            print("File path or name to gcode-files missing")
        
        self.thumbnail_inprogress = False
        self.previous_state = None

    def lcd_callback(self, evt, data=None):
        if evt == self.lcd.evt.HOME:
            self.printer.home(data)
        elif evt == self.lcd.evt.SHAPER_X:
            self.printer.Shaper_Calibrate("X")
            self.lcd.write("page shaper_wait")
        elif evt == self.lcd.evt.SHAPER_Y:
            self.printer.Shaper_Calibrate("Y")
            self.lcd.write("page shaper_wait")
        elif evt == self.lcd.evt.MOVE_X:
            self.printer.moveRelative('X', data, 4000)
        elif evt == self.lcd.evt.MOVE_Y:
            self.printer.moveRelative('Y', data, 4000)
        elif evt == self.lcd.evt.MOVE_Z:
            self.printer.moveRelative('Z', data, 600)
        elif evt == self.lcd.evt.MOVE_E:
            print(data)
            if (self.printer.thermalManager['temp_hotend'][0]['celsius'] > 180):
                self.printer.moveRelative('E', data[0], data[1])
            else:
                self.lcd.show_alert('Low Temperature!',7)
                print('Error: Low Temperature!')
        elif evt == self.lcd.evt.Z_OFFSET:   # data = paso relativo en mm (+ sube, - baja)
            self.printer.sendGCode('SET_GCODE_OFFSET Z_ADJUST=%.3f MOVE=1' % data)
            Thread(target=self.show_z_offset, daemon=True).start()
        elif evt == self.lcd.evt.NOZZLE:
            self.printer.setExtTemp(data)
        elif evt == self.lcd.evt.BED:
            self.printer.setBedTemp(data)
        elif evt == self.lcd.evt.FILES:
            try:
                res = self.printer.getREST('/server/files/directory?path=' +
                                           quote('gcodes/' + data if data else 'gcodes'))['result']
            except Exception as e:
                print('FILES: %s' % e)
                return []
            return tp.file_entries(data, res.get('dirs', []), res.get('files', []))
        elif evt == self.lcd.evt.PRINT_START:
            # por ruta (las carpetas como USB/ también); antes era por índice de una lista plana
            self.printer.sendGCode('SDCARD_PRINT_FILE FILENAME="%s"' % self.lcd.files[data])
            if self.thumbnail_inprogress == False:
                self.thumbnail_inprogress = True
        elif evt == self.lcd.evt.SETUP_MODEL:
            Thread(target=self.setup_model, args=(data,), daemon=True).start()
        elif evt == self.lcd.evt.SETUP_DONE:
            try:
                os.remove(tp.SETUP_PENDING)
            except OSError:
                pass
            self.lcd.write("asist=0")
            self.lcd.write("page main")
        elif evt == self.lcd.evt.CALIB:
            self.calib(*data)
        elif evt == self.lcd.evt.AI_PAGE:
            self.ai_page()
        elif evt == self.lcd.evt.TELEGRAM_QR:
            Thread(target=self.telegram_qr, daemon=True).start()
        elif evt == self.lcd.evt.WIFI_FORGET:
            Thread(target=self.wifi_forget, daemon=True).start()
        elif evt == self.lcd.evt.ERROR_LOG:
            self.error_log()
        elif evt == self.lcd.evt.FILE_INFO:
            Thread(target=self.show_file_info, daemon=True).start()
        elif evt == self.lcd.evt.THUMBNAIL:
            if self.thumbnail_inprogress == False:
                self.thumbnail_inprogress = True
                Thread(target=self.show_thumbnail).start()
        elif evt == self.lcd.evt.PRINT_STATUS:
            pass
        elif evt == self.lcd.evt.PRINT_STOP:
            self.printer.cancel_job()
        elif evt == self.lcd.evt.PRINT_PAUSE:
            self.printer.pause_job()
        elif evt == self.lcd.evt.PRINT_RESUME:
            self.printer.resume_job()
        elif evt == self.lcd.evt.PLR_RESUME:
            self.printer.sendGCode('RESUME_INTERRUPTED')
        elif evt == self.lcd.evt.PLR_DISCARD:
            self.printer.sendGCode('PLR_CLEAR')
        elif evt == self.lcd.evt.RESTART:
            self.printer.postREST('/printer/firmware_restart', json=None)
        elif evt == self.lcd.evt.FILAMENT_MATERIAL:
            Thread(target=self.filament_material, args=data, daemon=True).start()
        elif evt == self.lcd.evt.MAINTENANCE_STATUS:
            Thread(target=self.maintenance_status, daemon=True).start()
        elif evt == self.lcd.evt.FILAMENT_CHANGE:
            if self.printer.getState() == 'printing':
                self.printer.sendGCode('M600')
            else:
                self.lcd.write('page prefilament')
        elif evt == self.lcd.evt.NEOPIXEL:
            self.printer.sendGCode(tp.neopixel_gcode(*data))
        elif evt == self.lcd.evt.FAN_PART:
            Thread(target=self.fan_part, args=(data,), daemon=True).start()
        elif evt == self.lcd.evt.MESH:
            Thread(target=self.mesh, args=data, daemon=True).start()
        elif evt == self.lcd.evt.WIFI_SCAN:
            Thread(target=self.wifi_scan, daemon=True).start()
        elif evt == self.lcd.evt.WIFI_PAGE:
            pages = max(1, -(-len(self.wifi_nets) // tp.WIFI_ROWS))
            self.wifi_page = (self.wifi_page + data) % pages
            self.wifi_render()
        elif evt == self.lcd.evt.WIFI_SELECT:
            self.wifi_select(data)
        elif evt == self.lcd.evt.WIFI_CONNECT:
            Thread(target=self.wifi_connect, args=(data,), daemon=True).start()
        elif evt == self.lcd.evt.SHOW_QR:
            self.lcd.show_qr("http://%s" % get_ip())
        elif evt == self.lcd.evt.MAINTENANCE_DONE:
            self.printer.sendGCode('MANTENIMIENTO_HECHO')
        elif evt == self.lcd.evt.PRINT_SPEED:
            self.printer.set_print_speed(data)
        elif evt == self.lcd.evt.FLOW:
            self.printer.set_flow(data)
        elif evt == self.lcd.evt.PROBE:
            if data is not None:   # Z+/Z- en la calibración con sonda: printer.probe_calibrate no existe y mataba el hilo
                self.printer.Probe_Z_Test(abs(data), '+' if data > 0 else '-')
                Thread(target=self.show_z_offset, daemon=True).start()
            else:
                self.printer.Probe_Calibrate()
                self.wait_probe = True
        elif evt == self.lcd.evt.PROBE_COMPLETE:        
            self.wait_probe = False
            #self.printer.sendGCode('G1 F1000 Z15.0')   
            self.printer.sendGCode('G29 S4')            
        elif evt == self.lcd.evt.PROBE_BACK:            
            #self.printer.sendGCode('ACCEPT')           
            #self.printer.sendGCode('G1 F1000 Z15.0')   
            self.printer.sendGCode('SAVE_CONFIG')
        elif evt == self.lcd.evt.BED_MESH:
            pass
        elif evt == self.lcd.evt.LIGHT:
            self.printer.set_led(data)
        elif evt == self.lcd.evt.FAN:
            self.printer.set_fan(data)
        elif evt == self.lcd.evt.MOTOR_OFF:
            self.printer.sendGCode('M18')
        elif evt == self.lcd.evt.ACCEL:
            self.printer.sendGCode("SET_VELOCITY_LIMIT ACCEL=%d" % data)
        elif evt == self.lcd.evt.Min_Cruise_Ratio:
            self.printer.sendGCode("SET_VELOCITY_LIMIT minimum_cruise_ratio=%d" % data)
        elif evt == self.lcd.evt.VELOCITY:
            self.printer.sendGCode("SET_VELOCITY_LIMIT VELOCITY=%d" % data)
        elif evt == self.lcd.evt.SQUARE_CORNER_VELOCITY:
            print("SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=%.1f" % data)
            self.printer.sendGCode("SET_VELOCITY_LIMIT SQUARE_CORNER_VELOCITY=%.1f" % data)
        elif evt == self.lcd.evt.CONSOLE:
            self.printer.sendGCode(data)
        elif evt == self.lcd.evt.AutoBedMesh:
            Thread(target=self.auto_mesh, args=(data,), daemon=True).start()   # data = puntos por lado (0: printer.cfg)
        elif evt == self.lcd.evt.Screw_Adjust:
            self.printer.Screw_Adjust(data)
        elif evt == self.lcd.evt.Screws_Tilt_Calculate:
            self.lcd.write("page autohome")
            self.lcd.write('autohome.t1.txt="Screw Tilt Calculate..."')
            self.printer.Screws_Tilt_Calculate()
            self.printer.wait_for_gcode_command(gcode_code=': adjust')
            time.sleep(1)
            self.lcd.write('page 69')
            screws_list = self.printer.Screws_Tilt_Calculate_Show()
            if len(screws_list)== 3:
                self.lcd.screw_alert_4(screws_list)
            elif len(screws_list)== 5:
                self.lcd.screw_alert_6(screws_list)
        elif evt == self.lcd.evt.Pid_Bed:
            self.lcd.write("page autohome")
            self.lcd.write('autohome.t1.txt="Calibrating Bed PID..."')
            self.printer.CalibratePID(data,bed=True)
            self.printer.wait_for_gcode_command(gcode_code='Klipper state: Disconnect')
            self.lcd.write("page levelmenu_PID")
        elif evt == self.lcd.evt.Pid_Extruder:
            self.lcd.write("page autohome")
            self.lcd.write('autohome.t1.txt="Calibrating Extruder PID..."')
            self.lcd.probe_mode=True
            self.printer.CalibratePID(data,bed=False)
            self.printer.wait_for_gcode_command(gcode_code='Klipper state: Disconnect')
            self.lcd.probe_mode=False
            self.lcd.write("page levelmenu_PID")
        elif evt == self.lcd.evt.Probe_calibrate:
            self.printer.Probe_Calibrate()
        elif evt == self.lcd.evt.Probe_Z_PLUS:
            self.printer.Probe_Z_Test(data,'+')
        elif evt == self.lcd.evt.Probe_Z_MINUS:
            self.printer.Probe_Z_Test(data,'-')
        elif evt == self.lcd.evt.ABORT:
            self.printer.sendGCode('ABORT')
        elif evt == self.lcd.evt.Filament_Sensor_Disable:
            self.printer.sendGCode('SET_FILAMENT_SENSOR SENSOR=fila ENABLE=0')
        elif evt == self.lcd.evt.Filament_Sensor_Enable:
            self.printer.sendGCode('SET_FILAMENT_SENSOR SENSOR=fila ENABLE=1')
        elif evt == self.lcd.evt.SAVE_CONFIG:
            self.printer.sendGCode(tp.save_z_gcode(*self.z_state()))
        elif evt == self.lcd.evt.RUNOUT_PARK:
            self.printer.sendGCode('_CAMBIO_FILAMENTO')
        elif evt == self.lcd.evt.EMERGENCY_STOP:
            print("Emergency Stop Triggered!")
            self.printer.emergency_stop()
            time.sleep(1)
            self.printer.sendGCode('FIRMWARE_RESTART')
   
        else:
            print("lcd_callback event not recognised %d" % evt)

if __name__ == "__main__":
    Thread(target=tp.watchdog_loop, daemon=True).start()
    x = KlipperLCD()
    x.start()
    Thread(target=x.update_ip_loop, daemon=True).start()
