# Based on KlipperLCD by joakimtoe (Apache-2.0, see LICENSE). Modified for Tortillery+:
# generic confirm dialog on the askprint page, continueprint power-loss page (with fallback
# when the TFT lacks it), 0x105F handling, TJC error-byte tracking.
import binascii
from time import sleep, monotonic
from threading import Thread
from array import array
from io import BytesIO
from PIL import Image
import lib_col_pic

import atexit
import serial
import tortillery as tp

FHONE = 0x5a
FHTWO = 0xa5
FHLEN = 0x06

MaxFileNumber = 25 #

RegAddr_W = 0x80
RegAddr_R = 0x81
CMD_WRITEVAR = 0x82
CMD_READVAR  = 0x83
CMD_CONSOLE  = 0x42

ExchangePageBase = 0x5A010000 # Unsigned long
StartSoundSet    = 0x060480A0
FONT_EEPROM      = 0

# variable addr
ExchangepageAddr = 0x0084
SoundAddr        = 0x00A0

RX_STATE_IDLE = 0
RX_STATE_IDLE_HEX = 0xff
RX_STATE_READ_LEN = 1
RX_STATE_READ_CMD = 2
RX_STATE_READ_DAT = 3

PLA   = 0
ABS   = 1
PETG  = 2
TPU  = 3
PROBE = 4


class _printerData():
    hotend_target   = None
    hotend          = None
    bed_target      = None
    bed             = None

    state           = None

    percent         = None
    duration        = None
    remaining       = None
    feedrate        = None
    flowrate        = 0
    fan             = None
    x_pos           = None
    y_pos           = None
    z_pos           = None
    z_offset        = None
    file_name       = None
    
    max_velocity           = None
    max_accel              = None
    minimum_cruise_ratio     = None
    square_corner_velocity = None

class LCDEvents():
    HOME           = 1
    MOVE_X         = 2
    MOVE_Y         = 3
    MOVE_Z         = 4
    MOVE_E         = 5
    NOZZLE         = 6
    BED            = 7
    FILES          = 8
    PRINT_START    = 9
    PRINT_STOP     = 10
    PRINT_PAUSE    = 11
    PRINT_RESUME   = 12
    PROBE          = 13
    BED_MESH       = 14
    LIGHT          = 15
    FAN            = 16
    MOTOR_OFF      = 17
    PRINT_STATUS   = 18 ## Not needed?
    PRINT_SPEED    = 19
    FLOW           = 20
    Z_OFFSET       = 21
    PROBE_COMPLETE = 22
    PROBE_BACK     = 23
    ACCEL          = 24
    Min_Cruise_Ratio = 25
    VELOCITY       = 26
    SQUARE_CORNER_VELOCITY = 27
    THUMBNAIL      = 28
    CONSOLE        = 29
    AutoBedMesh    = 30
    Screw_Adjust   = 31
    Screws_Tilt_Calculate   = 32
    Z_offset_calibrate  = 33
    Probe_calibrate     = 34
    Probe_Z_PLUS   = 35
    Probe_Z_MINUS  = 36
    Pid_Extruder   = 37
    Pid_Bed        = 38
    SAVE_CONFIG    = 39
    ABORT          = 40
    Filament_Sensor_Enable = 41
    Filament_Sensor_Disable = 42
    SHAPER_X = 43
    SHAPER_Y = 44
    EMERGENCY_STOP = 45
    PLR_RESUME     = 46
    PLR_DISCARD    = 47
    RESTART        = 48
    MAINTENANCE_DONE = 49
    FILAMENT_MATERIAL = 50   # (temp, mm, feedrate): calienta y mueve el filamento
    MAINTENANCE_STATUS = 51
    SHOW_QR        = 52
    WIFI_SCAN      = 53
    WIFI_PAGE      = 54   # +1 / -1
    WIFI_SELECT    = 55   # fila 0-4
    WIFI_CONNECT   = 56   # contraseña (str)
    FILAMENT_CHANGE = 57  # M600 imprimiendo; si no, página de filamento
    NEOPIXEL       = 58   # ('color', índice) o ('modo', 'extruder_temp'|'bed_temp')
    FAN_PART       = 59   # porcentaje, o None para abrir la página con el valor actual
    MESH           = 60
    FILE_INFO      = 61   # datos del archivo elegido en askprint
    WIFI_FORGET    = 62   # olvidar la red elegida en wifi_pass
    ERROR_LOG      = 63   # página errores: últimos errores de Klipper
    SETUP_MODEL    = 64   # asistente: "PRO" | "PLUS"
    CALIB          = 66   # Tortillery+ 2.0: (acción, dato) de las páginas de calibración
    AI_PAGE        = 67   # página Vigilancia IA
    TELEGRAM_QR    = 68   # QR del bot de Telegram
    RUNOUT_PARK    = 69   # sin filamento, Aceptar: cabezal a la izquierda para cargar
    SETUP_DONE     = 65   # asistente: Terminar   # ('abrir'|'elegir'|'cargar'|'guardar'|'borrar', fila)

    
class LCD:
    def __init__(self, port=None, baud=115200, callback=None, debug=False):
        self.Debug = debug
        self.encoding = 'utf-8'  # 'latin-1' con el TFT original de Artillery
        self.addr_func_map = {
            0x1002: self._MainPage,          
            0x1004: self._Adjustment,        
            0x1006: self._PrintSpeed,        
            0x1008: self._StopPrint,         
            0x100A: self._PausePrint,        
            0x100C: self._ResumePrint,       
            0x1026: self._ZOffset,           
            0x1030: self._TempScreen,        
            0x1032: self._CoolScreen,        
            0x1034: self._Heater0TempEnter,  
            0x1038: self._Heater1TempEnter,  
            0x103A: self._HotBedTempEnter,   
            0x103E: self._SettingScreen,     
            0x1040: self._SettingBack,       
            0x1044: self._BedLevelFun,       
            0x1046: self._AxisPageSelect,    
            0x1048: self._Xaxismove,         
            0x104A: self._Yaxismove,         
            0x104C: self._Zaxismove,         
            0x104E: self._SelectExtruder,    
            0x1054: self._Heater0LoadEnter,  
            0x1056: self._FilamentLoad,      
            0x1058: self._Heater1LoadEnter,  
            0x105C: self._SelectLanguage,    
            0x105E: self._FilamentCheck,     
            0x105F: self._PowerContinuePrint,
            0x1060: self._LevellingScreen,
            0x1062: self._Tortillery,        # páginas propias del TFT Tortillery+
            0x1090: self._PrintSelectMode,   
            0x1092: self._XhotendOffset,     
            0x1094: self._YhotendOffset,     
            0x1096: self._ZhotendOffset,     
            0x1098: self._StoreMemory,       
            0x2198: self._PrintFile,         
            0x2199: self._SelectFile,        
            0x110E: self._ChangePage,        
            0x2200: self._SetPreNozzleTemp,  
            0x2201: self._SetPreBedTemp,     
            0x2202: self._HardwareTest,      
            0X2203: self._Err_Control,
            0x4201: self._Console,
            0x4202: self._WifiPassword
        }
        self.evt = LCDEvents()
        self.callback = callback
        self.printer = _printerData()
                         # PLA, ABS, PETG, TPU, PROBE 
        self.preset_temp     = [200, 245,  225, 220, 200]
        self.preset_bed_temp = [ 60, 100,   70,  60,  60]
        self.preset_index    = 0
        # UART communication parameters
        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baud
        self.ser.timeout = None
        self.running = False
        self.rx_buf = bytearray()
        self.rx_data_cnt = 0
        self.rx_state = RX_STATE_IDLE
        self.error_from_lcd = False
        # List of GCode files
        self.files = False
        self.selected_file = False
        self.cwd = ''          # carpeta del explorador, relativa a gcodes/ ('' = raíz)
        self.entries = []      # filas de la carpeta: tortillery.file_entries
        self.waiting = None
        # Adjusting temp and move axis params
        self.adjusting = 'Hotend'
        self.temp_unit = 10
        self.move_unit = 1
        self.load_len = 25
        self.feedrate_e = 300
        self.z_offset_unit = 0.1
        self.light = False
        self.filament_sensor = True        # Adjusting speed
        # Adjusting speed
        self.speed_adjusting = None
        self.speed_unit = 10
        self.adjusting_max = False
        self.accel_unit = 100
        # Probe /Level mode
        self.probe_mode = False
        # Thumbnail
        self.is_thumbnail_written = False
        self.askprint = False
        self.confirm_action = None   # event sent when "Confirm" is pressed on the reused askprint page
        self.lcd_error = None        # (code, time) of the last error byte returned by the TJC screen
        # Make sure the serial port closes when you quit the program.
        atexit.register(self._atexit)

    def _atexit(self):
        self.ser.close()
        self.running = False
    
    def start(self, *args, **kwargs):
        self.running = True
        self.ser.open()
        Thread(target=self.run).start()

        #self.write(b'page boot')
        self.write("page boot")
        self.write(b'com_star')
        self.write(b'main.va0.val=1')
        self.write("boot.j0.val=1")
        self.write("boot.t0.txt=\"Starting KlipperLCD service...\"")
        #self.write("page main")
    
    def boot_progress(self, progress, text="Starting Klipper..."):
        self.write("boot.t0.txt=\"%s\"" % text.replace('"', "'")[:64])
        self.write("boot.j0.val=%d" % min(progress, 99))

    def about_machine(self, size, fw):
        print("Machine size: " + self.printer.MACHINE_SIZE)
        print("Klipper version: " + self.printer.SHORT_BUILD_VERSION)
        self.write("information.size.txt=\"%s\"" % size)
        self.write("information.sversion.txt=\"%s\"" % fw)        

    def write(self, data, eol=True, lf=False):
        dat = bytearray()
        if type(data) == str:
            dat.extend(data.encode(self.encoding, errors='replace'))  # el TFT Tortillery+ es UTF-8
        else:
            dat.extend(data)

        if lf:
            dat.extend(dat[-1:])
            dat.extend(dat[-1:])
            dat[len(dat)-2] = 10 #'\r'
            dat[len(dat)-3] = 13 #'\n'
        self.ser.write(dat)
        if eol:
            self.ser.write(bytearray([0xFF, 0xFF, 0xFF]))

    def read_variable(self, variable_name: str) -> int:
        try:
            print('read_variable')
            command = f'get {variable_name}'
            self.write(command)  # Send command to get the variable
            response = self.ser.read_until(b'\xff\xff\xff')  # Read response until end-of-line markers
            response = response.split(b'\xff\xff\xff')[0]  # Split at FF FF FF and take the first part
            if response[0] == ord('q'):
                # Convert the rest of the bytes to an integer
                int_value = int.from_bytes(response[1:], byteorder='little')
                return int_value  # Return the value as a hexadecimal string
            else:
                print(f'read_variable() error: {response}')
                return -1
        except Exception as ex:
            print(f'read_variable() error: {ex}')
            return -1
        
    def read_element(self, variable_name: str) -> str:
        try:
            command = f'get {variable_name}'
            self.write(command)  # Send command to get the variable
            response = self.ser.read_until(b'\xff\xff\xff')  # Read response until end-of-line markers
            if response[0] == ord('p'):
                str_value = response[1:].decode('ascii')
                return str_value
            else:
                print(f'read_element() error: {response}')
                return None
        except Exception as ex:
            print(f'read_element() error: {ex}')
            return None
        
    def clear_thumbnail(self):
        self.write("printpause.cp0.close()")
        self.write("printpause.cp0.aph=0")
        self.write("printpause.va0.txt=\"\"")


    def write_thumbnail(self, img):
        
        self.clear_thumbnail()
        self.write("printpause.va1.txt=\"\"")  

        # Abrir imagen desde los datos binarios
        im = Image.open(BytesIO(img))
        width, height = im.size
        if width != 160 or height != 160:
            im = im.resize((160, 160))
            width, height = im.size

        pixels = im.load()

        color16 = array('H')
        for i in range(height):
            for j in range(width):
                r, g, b, a = pixels[j, i]
                r = r >> 3
                g = g >> 2
                b = b >> 3
                rgb = (r << 11) | (g << 5) | b
                if rgb == 0x0000:
                    rgb = 0x4AF0  # Color por defecto si es negro puro
                color16.append(rgb)

        output_data = bytearray(height * width * 10)
        result_int = lib_col_pic.ColPic_EncodeStr(
            color16, width, height, output_data,
            width * height * 10, 1024
        )

        each_max = 512
        j = 0
        k = 0
        result = [bytearray()]
        for i in range(len(output_data)):
            if output_data[i] != 0:
                if j % each_max == 0:
                    result.append(bytearray())
                    k += 1
                result[k].append(output_data[i])
                j += 1

        # Enviar imagen codificada al LCD
        self.error_from_lcd = True
        while self.error_from_lcd:
            print("Write thumbnail to LCD")
            self.error_from_lcd = False

            self.clear_thumbnail()
            self.write("printpause.va1.txt=\"\"")  

            sleep(0.2)

            for bytes in result:
                self.write("printpause.cp0.aph=0")
                self.write("printpause.va0.txt=\"\"", eol=True)

                self.write("printpause.va0.txt=\"", eol=False)
                self.write(bytes, eol=False)
                self.write("\"")

                self.write("printpause.va1.txt+=printpause.va0.txt")
                sleep(0.02)

            sleep(0.2)
            self.write("printpause.cp0.aph=127")
            self.write("printpause.cp0.write(printpause.va1.txt)")
            self.is_thumbnail_written = True
            print("Write thumbnail to LCD done!")

        if self.askprint:
            self.write("askprint.cp0.aph=127")
            self.write("askprint.cp0.write(printpause.va1.txt)")
        # Open as image
        im = Image.open(BytesIO(img))
        width, height = im.size
        if width != 160 or height != 160:
            im = im.resize((160, 160))
            width, height = im.size

        pixels = im.load()

        color16 = array('H')
        for i in range(height): #Height
            for j in range(width): #Width
                r, g, b, a = pixels[j, i]
                r = r >> 3
                g = g >> 2
                b = b >> 3
                rgb = (r << 11) | (g << 5) | b
                if rgb == 0x0000:
                    rgb = 0x4AF0
                color16.append(rgb)

        output_data = bytearray(height * width * 10)
        result_int = lib_col_pic.ColPic_EncodeStr(color16, width, height, output_data, width * height * 10, 1024)

        each_max = 512
        j = 0
        k = 0
        result = [bytearray()]
        for i in range(len(output_data)):
            if output_data[i] != 0:
                if j % each_max == 0:
                    result.append(bytearray())
                    k += 1
                result[k].append(output_data[i])
                j += 1

        # Send image to screen
        self.error_from_lcd = True 
        while self.error_from_lcd == True:
            print("Write thumbnail to LCD")
            self.error_from_lcd = False 

            # Clear screen
            self.clear_thumbnail()   

            sleep(0.2)

            for bytes in result:
                self.write("printpause.cp0.aph=0")
                self.write("printpause.va0.txt=\"\"")#

                self.write("printpause.va0.txt=\"", eol = False)
                self.write(bytes, eol = False)
                self.write("\"")

                self.write(("printpause.va1.txt+=printpause.va0.txt"))
                sleep(0.02)

            sleep(0.2)
            self.write("printpause.cp0.aph=127")
            self.write("printpause.cp0.write(printpause.va1.txt)")
            self.is_thumbnail_written = True
            print("Write thumbnail to LCD done!")
        
        if self.askprint == True:
            self.write("askprint.cp0.aph=127")
            self.write("askprint.cp0.write(printpause.va1.txt)")            
   
    def clear_console(self):
        self.write("console.buf.txt=\"\"")
        self.write("console.slt0.txt=\"\"")


    def format_console_data(self, msg, data_type):
        data = None
        if data_type == 'command':
            data = "> " + msg
        elif data_type == 'response':
            if 'B:' in msg and 'T0:' in msg:
                pass ## Filter out temperature responses
            else:
                data = msg.replace("// ", "")
                data = data.replace("??????", "?")
                data = data.replace("echo: ", "")
                data = "< " + data
        else:
            print("format_console_data: type unknown")

        return data
    
    def write_console(self, data):
        if "\"" in data:
            data = data.replace("\"", "'")

        if '\n' in data:
            data = data.replace("\n", "\r\n")
        
        self.write("console.buf.txt=\"%s\"" % data, lf = True)
        self.write("console.buf.txt+=console.slt0.txt")
        self.write("console.slt0.txt=console.buf.txt")

    def write_gcode_store(self, gcode_store):
        self.clear_console()
        for data in gcode_store:
            msg = self.format_console_data(data['message'], data['type'])
            if msg: 
                self.write_console(msg)

    def write_macros(self, macros):
        self.write("macro.cb0.path=\"\"")
        for macro in macros:
            line_feed = True
            if macro == macros[-1]: #Last element, dont print with line feed
                line_feed = False
            self.write("macro.cb0.path+=\"%s\"" % macro, lf = line_feed)


    def data_update(self, data):
        if self.Debug:
            print("data.state: %s self.printer.state: %s" % (data.state, self.printer.state))
            
        if data.hotend_target != self.printer.hotend_target:
            self.write("params.nozzle_target.txt=\"%d\"" % data.hotend_target)
        if data.bed_target != self.printer.bed_target:
            self.write("params.bed_target.txt=\"%d\"" % data.bed_target)
        if data.hotend != self.printer.hotend or data.hotend_target != self.printer.hotend_target:
            self.write("params.nozzletemp.txt=\"%d / %d\"" % (data.hotend, data.hotend_target))
        if data.bed != self.printer.bed or data.bed_target != self.printer.bed_target:
            self.write("params.bedtemp.txt=\"%d / %d\"" % (data.bed, data.bed_target))

        if data.z_offset:
            self.write("params.z_offset.val=%d" % (int)(data.z_offset * 100))
            #self.write("adjustzoffset.z_offset.val=%d" % (int)(data.z_pos * 100))
        if data.x_pos:
            self.write("params.x.val=%d" % (int)(data.x_pos * 100) )
        if data.y_pos:
            self.write("params.y.val=%d" % (int)(data.y_pos * 100) )
        if data.z_pos:
            self.write("params.z.val=%d" % (int)(data.z_pos * 100) )

       

        if self.adjusting_max:
            if data.max_accel != self.printer.max_accel:
                self.write("speed_settings.accel.val=%d" % data.max_accel)
            if data.minimum_cruise_ratio != self.printer.minimum_cruise_ratio:
                self.write("speed_settings.minimum_cruise.val=%d" % data.minimum_cruise_ratio)
            if data.max_velocity != self.printer.max_velocity:
                self.write("speed_settings.velocity.val=%d" % data.max_velocity)
            if data.square_corner_velocity != self.printer.square_corner_velocity:
                self.write("speed_settings.sqr_crnr_vel.val=%d" % int(data.square_corner_velocity*10))

        if data.state != self.printer.state:
                print("Printer state: %s" % data.state)
                if data.state == "printing":
                    print("Ongoing print detected")
                    self.write("page printpause")
                    self.write("restFlag1=0")
                    self.write("restFlag2=1")
                    if self.is_thumbnail_written == False:
                        self.callback(self.evt.THUMBNAIL, None)
                elif data.state == "paused" or data.state == "pausing":
                    print("Ongoing pause detected")
                    self.write("page printpause")
                    self.write("restFlag1=1")
                    if self.is_thumbnail_written == False:
                        self.callback(self.evt.THUMBNAIL, None)
                elif (data.state == "cancelled"):
                    self.write("page main")
                    self.is_thumbnail_written = False
                elif (data.state == "complete"):
                    # patrón de pressure advance terminado: directamente a elegir la línea
                    self.write("page pa_pick" if str(data.file_name).endswith('tortillery_pa.gcode')
                               else "page printfinish")
                    self.is_thumbnail_written = False

        if data != self.printer:
            self.printer = data

    def probe_mode_start(self):
        self.probe_mode = True
        self.z_offset_unit = 1
        self.write("params.z_offset.val=%d" % (int)(self.printer.z_offset * 100))
        self.write("page levelmenu_z")
        self.write("levelmenu_z.tm0.en=0")
        self.write("levelmenu_z.tm0.en=0")

    def run(self):
        while self.running:
                incomingByte = self.ser.read(1)
                if not incomingByte: 
                    print("Received empty byte.") 
                    continue
                if self.rx_state == RX_STATE_IDLE:
                    if incomingByte[0] == FHONE:
                        self.rx_buf.extend(incomingByte)
                    elif incomingByte[0] == FHTWO:
                        if self.rx_buf[0] == FHONE:
                            self.rx_buf.extend(incomingByte)
                            self.rx_state = RX_STATE_READ_LEN
                        else:
                            self.rx_buf.clear()
                            print("Unexpected header received: 0x%02x ()" % incomingByte[0])  
                    elif incomingByte[0] == RX_STATE_IDLE_HEX:
                        self.rx_buf.clear()
                        self.rx_state = RX_STATE_IDLE       
                    else:
                        self.rx_buf.clear()
                        self.error_from_lcd = True
                        self.lcd_error = (incomingByte[0], monotonic())  # e.g. 0x1A/0x03: unknown page/object
                        if self.Debug:
                            print("Unexpected data received: 0x%02x" % incomingByte[0])

                elif self.rx_state == RX_STATE_READ_LEN:
                    # Check if len is as expected, seems to alway be 6 bytes?
                    #if incomingByte[0] == FHLEN:
                    self.rx_buf.extend(incomingByte) # Read length
                    self.rx_state = RX_STATE_READ_DAT
                    #else:
                    #    self.rx_buf.clear()
                    #    self.rx_state = RX_STATE_IDLE
                    #    print("Unexpected len param received: 0x%02x" % incomingByte[0])
                #
                elif self.rx_state == RX_STATE_READ_DAT:
                    self.rx_buf.extend(incomingByte)
                    self.rx_data_cnt += 1
                    len = self.rx_buf[2]
                    if self.rx_data_cnt >= len:
                        # New command/message received from display
                        cmd = self.rx_buf[3]
                        data = self.rx_buf[-(len-1):] # Remove header and command
                        # Handle incoming data
                        self._handle_command(cmd, data)
                        self.rx_buf.clear()
                        self.rx_data_cnt = 0
                        self.rx_state = RX_STATE_IDLE
                else:
                    if self.Debug:
                        print("Unexpected bytes received: %02x" % incomingByte[0])

    # Números de página del TFT Tortillery+ (tortillery_plus/screen/tortillery_pages.py)
    PAGE_PRETEMP = 7
    PAGE_PREFILAMENT = 9
    PAGE_UTILIDADES = 74   # base Tortillery v0.5.2: páginas nuevas desde la 73 (filmat, utilidades...)

    def _Tortillery(self, data):
        code = data[0]
        if 0x01 <= code <= 0x04 or 0x11 <= code <= 0x14:  # cargar / descargar PLA, ABS, PETG, TPU
            if self.printer.state == 'printing':
                self.write("page warn1_filament")
                return
            material = (code & 0x0F) - 1
            length = self.load_len if code < 0x10 else -self.load_len
            self.callback(self.evt.FILAMENT_MATERIAL, (self.preset_temp[material], length, self.feedrate_e))
        elif code == 0x20:
            self.callback(self.evt.CONSOLE, 'COPIA_SEGURIDAD_USB')
        elif code == 0x21:
            self.callback(self.evt.MAINTENANCE_STATUS)
        elif code == 0x22:
            self.callback(self.evt.MAINTENANCE_DONE)
        elif code == 0x23:
            self.callback(self.evt.SHOW_QR)
        elif code == 0x24:
            self.callback(self.evt.RESTART)
        elif code == 0x25:
            self.callback(self.evt.EMERGENCY_STOP)
        elif code == 0x31:
            self.callback(self.evt.WIFI_SCAN)
        elif code in (0x32, 0x33):
            self.callback(self.evt.WIFI_PAGE, -1 if code == 0x32 else 1)
        elif 0x40 <= code <= 0x44:
            self.callback(self.evt.WIFI_SELECT, code - 0x40)
        elif code == 0x26:
            self.callback(self.evt.FILAMENT_CHANGE)
        elif code == 0x27:
            self.callback(self.evt.ERROR_LOG)
        elif code in (0x2B, 0x2C):
            self.callback(self.evt.SETUP_MODEL, 'PRO' if code == 0x2B else 'PLUS')
        elif code == 0x2D:
            self.callback(self.evt.SETUP_DONE)
        elif code == 0x34:
            self.callback(self.evt.WIFI_FORGET)
        elif code == 0x80:
            self.callback(self.evt.CALIB, ('shaper', None))
        elif code == 0x81:
            self.callback(self.evt.CALIB, ('shaper_save', None))
        elif 0x82 <= code <= 0x85:   # patrón de pressure advance con PLA/ABS/PETG/TPU
            m = code - 0x82
            self.callback(self.evt.CALIB, ('pa_print', (self.preset_temp[m], self.preset_bed_temp[m],
                                                        ('pla', 'abs', 'petg', 'tpu')[m])))
        elif code == 0x86:
            self.callback(self.evt.CALIB, ('pa_save', self.read_variable('pa_pick.n.val')))
        elif 0x88 <= code <= 0x8B:   # extrusor: calentar y empujar 100 mm
            self.callback(self.evt.CALIB, ('ext_push', self.preset_temp[code - 0x88]))
        elif code == 0x8C:
            self.callback(self.evt.CALIB, ('ext_save', self.read_variable('extrusor.r.val')))
        elif code in (0x90, 0x91, 0x92):
            self.callback(self.evt.CALIB, ({0x90: 'twist_start', 0x91: 'twist_accept', 0x92: 'twist_save'}[code],
                                           None))
        elif code == 0x94:
            self.callback(self.evt.AI_PAGE)
        elif code == 0x95:
            self.callback(self.evt.TELEGRAM_QR)
        elif code == 0xA0:   # sin filamento: Aceptar
            self.callback(self.evt.RUNOUT_PARK)
        elif 0xA1 <= code <= 0xA6:   # página cargar: sacar (A1-A3) o meter (A4-A6) 10/50/100 mm
            mm = (10, 50, 100)[(code - 0xA1) % 3]
            self.callback(self.evt.MOVE_E, [-mm if code <= 0xA3 else mm, self.feedrate_e])
        elif code == 0xA7:   # página cargar: Reanudar
            if self.printer.state in ('paused', 'pausing'):
                self.callback(self.evt.PRINT_RESUME)
            self.write("page printpause")
        elif 0x50 <= code <= 0x55:
            self.callback(self.evt.NEOPIXEL, ('color', code - 0x50))
        elif code == 0x56:   # color a medida (página led_rgb, valores 0-100)
            rgb = tuple(self.read_variable('led_rgb.%s.val' % c) for c in 'rgb')
            if all(v is not None and 0 <= v <= 100 for v in rgb):
                self.callback(self.evt.NEOPIXEL, ('rgb', rgb))
        elif code in (0x58, 0x59, 0x5A):
            self.callback(self.evt.NEOPIXEL, ('modo', {0x58: 'extruder_temp', 0x59: 'auto', 0x5A: 'bed_temp'}[code]))
        elif 0x60 <= code <= 0x64:
            self.callback(self.evt.FAN_PART, (0, 25, 50, 75, 100)[code - 0x60])
        elif code == 0x65:
            self.callback(self.evt.FAN_PART, None)
        elif code == 0x70:
            self.callback(self.evt.MESH, ('abrir', None))
        elif 0x71 <= code <= 0x74:
            self.callback(self.evt.MESH, ('elegir', code - 0x71))
        elif code in (0x78, 0x79, 0x7A):
            self.callback(self.evt.MESH, ({0x78: 'cargar', 0x79: 'guardar', 0x7A: 'borrar'}[code], None))
        else:
            print("_Tortillery: Not recognised %d" % code)

    def _WifiPassword(self, data):
        # trama 0x42 de wifi_pass (como la consola): la contraseña termina en \r para no llegar nunca vacía
        self.callback(self.evt.WIFI_CONNECT, bytes(data).decode('utf-8', errors='replace').rstrip('\r'))

    def show_qr(self, url, title=None):
        self.write("page qr")
        if title:
            self.write('qr.title.txt="%s"' % title)
        self.write('qr.qr0.txt="%s"' % url)
        self.write('qr.url.txt="%s"' % url)

    def show_klipper_err(self, msg):
        # Página propia del TFT Tortillery+; con el TFT de Artillery, la de confirmación de siempre
        text = msg.replace('"', "'")[:250]
        sent = monotonic()
        self.write("page klipper_err")
        sleep(0.3)  # la pantalla responde enseguida si la página no existe
        err = self.lcd_error
        if err and err[1] >= sent and err[0] in (0x03, 0x1A):
            self.ask_confirm(self.evt.RESTART, "Reiniciar? " + msg)
            return
        self.write('klipper_err.t0.txt="%s"' % text)

    def show_alert(self,message:str,nextpages=1):
        self.write("page show_alert")
        self.write(f'nextpages={nextpages}')
        self.write(f't1.txt="{message}"')


    def _handle_command(self, cmd, dat):
        if cmd == CMD_WRITEVAR: #0x82
            print("Write variable command received")
            print(binascii.hexlify(dat))
        elif cmd == CMD_READVAR: #0x83
            addr = dat[0]
            addr = (addr << 8) | dat[1]
            bytelen = dat[2]
            data = [32]
            for i in range (0, bytelen, 2):
                idx = int(i / 2)
                data[idx] = dat[3 + i]
                data[idx] = (data[idx] << 8) | dat[4 + i]
            self._handle_readvar(addr, data)
        elif cmd == CMD_CONSOLE: #0x42
            addr = dat[0]
            addr = (addr << 8) | dat[1]
            data = dat[3:] # Remove addr and len
            self._handle_readvar(addr, data)
        else:
            print("Command not reqognised: %d" % cmd)
            print(binascii.hexlify(dat))

    def _handle_readvar(self, addr, data):
        if addr in self.addr_func_map:
            # Call function corresponding with addr
            if (self.addr_func_map[addr].__name__ == "_BedLevelFun" and data[0] == 0x0a):
                pass ## Avoid to spam the log file while printing
            else:
                print("%s: len: %d data[0]: %x" % (self.addr_func_map[addr].__name__, len(data), data[0]))
            self.addr_func_map[addr](data)
        else:
            print("_handle_readvar: addr %x not recognised" % addr)

    def _Console(self, data):
        if data[0] == 0x01: # Back
            state = self.printer.state
            if state == "printing" or state == "paused" or state == "pausing":
                self.write("page printpause")
            else:
                self.write("page main")
        else:
            print(data.decode())
            self.callback(self.evt.CONSOLE, data.decode())

    def _show_dir(self):
        # Explorador por carpetas (USB incluido): '< Atras', [carpetas] y archivos, los más nuevos primero
        self.entries = self.callback(self.evt.FILES, self.cwd) or []
        self.files = [e['path'] for e in self.entries] or False
        for i in range(MaxFileNumber):
            e = self.entries[i] if i < len(self.entries) else None
            label = e['label'].replace('"', "'") if e else ''
            self.write("file%d.t%d.txt=\"%s\"" % (i // 5 + 1, i, label))
            # icono de la fila (TFT Tortillery+ 2.0; con otro TFT el componente no existe y la pantalla lo ignora)
            self.write("file%d.i%d.picc=params.ic_%s.val" % (i // 5 + 1, i, e.get('icon', 'none') if e else 'none'))
        self.write("page file1" if self.entries else "page nosdcard")

    def _MainPage(self, data): #
        if data[0] == 1: # Print
            self.cwd = ''
            self._show_dir()

        elif data[0] == 2: # Abort print
            print("Abort print not supported") #TODO:
        else:
            print("_MainPage: %d not supported" % data[0])
    
    def _Adjustment(self, data):
        if data[0] == 0x01: # Filament tab
            self.write("adjusttemp.targettemp.val=%d" % self.printer.hotend_target)
            self.write("adjusttemp.va0.val=1")
            self.write("adjusttemp.va1.val=3") #Setting default to 10
            self.adjusting = 'Hotend'
            self.temp_unit = 10
            self.move_unit = 1
        elif data[0] == 0x02:
            self.write("page printpause")
        elif data[0] == 0x03:
            if self.printer.fan > 0:
                self.printer.fan = 0
                self.callback(self.evt.FAN, 0)
            else:
                self.printer.fan = 100
                self.callback(self.evt.FAN, 100)
        elif data[0] == 0x05:
            print("Filament tab")
            self.speed_adjusting = None
            self.write("page adjusttemp")
        elif data[0] == 0x06: # Speed tab
            print("Speed tab")
            self.speed_adjusting = 'PrintSpeed'
            self.write("adjustspeed.targetspeed.val=%d" % self.printer.feedrate)
            self.write("page adjustspeed")
        elif data[0] == 0x07: # Adjust tab
            print("Adjust tab")
            self.z_offset_unit = 0.1
            self.speed_adjusting = None
            self.write("adjustzoffset.zoffset_value.val=2")
            print(self.printer.z_offset)
            self.write("adjustzoffset.z_offset.val=%d" % (int) (self.printer.z_offset * 100))
            self.write("page adjustzoffset")
        elif data[0] == 0x08: #
            self.printer.feedrate = 100
            self.write("adjustspeed.targetspeed.val=%d" % 100)
            self.callback(self.evt.PRINT_SPEED, self.printer.feedrate)
        elif data[0] == 0x09:
            self.printer.flowrate = 100
            self.write("adjustspeed.targetspeed.val=%d" % 100)
            self.callback(self.evt.FLOW, self.printer.flowrate)
        elif data[0] == 0x0a:
            self.printer.fan = 100
            self.write("adjustspeed.targetspeed.val=%d" % 100)
            self.callback(self.evt.FAN, self.printer.fan)
        else:
            print("_Adjustment: %d not supported" % data[0])
    
    def _PrintSpeed(self, data):        
        print("_PrintSpeed: %d not supported" % data[0])
    
    def _StopPrint(self, data):  
        if data[0] == 0x01 or data[0] == 0xf1:
            self.callback(self.evt.PRINT_STOP)
            self.write("resumeconfirm.t1.txt=\"Stopping print. Please wait!\"")
        elif data[0] == 0xF0:
            if self.printer.state == "printing":
                self.write("page printpause")
        else:
            print("_StopPrint: %d not supported" % data[0])
    
    def _PausePrint(self, data):        
        if data[0] == 0x01:
            if self.printer.state == "printing":
                self.write("page pauseconfirm")
        elif data[0] == 0xF1:
            self.callback(self.evt.PRINT_PAUSE)
            self.write("page printpause")
        else:
            print("_PausePrint: %d not supported" % data[0])
           
    
    def _ResumePrint(self, data):       
        if data[0] == 0x01:
            if self.printer.state == "paused" or self.printer.state == "pausing":
                self.callback(self.evt.PRINT_RESUME)
            self.write("page printpause")
        else:
            print("_ResumePrint: %d not supported" % data[0])
    
    def _ZOffset(self, data):           
        print("_ZOffset: %d not supported" % data[0])
    
    def _TempScreen(self, data):
        if data[0] == 0x01: # Hotend
            self.write("adjusttemp.targettemp.val=%d" % self.printer.hotend_target)
            self.adjusting = 'Hotend'
        elif data[0] == 0x03: # Heatbed
            self.write("adjusttemp.targettemp.val=%d" % self.printer.bed_target)
            self.adjusting = 'Heatbed'
        elif data[0] == 0x04: # 
            pass
        elif data[0] == 0x05: # Move 0.1mm / 1C / 1%
            self.temp_unit = 1
            self.speed_unit = 1
            self.move_unit = 0.1
            self.accel_unit = 10
        elif data[0] == 0x06: # Move 1mm / 5C / 5%
            self.temp_unit = 5
            self.speed_unit = 5
            self.move_unit = 1
            self.accel_unit = 50
        elif data[0] == 0x07: # Move 10mm / 10C /10%
            self.temp_unit = 10
            self.speed_unit = 10
            self.move_unit = 10
            self.accel_unit = 100
        elif data[0] == 0x08: # + temp
            if self.adjusting == 'Hotend':
                self.printer.hotend_target += self.temp_unit
                self.write("adjusttemp.targettemp.val=%d" % self.printer.hotend_target)
                self.callback(self.evt.NOZZLE, self.printer.hotend_target)
            elif self.adjusting == 'Heatbed':
                self.printer.bed_target += self.temp_unit
                self.write("adjusttemp.targettemp.val=%d" % self.printer.bed_target)
                self.callback(self.evt.BED, self.printer.bed_target)

        elif data[0] == 0x09: # - temp
            if self.adjusting == 'Hotend':
                self.printer.hotend_target -= self.temp_unit
                self.write("adjusttemp.targettemp.val=%d" % self.printer.hotend_target)
                self.callback(self.evt.NOZZLE, self.printer.hotend_target)
            elif self.adjusting == 'Heatbed':
                self.printer.bed_target -= self.temp_unit
                self.write("adjusttemp.targettemp.val=%d" % self.printer.bed_target)
                self.callback(self.evt.BED, self.printer.bed_target)
        elif data[0] == 0x0a: # Print
            self.write("adjustspeed.targetspeed.val=%d" % self.printer.feedrate)
            self.speed_adjusting = 'PrintSpeed'
        elif data[0] == 0x0b: # Flow
            self.write("adjustspeed.targetspeed.val=%d" % self.printer.flowrate)
            self.speed_adjusting = 'Flow'
        elif data[0] == 0x0c: # Fan
            self.write("adjustspeed.targetspeed.val=%d" % self.printer.fan)
            self.speed_adjusting = 'Fan'
        elif data[0] == 0x0d or data[0] == 0x0e: # Adjust speed
            unit = self.speed_unit 
            if data[0] == 0x0e:
                unit = -self.speed_unit
            if self.speed_adjusting == 'PrintSpeed':
                self.printer.feedrate += unit
                self.write("adjustspeed.targetspeed.val=%d" % self.printer.feedrate)
                self.callback(self.evt.PRINT_SPEED, self.printer.feedrate)
            elif self.speed_adjusting == 'Flow':
                self.printer.flowrate += unit
                self.write("adjustspeed.targetspeed.val=%d" % self.printer.flowrate)
                self.callback(self.evt.FLOW, self.printer.flowrate)
            elif self.speed_adjusting == 'Fan':
                self.printer.fan += unit
                self.write("adjustspeed.targetspeed.val=%d" % self.printer.fan)
                self.callback(self.evt.FAN, self.printer.fan)
            else:
                print("self.speed_adjusting not recognised %s" % self.speed_adjusting)
        elif data[0] == 0x42: # Accel/Speed advanced
            self.speed_unit = 10
            self.accel_unit = 100
            self.adjusting_max = True
            self.write("speed_settings.t4.font=0")
            self.write("speed_settings.accel.val=%d" % self.printer.max_accel)
            self.write("speed_settings.minimum_cruise.val=%d" % self.printer.minimum_cruise_ratio)
            self.write("speed_settings.velocity.val=%d" % self.printer.max_velocity)
            self.write("speed_settings.sqr_crnr_vel.val=%d" % int(self.printer.square_corner_velocity*10))
        elif data[0] == 0x43: # Max acceleration set
            self.adjusting_max = False

        elif data[0] == 0x11 or data[0] == 0x15: #Accel decrease / increase
            unit = self.accel_unit
            if data[0] == 0x11:
                unit = -self.accel_unit
            new_accel = self.printer.max_accel + unit
            self.write("speed_settings.accel.val=%d" % new_accel)
            
            self.callback(self.evt.ACCEL, new_accel)
            self.printer.max_accel = new_accel

        elif data[0] == 0x12 or data[0] == 0x16: #Accel to Decel decrease / increase
            unit = self.accel_unit
            if data[0] == 0x12:
                unit = -self.accel_unit
            new_accel = self.printer.minimum_cruise_ratio + unit
            self.write("speed_settings.minimum_cruise.val=%d" % new_accel)
            
            self.callback(self.evt.Min_Cruise_Ratio, new_accel)
            self.printer.minimum_cruise_ratio = new_accel

        elif data[0] == 0x13 or data[0] == 0x17: #Velocity decrease / increase
            unit = self.speed_unit
            if data[0] == 0x13:
                unit = -self.speed_unit
            new_velocity = self.printer.max_velocity + unit
            self.write("speed_settings.velocity.val=%d" % new_velocity)
            
            self.callback(self.evt.VELOCITY, new_velocity)
            self.printer.max_velocity = new_velocity

        elif data[0] == 0x14 or data[0] == 0x18: #Square Corner Velozity decrease / increase
            unit = self.speed_unit/10
            if data[0] == 0x14:
                unit = -self.speed_unit/10
            new_velocity = self.printer.square_corner_velocity + unit
            print(new_velocity*10)
            self.write("speed_settings.sqr_crnr_vel.val=%d" % int(new_velocity*10))

            self.callback(self.evt.SQUARE_CORNER_VELOCITY, new_velocity)
            self.printer.square_corner_velocity = new_velocity

        else:
            print("_TempScreen: Not recognised %d" % data[0])
    
    def _LevellingScreen(self, data):

        if data[0] == 0x01: # Auto_BedMesh
            self.callback(self.evt.AutoBedMesh,0)
        elif 0x20 <= data[0] <= 0x23: # Auto_BedMesh eligiendo los puntos (Tortillery+: 5x5, 6x6, 7x7, 9x9)
            self.callback(self.evt.AutoBedMesh, tp.MESH_POINTS[data[0] - 0x20])
        elif data[0] == 0x02: # bed_screw
            position_value = self.read_variable('levelmenu_scr.probe.val')
            if (position_value >= 0):
                self.callback(self.evt.Screw_Adjust,position_value)     
        elif data[0] == 0x03: # probe_calibrate
            self.callback(self.evt.Probe_calibrate,0)     
        elif data[0] == 0x04: # z_tilt_up
            self.callback(self.evt.Probe_Z_PLUS,self.z_offset_unit)     
        elif data[0] == 0x05: # z_tilt_down
            self.callback(self.evt.Probe_Z_MINUS,self.z_offset_unit)     
        elif data[0] == 0x06: # PID_nozzle
            target_pid = self.read_variable('levelmenu_PID.va1.val')
            if (target_pid > 0 and target_pid <= 300):
                self.callback(self.evt.Pid_Extruder,target_pid)     
        elif data[0] == 0x07: # PID_Bed
            target_pid = self.read_variable('levelmenu_PID.va2.val')
            if (target_pid > 0 and target_pid <= 200):
                self.callback(self.evt.Pid_Bed,target_pid)    
        elif data[0] == 0x08: # Screws_Tilt_Calculate
                self.callback(self.evt.Screws_Tilt_Calculate,0)      
        elif data[0] == 0x10: # SAVE_CONFIG
            print("ACCEPT AND SAVE_CONFIG")
            self.callback(self.evt.SAVE_CONFIG,0)
        elif data[0] == 0x11: # SAVE_CONFIG
            print("ABORT")
            self.callback(self.evt.ABORT,0)
        else:
            print("_TempScreen: Not recognised %d" % data[0])
        if data[0] == 0x12:
            self.callback(self.evt.SHAPER_X, 0)
        elif data[0] == 0x13:
            self.callback(self.evt.SHAPER_Y, 0)   
    
    def _CoolScreen(self, data):
        if data[0] == 0x01: #Turn off nozzle
            if self.printer.state == "printing":
                # Ignore
                self.write("adjusttemp.targettemp.val=%d" % self.printer.hotend_target)
            else:
                self.callback(self.evt.NOZZLE, 0)
        elif data[0] == 0x02: #Turn off bed
            self.callback(self.evt.BED, 0)
        elif data[0] == 0x09: #Preheat PLA
            self.callback(self.evt.NOZZLE, self.preset_temp[PLA])
            self.callback(self.evt.BED, self.preset_bed_temp[PLA])
            self.write("params.nozzle_target.txt=\"%d\"" % self.preset_temp[PLA])
            self.write("params.bed_target.txt=\"%d\"" % self.preset_bed_temp[PLA])
        elif data[0] == 0x0a: #Preheat ABS
            self.callback(self.evt.NOZZLE, self.preset_temp[ABS])
            self.callback(self.evt.BED, self.preset_bed_temp[ABS])
            self.write("params.nozzle_target.txt=\"%d\"" % self.preset_temp[ABS])
            self.write("params.bed_target.txt=\"%d\"" % self.preset_bed_temp[ABS])
        elif data[0] == 0x0b: #Preheat PETG
            self.callback(self.evt.NOZZLE, self.preset_temp[PETG])
            self.callback(self.evt.BED, self.preset_bed_temp[PETG])
            self.write("params.nozzle_target.txt=\"%d\"" % self.preset_temp[PETG])
            self.write("params.bed_target.txt=\"%d\"" % self.preset_bed_temp[PETG])
        elif data[0] == 0x0c: #Preheat TPU
            self.callback(self.evt.NOZZLE, self.preset_temp[TPU])
            self.callback(self.evt.BED, self.preset_bed_temp[TPU])
            self.write("params.nozzle_target.txt=\"%d\"" % self.preset_temp[TPU])
            self.write("params.bed_target.txt=\"%d\"" % self.preset_bed_temp[TPU])
        elif data[0] == 0x0d: #Preheat PLA setting
            self.preset_index = PLA
            self.write("tempsetvalue.nozzletemp.val=%d" % self.preset_temp[PLA])
            self.write("tempsetvalue.bedtemp.val=%d" % self.preset_bed_temp[PLA])
            self.write("page tempsetvalue")
        elif data[0] == 0x0e: #Preheat ABS setting
            self.preset_index = ABS
            self.write("tempsetvalue.nozzletemp.val=%d" % self.preset_temp[ABS])
            self.write("tempsetvalue.bedtemp.val=%d" % self.preset_bed_temp[ABS])
            self.write("page tempsetvalue")
        elif data[0] == 0x0f: #Preheat PETG setting
            self.preset_index = PETG
            self.write("tempsetvalue.nozzletemp.val=%d" % self.preset_temp[PETG])
            self.write("tempsetvalue.bedtemp.val=%d" % self.preset_bed_temp[PETG])
            self.write("page tempsetvalue")
        elif data[0] == 0x10: #Preheat TPU setting
            self.preset_index = TPU
            self.write("tempsetvalue.nozzletemp.val=%d" % self.preset_temp[TPU])
            self.write("tempsetvalue.bedtemp.val=%d" % self.preset_bed_temp[TPU])
            self.write("page tempsetvalue")
        elif data[0] == 0x11: # Level
            self.preset_index = PROBE
            self.write("tempsetvalue.nozzletemp.val=%d" % self.preset_temp[PROBE])
            self.write("tempsetvalue.bedtemp.val=%d" % self.preset_bed_temp[PROBE])
            self.write("page tempsetvalue")
        else:
            print("_CoolScreen: Not recognised %d" % data[0])
    
    def _Heater0TempEnter(self, data):
        temp = ((data[0] & 0x00FF) << 8) | ((data[0] & 0xFF00) >> 8) 
        print("Set nozzle temp: %d" % temp)
        self.callback(self.evt.NOZZLE, temp)
    
    def _Heater1TempEnter(self, data):  
        print("_Heater1TempEnter: %d not supported" % data[0])
    
    def _HotBedTempEnter(self, data):   
        temp = ((data[0] & 0x00FF) << 8) | ((data[0] & 0xFF00) >> 8) 
        self.callback(self.evt.BED, temp)
    
    def _SettingScreen(self, data):
        if data[0] == 0x01:
            self.callback(self.evt.PROBE)
            self.write("page autohome")
            self.write("levelmenu_z.va1.val=1")

        elif data[0] == 0x06: # Motor release
            self.callback(self.evt.MOTOR_OFF)
        elif data[0] == 0x07: # Fan Control
            pass
        elif data[0] == 0x08: 
            if not self.filament_sensor:
                self.callback(self.evt.Filament_Sensor_Enable)
                self.write("set.va1.val=1")
                self.write("st_fil=1")
                self.filament_sensor = True
            else:
                self.callback(self.evt.Filament_Sensor_Disable)
                self.write("set.va1.val=0")
                self.write("st_fil=0")
                self.filament_sensor = False
        elif data[0] == 0x09: # 
            self.write("page pretemp")
            self.write("params.nozzle_target.txt=\"%d\"" % self.printer.hotend_target)
            self.write("params.bed_target.txt=\"%d\"" % self.printer.bed_target)
        elif data[0] == 0x0a:
            self.write("page prefilament")
            self.write("prefilament.filamentlength.txt=\"%d\"" % self.load_len)
            self.write("prefilament.filamentspeed.txt=\"%d\"" % self.feedrate_e)
        elif data[0] == 0x0b:
            self.write("page set")
        elif data[0] == 0x0c:
            self.write("page warn_rdlevel")
        elif data[0] == 0x0d: # Advanced Settings
            self.write("multiset.plrbutton.val=1") #TODO recovery enabled?
            #else self.write("multiset.plrbutton.val=1")
            self.write("page multiset")

        else:
            print("_SettingScreen: Not recognised %d" % data[0])

        return
    
    def _SettingBack(self, data):
        print(f"_SettingBack data: {data}")  # Asegura que llega
        if data[0] == 0x01:
            if self.probe_mode:
                self.probe_mode = False
                self.callback(self.evt.PROBE_BACK)
        elif data[0] == 0x02:
            print("Emergency stop triggered from settingBack")
            self.callback(self.evt.EMERGENCY_STOP)
        else:
            print("_SettingBack: Not recognised %d" % data[0])
    
    def _BedLevelFun(self, data):
        if data[0] == 0x02 or data[0] == 0x03: # z_offset Up / Down
            offset = self.printer.z_offset
            unit = self.z_offset_unit
            if data[0] == 0x03:
                unit = - self.z_offset_unit
            
            if self.probe_mode:
                z_pos = self.printer.z_pos + unit
                print("Probe: z_pos %d" % z_pos)
                self.write("params.z_offset.val=%d" % (int)(z_pos * 100))
                #self.write("adjustzoffset.z_offset.val=%d" % (int)(self.printer.z_pos * 100))
                self.callback(self.evt.PROBE, unit)
            else:
                offset += unit
                #self.write("params.z_offset.val=%d" % (int)(offset * 100))
                self.write("adjustzoffset.z_offset.val=%d" % (int)(offset * 100))
                self.callback(self.evt.Z_OFFSET, offset)
                self.printer.z_offset = offset
        elif data[0] == 0x04:
            self.z_offset_unit = 0.005
            self.write("adjustzoffset.zoffset_value.val=1")
        elif data[0] == 0x05:
            self.z_offset_unit = 0.05
            self.write("adjustzoffset.zoffset_value.val=2")
        elif data[0] == 0x06:
            self.z_offset_unit = 1
            self.write("adjustzoffset.zoffset_value.val=3")
        elif data[0] == 0x07: # LED 2 TODO: Where is LED2??
            print("Toggle led2!!????")
        elif data[0] == 0x08: # Light control
            if self.light == True:
                self.light = False
                self.write("status_led2=0")
                self.callback(self.evt.LIGHT, 0)
            else:
                self.light = True
                self.write("status_led2=1")
                self.callback(self.evt.LIGHT, 1)
        elif data[0] == 0x09: # Bed mesh leveling
            # Wait for heaters?
            self.callback(self.evt.PROBE_COMPLETE)
            self.write("page levelmenu_z")
            self.write("levelmenu_z.tm0.en=0")
            self.write("levelmenu_z.tm0.en=0")
            #self.write("page warn_zoffset")

        elif data[0] == 0x0a:
            #status = self.callback(self.evt.PRINT_STATUS)
            self.write("printpause.printspeed.txt=\"%d\"" % self.printer.feedrate)
            self.write("printpause.fanspeed.txt=\"%d\"" % self.printer.fan)
            self.write("printpause.zvalue.val=%d" % (int)(self.printer.z_pos*10))
            self.write("printpause.printtime.txt=\"%d h %d min\"" % (self.printer.remaining/3600,(self.printer.remaining % 3600)/60))
            self.write("printpause.printprocess.val=%d" % self.printer.percent)
            self.write("printpause.printvalue.txt=\"%d\"" % self.printer.percent)

        elif data[0] == 0x0b:
            pass # Screen requesting nozzle and bed temp
        elif data[0] == 0x0c:
            pass
            #self.write(b'tm0.en=0')
            #self.write(b'va0.val=0')
            #self.write(b'tm1.en=1')
            #self.write(b'main.va0.val=1') #Plus:2 Pro:1 Max:3
        elif data[0] == 0x16:
            self.write("main.va0.val=1")
            self.write("printpause.t0.txt=\"%s\"" % self.printer.file_name)
            #status = self.callback(self.evt.PRINT_STATUS)
            self.write("printpause.printprocess.val=%d" % self.printer.percent)
            self.write("printpause.printvalue.txt=\"%d\"" % self.printer.percent)
        else:
            print("_BedLevelFun: Data not recognised %d" % data[0])
    
    def _AxisPageSelect(self, data):
        if data[0] == 0x04: #Home all
            self.callback(self.evt.HOME, 'X Y Z')
        elif data[0] == 0x05: #Home X
            self.callback(self.evt.HOME, 'X')
        elif data[0] == 0x06: #Home Y
            self.callback(self.evt.HOME, 'Y')
        elif data[0] == 0x07: #Home Z
            self.callback(self.evt.HOME, 'Z')
        else:
            print("_AxisPageSelect: Data not recognised %d" % data[0])
    
    def _Xaxismove(self, data):
        if data[0] == 0x01: # X+
            self.callback(self.evt.MOVE_X, self.move_unit)
        elif data[0] == 0x02: # X-
            self.callback(self.evt.MOVE_X, -self.move_unit)
        else:
            print("_Xaxismove: Data not recognised %d" % data[0])
    
    def _Yaxismove(self, data):         
        if data[0] == 0x01: # Y+
            self.callback(self.evt.MOVE_Y, self.move_unit)
        elif data[0] == 0x02: # Y-
            self.callback(self.evt.MOVE_Y, -self.move_unit)
        else:
            print("_Yaxismove: Data not recognised %d" % data[0])
    
    def _Zaxismove(self, data):
        if data[0] == 0x01: # Z+
            self.callback(self.evt.MOVE_Z, self.move_unit)
        elif data[0] == 0x02: # Z-
            self.callback(self.evt.MOVE_Z, -self.move_unit)
        else:
            print("_Zaxismove: Data not recognised %d" % data[0])
    
    def _SelectExtruder(self, data):    
        print("_SelectExtruder: Not recognised %d" % data[0])
    
    def _Heater0LoadEnter(self, data):
        load_len = ((data[0] & 0x00FF) << 8) | ((data[0] & 0xFF00) >> 8)
        self.load_len = load_len
        print(load_len)

    def _Heater1LoadEnter(self, data):  
        feedrate_e = ((data[0] & 0x00FF) << 8) | ((data[0] & 0xFF00) >> 8)
        self.feedrate_e = feedrate_e
        print(feedrate_e)
    
    def _FilamentLoad(self, data):
        if data[0] == 0x01 or data[0] == 0x02: # Load / Unload 
            if self.printer.state == 'printing':
                self.write("page warn1_filament")
            else:
                if data[0] == 0x01:
                    self.callback(self.evt.MOVE_E, [-self.load_len, self.feedrate_e])
                else:
                    self.callback(self.evt.MOVE_E, [self.load_len, self.feedrate_e])
        elif data[0] == 0x05: # Temp warning Confirm
            pass
        elif data[0] == 0x06: # Temp warning Cancel
            pass

        elif data[0] == 0x0a: # Back
            self.write("page main")
        else:   
            print("_FilamentLoad: Not recognised %d" % data[0])
    
    def _SelectLanguage(self, data):    
        print("_SelectLanguage: Not recognised %d" % data[0])
    
    def _FilamentCheck(self, data):     
        print("_FilamentCheck: Not recognised %d" % data[0])
    
    def _PowerContinuePrint(self, data):
        if data[0] in (0x01, 0x02) and self.confirm_action == self.evt.PLR_RESUME:
            self._PrintFile([0x01 if data[0] == 0x01 else 0x0A])  # same as Confirm/Cancel
        else:  # 0x03 = power-loss switch in Advanced settings (always on here)
            print("_PowerContinuePrint: Not recognised %d" % data[0])
    
    def _PrintSelectMode(self, data):   
        print("_PrintSelectMode: Not recognised %d" % data[0])
    
    def _XhotendOffset(self, data):     
        print("_XhotendOffset: Not recognised %d" % data[0])
    
    def _YhotendOffset(self, data):     
        print("_YhotendOffset: Not recognised %d" % data[0])
    
    def _ZhotendOffset(self, data):     
        print("_ZhotendOffset: Not recognised %d" % data[0])
    
    def _StoreMemory(self, data):       
        print("_StoreMemory: Not recognised %d" % data[0])
    
    def ask_confirm(self, action, text):
        # Reuses the "print this file?" page (no new page in the TFT without its .HMI):
        # Confirm sends 0x2198 01 -> callback(action), Cancel sends 0x2198 0A
        self.confirm_action = action
        self.write("askprint.t1.txt=\"¿Confirmar?\"")
        self.write("askprint.t0.txt=\"%s\"" % text.replace('"', "'")[:60])
        self.write("askprint.cp0.close()")
        self.write("askprint.cp0.aph=0")
        self.write("page askprint")

    def ask_plr(self, file_name):
        # The screen's own power-loss page (continueprint in Elegoo's LCD_program.HMI):
        # "Do you want to resume the job?", t0 = file name, Confirm/Cancel send 0x105F 01/02
        self.confirm_action = self.evt.PLR_RESUME
        name = file_name.replace('"', "'")
        self.write("printpause.t0.txt=\"%s\"" % name)
        sent = monotonic()
        self.write("page continueprint")
        sleep(0.3)  # the screen answers an unknown page within a few ms
        err = self.lcd_error
        if err and err[1] >= sent and err[0] in (0x03, 0x1A):
            print("PLR: this TFT has no 'continueprint' page, using askprint")
            self.ask_confirm(self.evt.PLR_RESUME, name)
            return
        self.write("continueprint.t0.txt=\"%s\"" % name)  # local field: only after the page change

    def plr_done(self, resumed):
        # Decidido fuera de la pantalla (Telegram, Mainsail): quitar la pregunta del corte de luz
        self.confirm_action = None
        if resumed:
            self.write("printpause.printvalue.txt=\"0\"")
            self.write("printpause.printprocess.val=0")
            self.write("page printpause")
        else:
            self.write("page main")

    def _PrintFile(self, data):
        if self.confirm_action and data[0] in (0x01, 0x0A):
            action, self.confirm_action = self.confirm_action, None
            if data[0] == 0x01:
                if action == self.evt.PLR_RESUME:
                    self.write("printpause.printvalue.txt=\"0\"")
                    self.write("printpause.printprocess.val=0")
                    self.write("page printpause")
                else:
                    self.write("page main")
                self.callback(action)
            else:
                self.write("page main")
                if action == self.evt.PLR_RESUME:
                    self.callback(self.evt.PLR_DISCARD)
            return
        if data[0] == 0x01:
            self.write("file%d.t%d.pco=65504" % ((self.selected_file / 5) + 1, self.selected_file))
            #self.write("params.z_offset.val=%d" % 0)
            self.write("printpause.printvalue.txt=\"0\"")
            self.write("printpause.printprocess.val=0")
            self.write("params.z_offset.val=%d" % (int)(self.printer.z_offset * 100))
            self.write("page printpause")
            self.write("restFlag2=1")
            #self.write("printpause.cp0.close()")
            #self.write("printpause.cp0.aph=0")
            #self.write("printpause.va0.txt=\"\"")
            #self.write("printpause.va1.txt=\"\"")
            self.callback(self.evt.PRINT_START, self.selected_file)

        elif data[0] == 0x0A:
            if self.askprint:
                self.askprint = False
                self.write("page file1")
            else:
                self.write("page main")
            
        else:
            print("_PrintFile: Not recognised %d" % data[0])
    
    def _SelectFile(self, data):
        print(self.files)
        if self.files and data[0] <= len(self.files):
            entry = self.entries[data[0] - 1]
            if entry['dir']:
                self.cwd = entry['path']
                self._show_dir()
                return
            self.confirm_action = None  # a pending dialog left with a page change must not hijack this print
            self.selected_file = (data[0] - 1)
            self.write("askprint.t0.txt=\"%s\"" % entry['name'].replace('"', "'"))
            self.write("askprint.t1.txt=\"¿Imprimir este modelo?\"")
            self.write("printpause.t0.txt=\"%s\"" % entry['name'].replace('"', "'"))
            self.callback(self.evt.FILE_INFO)
            self.write("askprint.cp0.close()")
            self.write("askprint.cp0.aph=0")
            self.write("page askprint")
            self.callback(self.evt.THUMBNAIL)
            self.askprint = True
        else:
            print("_SelectFile: Data not recognised %d" % data[0])

    
    def _ChangePage(self, data):        
        print("_ChangePage: Not recognised %d" % data[0])
    
    def _SetPreNozzleTemp(self, data):
        material = self.preset_index
        if data[0] == 0x01:
            self.preset_temp[material] += self.temp_unit
        elif data[0] == 0x02:
            self.preset_temp[material] -= self.temp_unit
        self.write("tempsetvalue.nozzletemp.val=%d" % self.preset_temp[material])
    
    def _SetPreBedTemp(self, data):
        material = self.preset_index
        if data[0] == 0x01:
            self.preset_bed_temp[material] += self.temp_unit
        elif data[0] == 0x02:
            self.preset_bed_temp[material] -= self.temp_unit
        material = self.preset_index
        self.write("tempsetvalue.bedtemp.val=%d" % self.preset_bed_temp[material])
    
    def _HardwareTest(self, data):
        if data[0] == 0x0f: # Hardware test page
            pass #Always requested on main page load, ignore
        else:
            print ("_HardwareTest: Not implemented: 0x%x" % data[0])
    
    def _Err_Control(self, data):       
        print("_Err_Control: Not recognised %d" % data[0])

    def screw_alert_4(self,screw_list:list[str]):
        self.write("nextpages=69")
        self.write("page screw_alert")
        self.write("screw_alert.p0.pic=167")  # dibujo de la cama de 4 tornillos (imagen del TFT Tortillery)
        self.write(f'screw_alert.t1.txt="(base)"')
        self.write(f'screw_alert.t2.txt="{screw_list[0]}"')
        self.write(f'screw_alert.t3.txt=""')
        self.write(f'screw_alert.t4.txt=""')
        self.write(f'screw_alert.t5.txt="{screw_list[2]}"')
        self.write(f'screw_alert.t6.txt="{screw_list[1]}"')


    def screw_alert_6(self,screw_list:list[str]):
        self.write("nextpages=69")
        self.write("page screw_alert")
        self.write("screw_alert.p0.pic=166")  # dibujo de la cama de 6 tornillos
        self.write(f'screw_alert.t1.txt="(base)"')
        self.write(f'screw_alert.t2.txt="{screw_list[0]}"')
        self.write(f'screw_alert.t3.txt="{screw_list[1]}"')
        self.write(f'screw_alert.t4.txt="{screw_list[2]}"')
        self.write(f'screw_alert.t5.txt="{screw_list[3]}"')
        self.write(f'screw_alert.t6.txt="{screw_list[4]}"')

if __name__ == "__main__":
    lcd = LCD("/dev/ttyUSB0", baud=115200)
    lcd.start()

    lcd.ser.write(b'page boot')
    lcd.ser.write(bytearray([0xFF, 0xFF, 0xFF]))

    lcd.ser.write(b'com_star')
    lcd.ser.write(bytearray([0xFF, 0xFF, 0xFF]))

    lcd.ser.write(b'main.va0.val=1')
    lcd.ser.write(bytearray([0xFF, 0xFF, 0xFF]))
    
    sleep(1)

    lcd.ser.write(b'page main')
    lcd.ser.write(bytearray([0xFF, 0xFF, 0xFF]))
    lcd.ser.write(b'params.nozzletemp.txt=\"%d / %d\"' % (23, 0))
    lcd.ser.write(bytearray([0xFF, 0xFF, 0xFF]))

    lcd.ser.write(b'params.bedtemp.txt=\"%d / %d\"' % (24, 0))
    lcd.ser.write(bytearray([0xFF, 0xFF, 0xFF]))
    
    lcd.write("set.va1.val=1")
    # Status LED
    #lcd.ser.write(b'status_led1=0')
    #lcd.ser.write(bytearray([0xFF, 0xFF, 0xFF]))