# Tortillery+ frente a la Tortillery original

La base es la imagen **Tortillery** de [CiareCw455/Tortillery](https://github.com/CiareCw455/Tortillery) (Armbian en
la eMMC de la placa MKS, Klipper, Moonraker, Mainsail, KlipperLCD y la pantalla Tortillery v0.5.2), de donde salió la
idea y el `.HMI` de la pantalla. Esta es la lista de todo lo que Tortillery+ cambia o añade, por temas.

## Instalación e imagen
- **Imagen de la eMMC lista para grabar**: lleva todo instalado. El primer arranque crea la
  identidad propia de cada impresora: claves SSH, machine-id y `MCU_ID.cfg`. Antes todas las impresoras compartían claves
  SSH y podían recibir la misma IP. También graba la placa y la pantalla sin USB.
- **Asistente en la pantalla**: modelo (X4 Pro o X4 Plus), idioma y bienvenida con WiFi y nivelación. Sin SSH.
  Al elegir el modelo la impresora se reinicia sola (1.1.5): antes la pantalla se quedaba en "falta printer.cfg"
  hasta apagarla y encenderla.
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
- Klipper, Moonraker y Mainsail, desde Mainsail, en canal `stable` (la imagen traía `dev`). La imagen 1.1.3 trae
  Klipper 0.14.0, Moonraker 0.11.0 y Mainsail 2.19.0 (el firmware de la placa no hace falta cambiarlo).
- **Tiempo de impresión exacto (1.1.5)**: Klipper Estimator (Moonraker `[analysis]`) recalcula el tiempo de cada G-code
  subido con los límites reales de la impresora.
- Mainsail busca versiones nuevas de Tortillery+ cada día (antes cada 7 y solo de madrugada).
- Mainsail ya no marca Klipper con aviso por los extras propios (`plr.py`, `gcode_shell_command.py`): git los ignora.
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
- **Sonda más precisa (1.1.5)**: `speed: 3`, `lift_speed: 12`, 3 toques y `samples_result: median` (antes 5 o 10 mm/s,
  2 toques y la media). Según las medidas de [grumat](https://github.com/grumat/artillery-x4-pro_config/wiki/The-Inductive-Z%E2%80%90Probe), con la cama y la boquilla calientes la sonda
  varía menos de la mitad.
- **Ventilador de la placa (1.1.5)**: `FAN2` (PC9) pasa de `heater_fan` a `[controller_fan]`. Antes solo giraba con la
  boquilla caliente; ahora gira al 80 % con cualquier motor o calentador encendido y 3 minutos más al 70 %. Idea de
  [grumat](https://github.com/grumat/artillery-x4-pro_config/wiki/Smarter-Mainboard-Fan-Controller).
- **Calibración guiada (2.0)**:
  - Input shaper X+Y con la aceleración máxima recomendada, guardada y aplicada al arrancar. `M204` no la supera.
  - Patrón de pressure advance.
  - Extrusor (100 mm).
  - `[axis_twist_compensation]`.
  - **Homing exacto de X/Y (1.1)**: `PRUEBA_HOMING` mide en mm cuánto varía el homing sin finales de carrera y
    `FIJAR_HOMING` guarda la fase de los motores (`endstop_phase`) para que caiga siempre en el mismo micropaso. Así
    la recuperación tras un corte de luz vuelve al punto exacto.
  - **Input shaper bien medido (1.1.5)**: la prueba de vibraciones cortaba en 70 Hz y la resonancia de X de la X4 está
    en unos 100 Hz; ahora mide de 5 a 135 Hz desde el centro de la cama.
  - **Pressure advance por material (1.1.5)**: el patrón guarda el valor de cada material y `PRINT_START MATERIAL=...`
    aplica el suyo (lo que hacen Bambu o Creality con su calibración de flujo, sin sensor). También al reanudar tras
    un corte de luz.
  - **Escuadra de X/Y (1.1.5)**: pieza de 100 mm ya preparada y `CALIBRAR_ESCUADRA` (`skew_correction`).
  - **Patrones de calibración (1.1.5)**: purgan delante del patrón (no en el borde de la cama, donde se podía salir) y
    al acabar el cabezal se aparta y la cama sale adelante.
  - **Parada de emergencia en la pantalla de impresión (1.1.5)**: botón rojo arriba a la izquierda, con confirmación.
  - **Sin filamento (1.1.5)**: aviso en la pantalla (Aceptar aparta el cabezal y abre Sacar/Meter 10-50-100 mm y
    Reanudar) y en Telegram con Enfriar / Reanudar / Cancelar. Las temperaturas ya no bajan solas en esa pausa y no
    reanuda sin filamento en el sensor. Antes paraba sin decir nada, con el cabezal encima de la pieza.
  - **No imprime sin filamento (1.1.5)**: con el sensor activo y sin filamento, `PRINT_START` para con un aviso en
    vez de calentar e imprimir al aire.
  - **M600 a la temperatura de la impresión (1.1.5)**: el cambio de filamento abre la misma página Sacar/Meter que
    Sin filamento (la de Filamento calentaba a la temperatura del material elegido).
  - **Tus ajustes no se pierden (1.1.5)**: `printer.cfg` incluye al final `config/ajustes/*.cfg`, que las
    actualizaciones no tocan; lo que pongas ahí gana sobre el resto (guía en `printer/README.md`).
  - **La pantalla ya no se queda colgada (1.1.5)**: las órdenes que manda (sacar filamento, temperaturas...) iban
    por el mismo bucle que la actualiza y sin límite de tiempo; una orden larga o que no contestaba la dejaba
    congelada y lo que se pulsaba después no llegaba a Klipper. Ahora van aparte y en orden.
  - **Tras un corte de luz no reanuda sin filamento (1.1.5)**: si el sensor no detecta filamento, _Continuar_ avisa en
    vez de imprimir al aire.
  - **Corte de luz durante una pausa (1.1.5)**: la pausa sube la boquilla 20 mm y la recuperación no lo sabía: al
    volver la luz reanudaba 20 mm por encima de la pieza, imprimiendo al aire. Ahora guarda la altura real también
    en pausa.
  - **Menú de órdenes en Telegram (1.1.5)**: el bot muestra sus órdenes en el menú **/** (la impresora las registra
    al arrancar) y `/ayuda` las explica. Guía de Telegram en `telegram/README.md`.
  - **Nombre en la red (1.1.5)**: `http://tortilleryplus.local` (antes había que buscar la IP).
  - **Purga sin etiquetas de objetos (1.1.5)**: la de Artillery, 8 mm más adentro; en el borde se podía salir de la cama.
  - **Homing de X/Y fiable (1.1.5)**: a 20 mm/s y con la sensibilidad ajustada: ya no golpea el tope ni se para antes, y `PRUEBA_HOMING` baja de varios mm a 0,2 mm.
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
  - **Luz LED (1.1)**: 6 colores, color a medida (R, G, B) y modos que siguen al hotend o a la cama. La elección se
    guarda (`LUZ_LED`, `tortillery_vars.cfg`) y se mantiene al imprimir y al reiniciar; antes cada impresión la volvía
    a poner en blanco.
  - **Malla automática (1.1)**: eliges 5x5, 6x6, 7x7 o 9x9 puntos antes de medir.
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
  - Detecta espagueti, pieza despegada, atasco, bola en la boquilla y capa desplazada.
  - Proveedores: Anthropic, OpenAI, Google, NVIDIA, Ollama o compatible. Se configura en `tortillery_ai.cfg` desde
    Mainsail.
  - Pausa y avisa con foto.
  - Revisa más a menudo en los 10 primeros minutos, y la primera capa con especial cuidado.
  - No paga fotos iguales.
  - `modelo_confirmar` (un segundo modelo confirma antes de pausar).
  - Avisa si la vigilancia deja de funcionar.
  - **Bola en la boquilla (1.1.5)**: detecta el plástico que se acumula alrededor de la boquilla antes de que envuelva
    el hotend.
  - **Capa desplazada (1.1.5)**: también avisa si las capas de arriba se han movido de lado respecto a las de abajo.
  - **Mira la pieza de cerca (1.1.5)**: cuando localiza la pieza, solo envía esa zona ampliada (los fallos pequeños se
    pierden en la foto entera).
  - **Marcar la cámara (1.1.5)**: web `http://tortilleryplus.local/ia` (4 fotos en 4 posiciones, tocas la boquilla y
    las esquinas de la cama). La IA sabe dónde está cada pieza en la foto aunque se muevan la cama y el cabezal, con
    la cámara en cualquier sitio, y la mira de cerca sin gastar consultas en buscarla.
  - **Fotos oscuras (1.1.5)**: si la foto sale oscura, enciende la luz del cabezal en blanco para hacerla y la deja
    como estaba; si aun así no se ve, no paga la consulta y avisa una vez por Telegram (de noche ningún modelo
    acierta).
  - **En vivo en Mainsail (1.1.5)**: cámara **ia** con la última foto revisada, la pieza (verde) y el fallo (rojo)
    marcados y el veredicto.
  - **Cualquier cámara (1.1)**: al empezar cada impresión la IA busca la cama en la foto y solo mira esa zona,
    ampliada. Compara cada foto con otra de hace unos minutos (pieza movida, espagueti que crece). Entiende el
    razonamiento de los modelos que piensan (`<think>`). Cada foto queda en el log. `--test foto.jpg` prueba con
    una foto y guarda en `ia_prueba.jpg` lo que ha visto la IA.
- **Telegram**:
  - Se configura en `telegram.cfg` desde Mainsail.
  - Avisos de inicio, cancelación y error.
  - **Pausa con foto y botones** (Reanudar / Cancelar / Otra foto).
  - **Fin con foto**, **vídeo del timelapse** y **aviso de mantenimiento**.
  - **Corte de luz (1.1)**: al volver la corriente avisa de a qué hora se fue y volvió, por dónde iba la impresión y
    deja **Continuar** o **Descartar** desde Telegram; la pregunta de la pantalla se quita sola. (Sin corriente la
    impresora no puede avisar en el momento del corte.)
  - Órdenes: `/foto`, `/estado`, `/reanudar`, `/cancelar`.
  - Solo obedece a tu chat.
- **Extras opcionales** (`extras.sh`): Tailscale, OctoEverywhere, Moonraker-Timelapse, Shake&Tune y **Mobileraker**
  (avisos push en el móvil).

## Próximos cambios
- **BLTouch (u otra sonda) en lugar de la sonda de serie**: hoy no se puede hacer desde `ajustes/`, porque un archivo
  incluido cambia opciones pero no borra secciones. Además, `[probe]` (la de serie, en PA8) y `[bltouch]` no pueden
  estar a la vez. El plan:
  - el usuario pone su `[bltouch]`, con los pines de su cableado, en `ajustes/bltouch.cfg`;
  - `tortillery-model.sh` ve ese archivo y quita el `[probe]` de serie al generar `printer.cfg`, así que sobrevive a
    las actualizaciones;
  - `[homing_override]` lee el Z-offset de `bltouch` si existe, y si no, de `probe`;
  - ejemplo comentado en `ejemplos/ajustes/` y explicación en la guía de [printer](../printer/README.md).

## Créditos
- [CiareCw455/Tortillery](https://github.com/CiareCw455/Tortillery): Tortillery original, la idea y el `.HMI` de la pantalla.
- [joakimtoe/KlipperLCD](https://github.com/joakimtoe/KlipperLCD) (Apache-2.0).
- JeroMod y Tortillery 2.0 (@UrtziDV): ideas incorporadas.
