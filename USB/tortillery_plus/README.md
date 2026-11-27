# Instalar Tortillery+ (X4 Pro / X4 Plus)

En la descarga (Google Drive, enlace en el README) hay:
- **`IMAGEN_EMMC/Tortillery+_<versión>.img`**: el sistema completo (Armbian, Klipper, Moonraker, Mainsail, KlipperLCD y
  Tortillery+ ya instalado). Se graba en la eMMC del ordenador de la placa, **no** en la MCU. El `.sha256` sirve para
  comprobar la descarga.
- **`USB/`**: el firmware de la pantalla (`800_480.tft`) y de la placa (`klipper.bin`) firmados, y la carpeta
  `tortillery_plus/`. Solo hace falta para pasar desde la Tortillery original o para actualizar la pantalla y la placa.
- **`LEEME.txt`**: este resumen.

## Instalación nueva (recomendada, sin USB ni SSH)
1. **balenaEtcher**: graba `Tortillery+_<versión>.img` en la eMMC y deja que verifique la escritura.
2. Pon la eMMC y **enciende la impresora**. El primer arranque tarda unos minutos y lo hace todo solo: graba la placa y la
   pantalla y crea la identidad propia de la impresora (claves SSH, machine-id, `MCU_ID.cfg`).
3. **En la pantalla**: elige el idioma y tu modelo (X4 Pro o X4 Plus). La impresora se reinicia sola una vez.
4. **Bienvenida**: conecta el WiFi y nivela la cama (también se puede luego desde Ajustes). Pulsa *Terminar*.

Mainsail queda en `http://tortilleryplus.local` o en `http://<IP>`; la IP sale en la bienvenida y en Ajustes. Por SSH: `ssh mks@<IP>` (root ya no entra por
SSH con contraseña). Telegram y la IA se activan después desde Mainsail (ver más abajo).

Si algo falla en el primer arranque, el log está en `/var/log/tortillery-firstboot.log`; el primer arranque se repite
hasta que la placa y la pantalla constan grabadas.

## Pasar de la Tortillery original a Tortillery+ (sin grabar la eMMC)
1. Copia **todo** lo de la carpeta `USB/` a la raíz de un USB en FAT32. Si quieres que se conecte al WiFi, renombra
   `wifi.cfg.ejemplo` a `wifi.cfg` y pon tu red (opcional: `telegram.cfg.ejemplo` → `telegram.cfg` con el token del bot).
2. Enciende la impresora con el USB puesto: los scripts de la Tortillery flashean la placa y la pantalla. Espera a que la
   pantalla vuelva a arrancar.
3. Por SSH (`ssh mks@<IP>`), con el USB todavía puesto:
   ```bash
   sudo bash ~/printer_data/gcodes/tortillery_plus/install.sh PRO    # o PLUS
   sudo reboot
   ```
   El instalador:
   - copia `artillery_X4_<MODELO>.cfg` → `printer.cfg` y `macros_X4_<MODELO>.cfg` → `macros.cfg`;
   - si ya había un `printer.cfg`, **conserva su calibración** (PID, Z-offset, mallas, input shaper del bloque
     `SAVE_CONFIG`) y guarda el anterior como `printer.cfg.orig`;
   - instala la pantalla nueva de KlipperLCD, la recuperación tras corte de luz, el actualizador USB, la cámara, la IA,
     Telegram y la actualización desde Mainsail.
4. Quita el USB (o déjalo: no vuelve a flashear lo que ya está grabado).

Tras el reinicio el USB aparece en la carpeta **`USB/`** de los G-codes (Mainsail y pantalla), y lo que subes por Mainsail se
guarda en la impresora. Si Klipper no arranca, la pantalla muestra la IP y el motivo.

## Actualizar
- **Tortillery+ (configs, macros, scripts, KlipperLCD)**: desde Mainsail, ver "Actualizar desde Mainsail" más abajo.
- **Pantalla y placa**: copia la carpeta `USB/` de la versión nueva a un USB en FAT32 y arranca con él. Solo se flashea lo
  que ha cambiado, nunca imprimiendo ni en pausa, y se comprueba la firma (ver "Firma del USB de actualización").

## Complementos opcionales (acceso remoto y timelapse)
Por SSH, solo los que quieras (se pueden repetir para actualizar). `~/tortillery` es la copia del repo que deja
`install.sh` cuando la impresora tiene internet; si no está, usa la ruta del USB (`~/printer_data/gcodes/USB/tortillery_plus/`):
```bash
sudo bash ~/tortillery/tortillery_plus/extras.sh tailscale     # Mainsail/SSH desde fuera de casa
bash ~/tortillery/tortillery_plus/extras.sh octoeverywhere     # SIN sudo: app, avisos y cámara remotos
sudo bash ~/tortillery/tortillery_plus/extras.sh timelapse     # vídeo de cada impresión (necesita cámara)
bash ~/tortillery/tortillery_plus/extras.sh mobileraker        # SIN sudo: avisos push en la app Mobileraker
```
- **Tailscale**: abre el enlace que imprime para iniciar sesión (o pasa una clave: `extras.sh tailscale tskey-...`).
  Añade `100.64.0.0/10` a `trusted_clients` de Moonraker para que Mainsail conecte por Tailscale.
- **OctoEverywhere**: su instalador muestra el enlace para vincular la impresora con tu cuenta.
- **Timelapse**: en el laminador, G-code "antes del cambio de capa": `TIMELAPSE_TAKE_FRAME`. Los vídeos salen en
  Mainsail > Timelapse. Sus macros van en `config/extras/`, que `printer.cfg` incluye: reinstalar Tortillery+ no las quita.
  Con Telegram activado, el vídeo te llega al bot al terminar de renderizarse (hasta 50 MB).
- **Mobileraker**: instala la app (Android/iOS), añade la impresora con `http://<IP>` y activa las notificaciones.

## Cámara USB / USB-C
Cualquier webcam UVC (las normales de PC; USB-C con adaptador si hace falta) funciona sin configurar: al arrancar o al
enchufarla, `tortillery-camera.sh` pone su id en `crowsnest.conf` y reinicia crowsnest. Mainsail la muestra como
"camara" (sección `[webcam camara]` de `moonraker.conf`). No valen las cámaras que solo dan H.264 o necesitan su app.
Comprobar: `ls /dev/v4l/by-id/` y `~/printer_data/logs/crowsnest.log`.

## Detección de fallos con IA (opcional)
Dos opciones, se pueden usar las dos:
- **Gadget de OctoEverywhere** (sin configurar nada, gratis): instala `extras.sh octoeverywhere` y activa Gadget en su web.
- **Tortillery IA** (`tortillery-ai.service`, ya instalado): en Mainsail > Máquina abre `tortillery_ai.cfg`, elige
  `proveedor` (anthropic, openai, google, nvidia, ollama u openai_compatible), pon `api_key`/`modelo`/`url` y guarda.
  Mientras imprime manda una foto cada `intervalo` s; con `confirmaciones` fotos seguidas con fallo (espagueti, pieza
  despegada, atasco, bola de plástico en la boquilla, capa desplazada) pausa, avisa por Telegram con la foto y lo apunta en Utilidades >
  Historial de errores.
  **En vivo en Mainsail**: en la cámara **ia** (selector de cámaras del panel) ves la última foto que ha mirado la IA, con
  la pieza en verde, el fallo en rojo y el veredicto arriba. Se actualiza en cada revisión. Para que las cajas salgan
  bien ajustadas, el modelo que mejor marca dónde están las cosas es Gemini (`proveedor = google`).
  Probar con la cámara mirando a la cama: `python3 /usr/local/bin/tortillery-ai.py --test` (deja en `config/ia_prueba.jpg`
  lo que ha visto, marcado).
  **Marcar la cámara** (recomendado): abre `http://tortilleryplus.local/ia` con la cama vacía. La impresora se coloca en
  4 posiciones (base, X, Y y Z movidos); en cada foto tocas la punta de la boquilla y las 4 esquinas de la cama
  (delante = lado de la pantalla; una esquina puede quedar fuera de la foto). Con eso sabe cómo se mueven la cama y el
  cabezal en la foto, sea cual sea el montaje de la cámara, y en cada revisión recorta justo las piezas (etiquetas de
  objetos del laminador) desde la cama hasta la altura impresa, sin consultas para buscarlas. Se guarda en
  `config/ia_marcas.json`; si mueves la cámara, vuelve a marcar (o bórralas desde la misma página). Sin marcas:
  Cuando localiza la pieza, solo envía esa zona ampliada (se ven mejor los fallos pequeños). Si la foto sale oscura
  enciende la luz del cabezal en blanco para hacerla; si aun así no se ve, no paga la consulta y avisa por Telegram:
  **pon luz sobre la cama**, de noche ningún modelo acierta.
  Log: `sudo journalctl -u tortillery-ai -f`. Cada foto es una petición de pago a tu proveedor (Ollama en tu PC: gratis).
  Los 10 primeros minutos mira cada 60 s (la primera capa); si la foto no ha cambiado no paga otra consulta;
  `modelo_confirmar` (opcional) es un segundo modelo que confirma antes de pausar. Si la IA deja de contestar, avisa.
  Estado en la pantalla: Utilidades > Más... > Vigilancia con IA, y en la barra de arriba del menú principal.
- **Obico autoalojado** (IA local gratis, en tu PC con Docker): alternativa sin proveedor de pago; ver su web.

## Telegram
Pon el token de tu bot (de @BotFather) en `telegram.cfg` desde Mainsail; antes mándale un mensaje al bot. Paso a paso,
con el ID del chat y todas las órdenes: [guía de Telegram](../telegram/README.md). Llegan los
avisos de inicio, cancelación y error; la **pausa** (la de la IA o cualquier otra) con foto y botones **Reanudar /
Cancelar / Otra foto**; el **fin** con foto; el vídeo del **timelapse** si está instalado; y el aviso de
**mantenimiento** (200 h) al terminar mientras toque. Al bot puedes
escribirle `/foto`, `/estado`, `/reanudar`, `/cancelar`, `/enfriar`, `/continuar`, `/descartar` y `/ayuda` (salen en
el menú **/** del bot; solo obedece a tu chat). Utilidades > Más... > QR de Telegram
abre el bot en el móvil.

**Sin filamento**: cuando el sensor se queda sin filamento la impresora se pausa (sube 20 mm) y **las temperaturas no
bajan** aunque pase el tiempo. En la pantalla sale *Sin filamento - Cargar filamento*: **Aceptar** lleva el cabezal a
la izquierda (la cama no se mueve) y abre *Cargar filamento*, con Sacar y Meter de 10, 50 y 100 mm y **Reanudar
impresión**. Por Telegram llega el aviso con foto y **Enfriar** (apaga solo la boquilla; la cama sigue para que la
pieza no se despegue, y al reanudar se vuelve a calentar), **Reanudar** y **Cancelar**. Sin filamento en el sensor no
reanuda (seguiría imprimiendo al aire).

**Corte de luz**: sin corriente la impresora no puede avisar en ese momento; al volver, si había una impresión a
medias, llega un aviso con la hora del corte y de la vuelta, por dónde iba (Z y % del archivo) y los botones
**Continuar / Descartar** (o `/continuar` y `/descartar`). Lo que elijas en Telegram quita la pregunta de la
pantalla, y al revés. Antes de continuar comprueba que la pieza sigue pegada a la cama.

## Malla de la cama y luz LED
- **Malla automática** (Nivelar > Malla automática, o Utilidades > Mallas > Medir nueva): elige los puntos por lado.
  5x5 es rápida, 6x6 la de siempre, 7x7 y 9x9 más precisas pero más lentas (9x9 son 81 puntos). Se guarda como
  `default` y Klipper se reinicia. La malla adaptativa de `PRINT_START` sigue usando la de `printer.cfg`.
- **Luz LED** (Utilidades > Luz LED): un color fijo, un color a medida (Rojo, Verde y Azul de 0 a 100 %), que siga a
  la temperatura del hotend o de la cama, o Automática (la de serie: sigue la temperatura al calentar y luego blanco).
  Se guarda en `tortillery_vars.cfg` y se mantiene al imprimir y al reiniciar. Desde Mainsail o el G-code:
  `LUZ_LED MODO=1 R=1 G=0.4 B=0` (color, de 0 a 1), `MODO=2` hotend, `MODO=3` cama, `MODO=0` automática.

## Calibración guiada (pantalla: Nivelar > Calibración)
- **Input shaper y aceleración**: mide X e Y con el acelerómetro del cabezal y enseña tipo, frecuencia y la aceleración
  máxima que recomienda; Guardar conserva el shaper (`SAVE_CONFIG`) y la aceleración. `M204` del laminador no la supera.
- **Pressure advance**: elige el material y la impresora imprime 21 líneas (lenta-rápida-lenta, PA de 0 a 0,10). Elige
  la de grosor más uniforme (la 1 es la de delante; marcas en 1, 6, 11, 16, 21) y Guardar. Se guarda **para ese
  material** (y como general): haz el patrón una vez con cada material que uses. Con `MATERIAL=` en `PRINT_START` (ver
  más abajo) cada impresión usa el suyo. A mano: `GUARDAR_PA MATERIAL=PETG VALOR=0.045`.
- **Extrusor (100 mm)**: marca el filamento a 120 mm de la entrada, elige material (calienta y empuja 100 mm), mide lo
  que queda hasta la marca y Guardar: corrige `rotation_distance`.
- **Torsión del eje X**: 3 puntos con papel, como el Z-Offset (la sonda va 17 mm a un lado de la boquilla).
PA, aceleración y `rotation_distance` se guardan en `config/tortillery_vars.cfg` y se aplican en cada arranque
(`config/calibracion.cfg`); para volver a lo de `printer.cfg`, borra la línea y reinicia el firmware.
Input shaper: la prueba mide de 5 a 135 Hz desde el centro de la cama. Hasta la 1.1 cortaba en 70 Hz y no veía la
resonancia de X (unos 100 Hz en la X4): **repite el input shaper** tras actualizar.
Gráficas de correas y vibraciones (opcional): `bash ~/tortillery/tortillery_plus/extras.sh shaketune`
(sin sudo) y en Mainsail `COMPARE_BELTS_RESPONSES` / `AXES_SHAPER_CALIBRATION`.

## Escuadra de X/Y (piezas cuadradas de verdad)
Si X e Y no forman exactamente 90°, los cuadrados salen romboides y las piezas que encajan no encajan.
1. Imprime `Tortillery/escuadra_PLA.gcode` (está en la lista de archivos; PLA, unos 10 min): un marco de 100 mm con un
   cuadradito macizo en la esquina **A**.
2. Con un calibre, por fuera: **AC** = diagonal desde A, **BD** = la otra diagonal, **AD** = el lado que va de A a la
   esquina de su derecha (lado delantero).
3. En la consola de Mainsail: `CALIBRAR_ESCUADRA AC=141.2 BD=141.6 AD=100.1` (tus medidas). Guarda y reinicia Klipper.
Se aplica en cada impresión que use `PRINT_START` con temperaturas (después de la purga) y al reanudar tras un corte.
Para quitarla: `QUITAR_ESCUADRA`. Si las diagonales se diferencian más de 4 mm, ajusta antes la mecánica.

## Homing exacto de X/Y (recomendado para la recuperación tras corte de luz)
### Por qué varía
La X4 no tiene finales de carrera en X e Y. El homing lleva el carro (X) o la cama (Y) contra el tope, y el driver del
motor (TMC2209, función *StallGuard*) nota que el motor se frena y avisa de que ha llegado. Cuánto tiene que frenarse
para avisar lo decide la **sensibilidad** (`driver_SGTHRS`, de 0 a 255; **más alto = más sensible**):
- **Demasiado sensible**: confunde el esfuerzo normal del movimiento con un choque y **se para antes del tope** (o ni
  arranca). La pieza sale desplazada.
- **Poco sensible**: tarda en darse cuenta, el motor **golpea y patina contra el tope** (ruido de "saltar dientes") y
  cada homing acaba en un punto distinto. Fuerza correas y poleas.
- **Bien ajustada**: llega al tope y se para en seco, sin ruido, siempre en el mismo sitio.

El valor correcto depende de la velocidad del homing, la corriente del motor y lo suave que se mueva cada eje, así que
puede cambiar un poco de una impresora a otra. Tortillery+ (1.1.5) trae: homing a **20 mm/s** (la mitad de
`rotation_distance`, lo que recomienda Klipper; a 40 mm/s el margen entre "se para antes" y "golpea" era de 1 punto),
**X = 45** e **Y = 70**, ajustados en una X4 Pro.

### 1. Comprobar el homing
En la consola de Mainsail, sin imprimir: `PRUEBA_HOMING` (9 homings desde puntos distintos, unos 2 min). Dice cuántos mm
varía cada eje:

| Resultado | Qué pasa | Qué hacer |
|---|---|---|
| 0,30 mm o menos | Bien | Si quieres reanudar exacto tras un corte de luz: paso 3 |
| Entre 0,30 y 2 mm | Holgura mecánica | Tensa la correa de ese eje, aprieta el prisionero de su polea (que no gire sola sobre el eje del motor) y revisa que el carro o la cama se muevan suaves a mano, sin tirones. Repite la prueba |
| Más de 2 mm, o se oyen golpes | Sensibilidad mal ajustada | Paso 2 |

### 2. Ajustar la sensibilidad (solo si hace falta)
Con la mano cerca del interruptor, un eje cada vez (ejemplo con X; para la cama, `stepper_y` y `G28 Y`):
1. `M18` (suelta los motores), lleva el carro a mano hacia el centro.
2. `SET_TMC_FIELD STEPPER=stepper_x FIELD=SGTHRS VALUE=45` y luego `G28 X`.
3. Mira cómo para:
   - se para antes del tope o no se mueve → **baja** 5;
   - golpea, vibra o suena a dientes saltando → **sube** 5;
   - llega y se para en seco → anota el valor.

   Repite desde el paso 1 hasta dar con el rango bueno y quédate con un valor **del medio**, no con el límite (si 40 y
   55 fallan y 45-50 van bien, usa 45 o 50).
4. Con los valores puestos (sin reiniciar Klipper, que los borra), `PRUEBA_HOMING` para confirmarlo.
5. Para que se queden: en Mainsail › Máquina, crea `ajustes/homing.cfg` con `[tmc2209 stepper_x]` y
   `driver_SGTHRS: 50` (tu valor; igual con `stepper_y`) y reinicia el firmware. Así no se pierde al actualizar
   ([más ajustes](../printer/README.md)).

### 3. Dejarlo exacto (recomendado para la recuperación tras corte de luz)
Al imprimir de corrido unas décimas no se notan, pero al reanudar tras un corte (o tras un `G28 X Y` en una pausa) la
pieza sigue desplazada esa diferencia. Con la sensibilidad ya buena y **justo después de reiniciar Klipper** (así no
cuentan los homings de los ajustes):
1. `PRUEBA_HOMING`. Si sale **0,30 mm o menos**:
2. `FIJAR_HOMING`. Guarda la fase de los motores (`[endstop_phase stepper_x/y]` al final de `printer.cfg`) y reinicia
   Klipper: desde entonces cada homing acaba en el mismo micropaso, exacto. No lo fijes con más variación (podría quedar
   desplazado 0,8 mm).

Para deshacerlo, borra las secciones `[endstop_phase stepper_x]` y `[endstop_phase stepper_y]` del final de
`printer.cfg` y reinicia el firmware. Si algún día un homing falla con "Endstop stepper_x incorrect phase", deshazlo y
repite la prueba. Repítela también si cambias la sensibilidad, una correa o un motor.

No subas X/Y a más de 16 micropasos: el driver deja de notar el choque y el homing golpea el tope sin pararse.

## Tiempo de impresión exacto
Moonraker pasa cada G-code que subes por Klipper Estimator, que calcula el tiempo con las velocidades y aceleraciones
reales de tu impresora (no con las del laminador). El tiempo restante de Mainsail y de la pantalla sale mucho más
ajustado. Solo los archivos subidos por Mainsail o el laminador (no los copiados a mano al USB).

## Rendimiento (lo aplica install.sh)
CPU en `performance` (`/etc/default/cpufrequtils`, lo aplica Armbian al arrancar), Klipper con más prioridad
(`klipper.service.d/tortillery.conf`, `Nice=-10`) y `vnstat` desactivado (escribía en la eMMC sin usarse).

## G-code de inicio en el laminador (opcional, recomendado)
`PRINT_START` sin parámetros hace lo mismo que antes. Con temperaturas hace todo el inicio: calentar cama → home →
malla adaptativa (solo bajo las piezas) → calentar boquilla → línea de purga (`draw_line`). Sustituye el G-code de inicio por:
- **OrcaSlicer**: `PRINT_START BED=[bed_temperature_initial_layer_single] EXTRUDER=[nozzle_temperature_initial_layer] MATERIAL=[filament_type]`
- **Cura**: `PRINT_START BED={material_bed_temperature_layer_0} EXTRUDER={material_print_temperature_layer_0} MATERIAL={material_type}`

`MATERIAL=` aplica el pressure advance guardado para ese material (PLA, PETG, ABS/ASA o TPU); sin él, el general.

Añade `PURGE=0` si no quieres la línea de purga. La malla adaptativa necesita etiquetas de objetos en el G-code: OrcaSlicer
las pone por defecto ("Label objects"); con Cura, Moonraker las añade solo si el archivo se **sube** por Mainsail o desde el
laminador (no a los archivos copiados al USB). Sin etiquetas, mide la cama entera como antes.

## Actualizar desde Mainsail (repo de GitHub)
`install.sh` clona el repo público (`REPO_URL` al principio de `install.sh`) en `~/tortillery` y añade
`[update_manager tortillery]` (canal `stable`: solo versiones etiquetadas). En Mainsail > Máquina > Actualizar aparece
`tortillery`; al actualizar, `tortillery-update.path` lanza `tortillery-update.sh` (espera si está imprimiendo). Por
seguridad no ejecuta nada de `~/tortillery` (es del usuario `mks`): root baja su propia copia a `/opt/tortillery/repo`,
comprueba que la última etiqueta lleva **la firma de Tortillery+** (`git verify-tag` con
`/usr/local/share/tortillery/tortillery_allowed_signers`) y solo entonces ejecuta su `install.sh` con el modelo de la
impresora. Una versión sin firma válida no se instala y queda apuntado en `/var/log/tortillery-update.log`. La pantalla
(`.tft`) y la placa siguen yendo por USB.

**Publicar una versión** (solo el autor, en el PC, en la carpeta del proyecto). El `.gitignore` solo deja subir lo
necesario para instalar: `tortillery_plus/` (sin `screen/`, herramientas, tests ni notas internas), `plr/`, `docs/` y
`README.md`. Las imágenes, `.HMI`, `.tft`, `RELEASE`, `printer.cfg`, `wifi.cfg` y las claves se quedan en el PC.
Las etiquetas se firman con `%USERPROFILE%\.tortillery\firma_git` (la misma clave que firma el USB, en formato SSH; ya
configurado en este repo con `gpg.format ssh`, `user.signingkey` y `tag.gpgSign`):
```powershell
git add .
git status
git commit -m "Tortillery+ 1.1.4"
git tag v1.1.4 -m "Tortillery+ 1.1.4"
git push origin main v1.1.4
```
Antes, sube `VERSION` en `install.sh`. Comprobar la firma: `git verify-tag v1.1.4` (con `gpg.ssh.allowedSignersFile`
apuntando a `tortillery_plus/system/tortillery_allowed_signers`, ya configurado). **Sin las claves de
`%USERPROFILE%\.tortillery` no podrás publicar versiones que las impresoras acepten: haz una copia.**

## Copias de seguridad de la config
Cada vez que cambia `printer.cfg` (por ejemplo, tras `SAVE_CONFIG`) se guarda una copia de `config/` en
`~/printer_data/backup/` y, si hay un USB puesto, en `USB/tortillery_backup/`; se quedan las 5 últimas de cada sitio.
Utilidades > `COPIA_SEGURIDAD_USB` la hace a mano. Llevan `tortillery_ai.cfg` y `telegram.cfg` (tu clave y tu token).

## Firma del USB de actualización
`build_release.py` (herramienta del autor) firma `SHA256SUMS` con la clave privada de `%USERPROFILE%\.tortillery\firma_privada.pem` (solo en
tu PC: haz una copia, sin ella no podrás firmar) y deja `SHA256SUMS.sig`. La impresora comprueba la firma con
`/usr/local/share/tortillery/tortillery_release.pub`: si está mal, no flashea nada; si no hay firma, flashea y lo apunta
en `/var/log/tortillery-update.log`.

## Comprobación de los archivos del USB (opcional, recomendado al distribuir)
Si en el USB hay un `SHA256SUMS`, solo se flashea si `klipper.bin` y `800_480.tft` coinciden (evita flashear una copia corrupta).
Para crearlo, en PowerShell dentro de la carpeta del USB:
```powershell
Get-FileHash klipper.bin,800_480.tft -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content SHA256SUMS
```

## Si se saca el USB imprimiendo
Si la impresión viene del USB, se pone en **pausa** (sube y aparca el cabezal, mantiene temperaturas) en vez de fallar. Al volver
a meter el **mismo** USB, la impresora reabre el archivo sola: pulsa **Reanudar** en la pantalla. (Hay una pequeña carrera: si
Klipper intenta leer antes de que llegue la pausa, puede quedar pausada sin aparcar; reanudar funciona igual.)

## Comprobar después de instalar
- `printer.cfg` arranca sin errores en Mainsail.
- Desconectar el termistor del hotend con la máquina en frío → Klipper debe pararse con "ADC out of range". (Reconectarlo con la
  máquina apagada.)
- Cancelar una impresión durante el calentamiento → los calentadores se apagan y no da error de extrusión en frío.
- Cortar la luz en una impresión de prueba → al arrancar la pantalla pregunta si reanudar.
- Tras el corte de luz de prueba, la pregunta sale en la página propia de la pantalla ("Do you want to resume the job?", con el
  nombre del archivo). Si la pantalla no tuviera esa página, sale la de confirmación genérica con el nombre del archivo.
- Desconectar el USB de la MCU con Klipper en marcha → la pantalla dice "Klipper parado: …" y Confirmar reinicia el firmware.
- `COPIA_SEGURIDAD_USB` desde la lista de macros → aparece `tortillery_backup_<fecha>.tar.gz` en el USB.
