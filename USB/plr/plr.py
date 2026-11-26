# Power loss recovery (PLR) for Klipper - Artillery X4 Pro/Plus (Tortillery)
#
# While an SD/virtual_sdcard print is running, the exact file byte offset and
# the matching g-code state are written to disk every `interval` seconds
# (atomic write + fsync, because the rootfs is mounted with commit=120).
# After a power cut, RESUME_INTERRUPTED (plr.cfg) uses this data to continue.
#
# Install: copy to ~/klipper/klippy/extras/plr.py and add [plr] to the config.
import io, os, json, logging, threading, queue


class PLR:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.interval = config.getfloat('interval', 5., minval=1.)
        self.filename = os.path.expanduser(
            config.get('filename', '~/printer_data/plr_state.json'))
        self.data = self._load()
        self.last_state = None
        # Disk writes run in a thread so fsync never stalls the reactor
        self.write_queue = queue.Queue()
        t = threading.Thread(target=self._writer)
        t.daemon = True
        t.start()
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('PLR_CLEAR', self.cmd_PLR_CLEAR,
                               desc="Discard saved power loss recovery data")
        gcode.register_command('PLR_START_FILE', self.cmd_PLR_START_FILE,
                               desc="Continue the saved file at saved offset")
        gcode.register_command('SDCARD_REOPEN', self.cmd_SDCARD_REOPEN,
                               desc="Reopen the paused print file (USB re-inserted)")
        self.printer.register_event_handler('klippy:ready', self._ready)

    def _ready(self):
        self.sdcard = self.printer.lookup_object('virtual_sdcard')
        self.print_stats = self.printer.lookup_object('print_stats')
        self.gcode_move = self.printer.lookup_object('gcode_move')
        self.toolhead = self.printer.lookup_object('toolhead')
        self.extruder = self.printer.lookup_object('extruder')
        self.bed = self.printer.lookup_object('heater_bed', None)
        self.fan = self.printer.lookup_object('fan', None)
        self.runout = self.printer.lookup_object('filament_switch_sensor fila', None)
        self.reactor.register_timer(self._tick, self.reactor.NOW)

    # ---- persistence ----
    def _load(self):
        try:
            with open(self.filename) as f:
                return json.load(f)
        except (IOError, OSError, ValueError):
            return None

    def _writer(self):
        while True:
            data = self.write_queue.get()
            try:
                if data is None:
                    if os.path.exists(self.filename):
                        os.remove(self.filename)
                else:
                    tmp = self.filename + '.tmp'
                    with open(tmp, 'w') as f:
                        json.dump(data, f)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp, self.filename)
                # Persist the rename/remove itself (directory entry)
                dfd = os.open(os.path.dirname(self.filename), os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except Exception:
                logging.exception("plr: unable to write %s", self.filename)

    def _clear(self):
        self.data = None
        self.write_queue.put(None)

    # ---- periodic snapshot ----
    def _tick(self, eventtime):
        state = self.print_stats.get_status(eventtime)['state']
        if state == 'printing' and self.sdcard.is_active():
            self._snapshot(eventtime)
        elif state == 'paused' and self.data is not None:
            # La pausa sube Z (PAUSE Z=20) y se puede mover a mano: RESUME_INTERRUPTED parte de toolhead_z (Z no se
            # vuelve a homear), así que tiene que ser donde está el cabezal de verdad, no donde estaba al pausar.
            # Si no, tras un corte en pausa reanudaba 20 mm por encima de la pieza, imprimiendo al aire.
            z = self.toolhead.get_position()[2]
            if z != self.data['toolhead_z']:
                self.data = dict(self.data, toolhead_z=z)
                self.write_queue.put(dict(self.data))
        elif (state in ('complete', 'cancelled', 'standby')
              and self.last_state in ('printing', 'paused')
              and self.data is not None):
            # Print ended normally in this session (CANCEL_PRINT here uses
            # SDCARD_RESET_FILE, which ends in 'standby', not 'cancelled')
            self._clear()
        # 'paused' and 'error' keep the last snapshot taken while printing
        self.last_state = state
        return eventtime + self.interval

    def _snapshot(self, eventtime):
        gm = self.gcode_move.get_status(eventtime)
        gpos = gm['gcode_position']
        th = self.toolhead.get_status(eventtime)
        data = {
            'file': self.print_stats.get_status(eventtime)['filename'],
            # next_file_position matches the g-code state even while a line
            # is still being dispatched (see virtual_sdcard.work_handler)
            'position': self.sdcard.get_file_position(),
            'x': gpos[0], 'y': gpos[1], 'z': gpos[2], 'e': gpos[3],
            'toolhead_z': self.toolhead.get_position()[2],
            'offset_z': gm['homing_origin'][2],
            'speed': gm['speed'],
            'speed_factor': gm['speed_factor'],
            'extrude_factor': gm['extrude_factor'],
            'absolute_coordinates': gm['absolute_coordinates'],
            'absolute_extrude': gm['absolute_extrude'],
            'extruder_temp': self.extruder.get_status(eventtime)['target'],
            # PRINT_START MATERIAL=... pone el PA del material (no el de arranque)
            'pressure_advance': self.extruder.get_status(eventtime)['pressure_advance'],
            'bed_temp': (self.bed.get_status(eventtime)['target']
                         if self.bed is not None else 0.),
            'fan': (self.fan.get_status(eventtime)['speed']
                    if self.fan is not None else 0.),
            # Slicers change accel per feature (SET_VELOCITY_LIMIT / M204)
            'max_velocity': th['max_velocity'],
            'max_accel': th['max_accel'],
            'square_corner_velocity': th['square_corner_velocity'],
            'minimum_cruise_ratio': th.get('minimum_cruise_ratio', 0.5),
            'runout_enabled': (self.runout.get_status(eventtime)['enabled']
                               if self.runout is not None else True),
        }
        if data['file'] and data != self.data:
            self.data = data
            self.write_queue.put(dict(data))

    # ---- status / commands ----
    def get_status(self, eventtime):
        if not self.data:
            return {'pending': False}
        status = dict(self.data)
        status['pending'] = True
        status['file_exists'] = os.path.isfile(os.path.join(
            self.sdcard.sdcard_dirname, self.data['file']))
        return status

    def cmd_PLR_CLEAR(self, gcmd):
        self._clear()
        gcmd.respond_info("PLR: datos de recuperacion borrados")

    def cmd_PLR_START_FILE(self, gcmd):
        if not self.data:
            raise gcmd.error("PLR: no hay impresion interrumpida")
        if self.sdcard.is_active():
            raise gcmd.error("PLR: ya hay una impresion en curso")
        # Same steps as SDCARD_PRINT_FILE (which also finds files in
        # subfolders, unlike M23), but starting at the saved offset
        self.sdcard._reset_file()
        self.sdcard._load_file(gcmd, self.data['file'], check_subdirs=True)
        self.sdcard.file_position = self.data['position']
        self.sdcard.do_resume()


    def cmd_SDCARD_REOPEN(self, gcmd):
        # After the USB is pulled during a print, the open file handle points
        # to a gone device and RESUME would fail. Swap it for the same file on
        # the re-mounted stick; position and print stats are untouched.
        sd = self.sdcard
        if sd.is_active() or sd.current_file is None:
            raise gcmd.error("SDCARD_REOPEN: no hay ninguna impresion en pausa")
        fname = self.print_stats.get_status(
            self.reactor.monotonic())['filename']
        path = os.path.join(sd.sdcard_dirname, fname)
        try:
            f = io.open(path, 'r', newline='')
            f.seek(0, os.SEEK_END)
            size = f.tell()
        except (IOError, OSError):
            raise gcmd.error("SDCARD_REOPEN: no se puede abrir '%s'" % fname)
        if size != sd.file_size:
            f.close()
            raise gcmd.error("SDCARD_REOPEN: '%s' no es el mismo archivo"
                             " (tamano distinto)" % fname)
        old, sd.current_file = sd.current_file, f
        try:
            old.close()
        except (IOError, OSError):
            pass
        gcmd.respond_info("USB reconectado: ya se puede reanudar")


def load_config(config):
    return PLR(config)
