# Tortillery+ frente a la Tortillery original

La base es la imagen **Tortillery** de [CiareCw455/Tortillery](https://github.com/CiareCw455/Tortillery) (Armbian en
la eMMC de la placa MKS, Klipper, Moonraker, Mainsail, KlipperLCD y la pantalla Tortillery v0.5.2), de donde salió la
idea y el `.HMI` de la pantalla. Esta es la lista de todo lo que Tortillery+ cambia o añade, por temas.

## Instalación e imagen
- **Imagen de la eMMC lista para grabar**: lleva todo instalado. El primer arranque crea la
  identidad propia de cada impresora: claves SSH, machine-id y `MCU_ID.cfg`. Antes todas las impresoras compartían claves
  SSH y podían recibir la misma IP. También graba la placa y la pantalla sin USB.
- **Asistente en la pantalla**: modelo (X4 Pro o X4 Plus), idioma y bienvenida con WiFi y nivelación. Sin SSH.
- `install.sh PRO|PLUS`: instala o actualiza conservando la calibración (bloque `SAVE_CONFIG`). Hace copia `.orig` de
  cada archivo que reemplaza.
- `tortillery-seal.sh`: prepara una impresora para copiarla como imagen. Borra redes, claves, historial, tokens, API keys y
  copias de la config.
- Primer arranque robusto: reintenta hasta que la placa y la pantalla constan grabadas.

## Actualizaciones
- **USB de actualización**:
  - Ya no reflashea en cada arranque: compara el sha256 con el último flasheo correcto.
  - Nunca actualiza imprimiendo ni en pausa (antes paraba Klipper en mitad de la impresión).
  - Klipper y la pantalla siempre vuelven a arrancar.
  - `mcu_update.sh` devuelve el resultado real del flasheo.
- `SHA256SUMS`: no se flashea una copia corrupta.
- **USB firmado** (ed25519, `SHA256SUMS.sig`):
  - Si la firma está mal, no se flashea nada.
  - Si el USB no lleva firma, se acepta y se apunta en el log.
  - La clave privada solo está en el PC (`%USERPROFILE%\.tortillery\firma_privada.pem`).
- **Actualizar Tortillery+ desde Mainsail** (`[update_manager tortillery]`): usa el repo público y solo versiones
  etiquetadas **y firmadas** (`git verify-tag`). Al cambiar de versión, `tortillery-update.path` instala la versión
  firmada desde una copia propia de root, nunca desde la carpeta de `mks`, con el modelo de la impresora. Nunca
  mientras imprime.
- Klipper, Moonraker y Mainsail, desde Mainsail, en canal `stable` (la imagen traía `dev`).
- Kernel y arranque de la placa retenidos (`apt-mark hold`): una actualización de Armbian podía dejarla sin arrancar.
- Desactivados `unattended-upgrades` y `apt-daily` (actualizaban en mitad de una impresión), `openvpn`, `rpcbind` y `vnstat`.

## Seguridad de la máquina
- `min_temp: 0` en el extrusor y la cama (detecta un termistor suelto) y `min_extrude_temp: 160`.
- `[verify_heater heater_bed]` más estricto: 2 °C en 120 s, en vez de 1 °C en 300 s.
- `idle_timeout` de 30 min (antes 10 h con los calentadores encendidos).
- **Pausa larga**:
  - A los 30 min se apaga el hotend.
  - **Una hora después, la cama**.
  - `RESUME` vuelve a calentar las dos.
- `CANCEL_PRINT`:
  - Apaga primero los calentadores.
  - Solo retrae en caliente.
  - Ya no usa `G28 X`.
- Comprobaciones de seguridad antes de reanudar tras un corte de luz (de JeroMod).
- Root ya no entra por SSH con contraseña (se usa `mks` + sudo). KlipperLCD ya no lleva una clave API fija de otra máquina.

## Fiabilidad
- **Recuperación tras corte de luz**:
  - Guarda el estado cada 5 s con fsync.
  - Al arrancar ofrece reanudar desde la página propia de la pantalla.
  - Restaura las aceleraciones y el sensor de filamento.
- **Watchdog**:
  - KlipperLCD avisa a systemd mientras refresca la pantalla; si se cuelga o se muere, se reinicia sola.
  - La placa se reinicia sola si el sistema se cuelga del todo (watchdog de hardware de systemd).
- Logs en RAM (`armbian-ramlog`, ya activo en la imagen): menos desgaste de la eMMC.
- **Copia automática de la config** cada vez que cambia `printer.cfg` (p. ej. tras `SAVE_CONFIG`). Se guarda en
  `printer_data/backup` y en el USB si está puesto, y se quedan las 5 últimas de cada sitio. Además está
  `COPIA_SEGURIDAD_USB` a mano.
- La pantalla ya no se congela con Klipper en error (por ejemplo, sin `printer.cfg`).
- **USB**:
  - Ahora se monta en `gcodes/USB/` con un único script; antes eran tres y a veces el USB no aparecía.
  - Montan también los USB en ext4.
  - Si se saca el USB imprimiendo, la impresora pausa; al volver a meterlo, se reanuda.
- WiFi por USB sin borrar las demás redes. Antes, una contraseña mal escrita dejaba la impresora sin red.
- **Rendimiento**:
  - CPU en `performance`.
  - Klipper con prioridad (`Nice=-10`).

## Klipper y macros
- `PRINT_START BED= EXTRUDER=`:
  - Hace home, malla adaptativa y purga.
  - Calienta la boquilla fuera de la cama.
  - Sin parámetros funciona como antes.
- `SMART_PARK` y `LINE_PURGE` (estilo KAMP). Moonraker con `enable_object_processing` (`EXCLUDE_OBJECT` con cualquier
  laminador).
- `[firmware_retraction]` (G10/G11), `[respond]`, `M300` con tono, duración y repeticiones.
- Corregido `idle_timeout` en pausa (`pause_resume.is_paused` nunca se activaba).
- **Calibración guiada (2.0)**:
  - Input shaper X+Y con la aceleración máxima recomendada, guardada y aplicada al arrancar. `M204` no la supera.
  - Patrón de pressure advance.
  - Extrusor (100 mm).
  - `[axis_twist_compensation]`.
  - Valores en `tortillery_vars.cfg`.
- Utilidades:
  - `COPIA_SEGURIDAD_USB`.
  - `MANTENIMIENTO_ESTADO` / `MANTENIMIENTO_HECHO`, con aviso cada 200 h de impresión.

## Pantalla (TFT Tortillery+, sobre la base Tortillery v0.5.2)
- Gris medio con iconos propios y la cabecera del menú principal corregida.
- **WiFi desde la pantalla**: buscar, conectar y "Olvidar esta red".
- Explorador por carpetas:
  - USB incluido; carpetas primero y archivos más nuevos arriba.
  - Iconos de carpeta, archivo y USB.
  - Tiempo y filamento antes de imprimir.
- Tiempo restante real (estimación del laminador) y contador de capas.
- Errores de Klipper en español con el motivo y botón de reiniciar el firmware. Historial de los 5 últimos.
- **Páginas nuevas**:
  - Elegir material al cargar o descargar.
  - Luz LED, ventilador de capa, mallas (cargar, guardar, borrar, medir) y mantenimiento.
  - Calibración (input shaper, pressure advance, extrusor, torsión).
  - Vigilancia IA.
  - Utilidades en dos páginas.
  - QR de Mainsail y de Telegram.
- Barra de estado en el menú principal: WiFi, cámara, IA y Telegram.
- Aviso del cambio de filamento `M600`, con carga y descarga durante la pausa.
- Lista de macros limpia: se ocultan las que dan error lanzadas sin parámetros.
- Versión de Tortillery+ en la página de información.

## Cámara, IA y avisos
- **Cámara USB/USB-C automática** (cualquier webcam UVC) y `[webcam]` en Mainsail sin configurar nada.
- **Vigilancia con IA**:
  - Detecta espagueti, pieza despegada y atasco.
  - Proveedores: Anthropic, OpenAI, Google, NVIDIA, Ollama o compatible. Se configura en `tortillery_ai.cfg` desde
    Mainsail.
  - Pausa y avisa con foto.
  - Revisa más a menudo en los 10 primeros minutos, y la primera capa con especial cuidado.
  - No paga fotos iguales.
  - `modelo_confirmar` (un segundo modelo confirma antes de pausar).
  - Avisa si la vigilancia deja de funcionar.
- **Telegram**:
  - Se configura en `telegram.cfg` desde Mainsail.
  - Avisos de inicio, cancelación y error.
  - **Pausa con foto y botones** (Reanudar / Cancelar / Otra foto).
  - **Fin con foto**, **vídeo del timelapse** y **aviso de mantenimiento**.
  - Órdenes: `/foto`, `/estado`, `/reanudar`, `/cancelar`.
  - Solo obedece a tu chat.
- **Extras opcionales** (`extras.sh`): Tailscale, OctoEverywhere, Moonraker-Timelapse, Shake&Tune y **Mobileraker**
  (avisos push en el móvil).

## Créditos
- [CiareCw455/Tortillery](https://github.com/CiareCw455/Tortillery): Tortillery original, la idea y el `.HMI` de la pantalla.
- [joakimtoe/KlipperLCD](https://github.com/joakimtoe/KlipperLCD) (Apache-2.0).
- JeroMod y Tortillery 2.0 (@UrtziDV): ideas incorporadas.
