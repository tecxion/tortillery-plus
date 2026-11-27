<div align="center">

<img src="assets/logo_fblanco.png" alt="Tortillery+" width="220">

# Tortillery+

**Klipper, Mainsail y una pantalla táctil nueva para la Artillery Sidewinder X4 Pro y X4 Plus**

[![Versión](https://img.shields.io/github/v/tag/tecxion/tortillery-plus?label=versi%C3%B3n&color=e21e26)](https://github.com/tecxion/tortillery-plus/tags)
![Impresoras](https://img.shields.io/badge/Artillery-X4%20Pro%20%7C%20X4%20Plus-222)
![Klipper](https://img.shields.io/badge/Klipper-Moonraker%20%2B%20Mainsail-b12f36)
![Idioma](https://img.shields.io/badge/idioma-espa%C3%B1ol-f1bf00)

[Descargar](#-descarga) · [Instalar](#-instalación) · [SSH](#-conectarse-por-ssh) · [Preguntas](#-preguntas-frecuentes) · [Problemas](#-problemas-comunes) · [Novedades](tortillery_plus/CAMBIOS.md) · [Guía completa](tortillery_plus/README.md) · [Personalizar](printer/README.md) · [Ejemplos](ejemplos/README.md) · [Telegram](telegram/README.md) · [🇬🇧 English](Traducido/README.md)

</div>

---

Grabas la imagen, enciendes la impresora y la pantalla te guía: **modelo, idioma, WiFi y nivelación**. Sin SSH, sin
editar archivos y conservando tu calibración en cada actualización.

## ✨ Qué trae

|                           |                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| 🖥️ **Pantalla nueva**     | WiFi desde la pantalla, explorador por carpetas con USB, tiempo restante real, errores en español y calibración guiada.   |
| 🎯 **Calibración guiada** | Input shaper con aceleración máxima, pressure advance por material, extrusor, torsión del eje X y escuadra X/Y.           |
| ⚡ **Corte de luz**       | Guarda el estado cada 5 s y al volver ofrece reanudar la impresión.                                                       |
| 📷 **Cámara automática**  | Cualquier webcam USB aparece en Mainsail sin configurar nada.                                                             |
| 🤖 **Vigilancia con IA**  | Detecta espagueti, piezas despegadas, atascos, bolas en la boquilla y capas desplazadas; pausa, avisa con foto y lo ves marcado en Mainsail. |
| 💬 **Telegram**           | Inicio, pausa con botones, fin con foto, vídeo del timelapse y aviso de mantenimiento. `/foto`, `/estado`, `/reanudar`.   |
| 🔄 **Actualizaciones**    | Desde Mainsail con un clic (solo versiones estables, nunca imprimiendo) y USB firmado para pantalla y placa.              |
| 🛡️ **Más segura**         | Apagado de calentadores en pausas largas, detección de termistor suelto, watchdog y copias automáticas de la config.      |

Lista completa de cambios respecto a la Tortillery original: **[CAMBIOS.md](tortillery_plus/CAMBIOS.md)**.

## 🆕 Novedades de la 1.1.5 (beta)

**Pantalla e impresión**
- 🛑 **Parada de emergencia** en la pantalla de impresión: botón rojo arriba a la izquierda, con confirmación.
- 🧵 **Sin filamento**: antes la impresora se paraba sin decir nada, con el cabezal encima de la pieza. Ahora avisa en
  la pantalla y en Telegram. _Aceptar_ aparta el cabezal a la izquierda (la cama no se mueve, no se pierde la posición) y
  abre _Cargar filamento_: Sacar y Meter 10, 50 o 100 mm y _Reanudar_. Las temperaturas no bajan solas en esa pausa;
  solo se apaga la boquilla si pulsas _Enfriar_ en Telegram. No reanuda si el sensor sigue sin filamento.
- 🔁 **Cambio de filamento (M600)**: abre la misma página _Cargar filamento_, a la temperatura de la impresión (antes
  calentaba a la del material elegido).
- 🚫 **No empieza sin filamento**: con el sensor activo y sin filamento, `PRINT_START` se para con un aviso.
- 📏 **Purga dentro de la cama**: los patrones de calibración purgan delante del patrón, y las impresiones sin etiquetas
  de objetos purgan 8 mm más adentro que la línea de Artillery (en el borde se podía salir).
- 🏠 **Homing de X/Y fiable**: a 20 mm/s y con la sensibilidad ajustada. `PRUEBA_HOMING` y `FIJAR_HOMING` lo dejan
  exacto para la recuperación tras un corte de luz.

**Calibración**
- Input shaper medido de 5 a 135 Hz (antes cortaba en 70 Hz y la resonancia de X de la X4 está en unos 100 Hz).
- Pressure advance por material: `PRINT_START MATERIAL=...` aplica el de PLA, PETG, ABS/ASA o TPU.
- Escuadra de X/Y con `CALIBRAR_ESCUADRA`.
- Al acabar un patrón, el cabezal se aparta y la cama sale adelante.

**IA y cámara**
- 📐 **Marca tu cámara** en `http://tortilleryplus.local/ia`: desde ahí la IA mira solo la pieza aunque se muevan la
  cama y el cabezal.
- Detecta también bolas en la boquilla y capas desplazadas, y mira la pieza de cerca.
- Si la foto sale oscura, enciende la luz del cabezal para hacerla.
- Cámara **ia** en Mainsail con lo último que ha revisado.

**Sistema**
- 🌐 La impresora se llama **`tortilleryplus.local`** en la red: ya no hace falta buscar la IP.
- ⏱️ Tiempo de impresión exacto (Klipper Estimator).
- 🛠️ **Tus ajustes no se pierden al actualizar**: lo que pongas en `config/ajustes/` gana sobre `printer.cfg`. Cómo
  hacerlo, en **[Personalizar la impresora](printer/README.md)**, con [ejemplos comentados](ejemplos/README.md).

## 📱 La pantalla

<div align="center">
<img src="assets/pantalla.png" alt="Pantallas de Tortillery+: menú principal, calibración, luz LED, malla automática, utilidades y color a medida" width="640">
</div>

<sub>Menú principal con la barra de estado, calibración guiada, luz LED, malla con 5x5 a 9x9 puntos, utilidades y color
a medida.</sub>

## 💬 Avisos en Telegram

<table>
<tr>
<td width="55%">
<img src="assets/telegram.png" alt="Avisos de Tortillery+ en Telegram: pausa con foto y botones, cancelación, inicio y fin con foto">
</td>
<td>

La impresora te escribe por Telegram:

- ▶️ **Inicio** y ⏹️ **cancelación**, también si cancelas desde la pantalla.
- ⏸️ **Pausa con foto** y botones: _Reanudar_, _Cancelar_ y _Otra foto_.
- ✅ **Fin con foto** y el tiempo que ha tardado.
- ⚡ **Corte de luz**: al volver la corriente te dice cuándo se fue, por dónde iba y te deja _Continuar_ o _Descartar_.
- 🤖 Si la IA ve un fallo, pausa y te manda la foto.
- 🧵 **Sin filamento**: aviso con _Enfriar_, _Reanudar_ y _Cancelar_; en la pantalla cargas el nuevo y las temperaturas no bajan.
- 🎬 Vídeo del timelapse y aviso de mantenimiento.

Órdenes: `/foto`, `/estado`, `/reanudar`, `/cancelar`, `/enfriar`, `/continuar`, `/descartar` y `/ayuda`, también en
el menú **/** del bot. Solo obedece a tu chat.

**[Guía de Telegram](telegram/README.md)**: crear el bot, el token, el ID del chat y las órdenes.

</td>
</tr>
</table>

## 🤖 Vigilancia con IA

Cada minuto (o lo que elijas) la IA mira la foto de la cámara. Si ve un fallo, **pausa la impresión** y te avisa con la foto.

- Al empezar cada impresión busca la cama en la foto y solo mira esa zona, ampliada: vale **cualquier posición de la
  cámara**.
- **Marca tu cámara** en `http://tortilleryplus.local/ia`: la impresora se pone en 4 posiciones, haces una foto en
  cada una y tocas la boquilla y las esquinas de la cama. Desde ahí la IA mira solo la pieza, ampliada, aunque la cama
  y el cabezal se muevan, y sin gastar consultas en buscarla. Vale con la cámara en el marco, en la cama o en el cabezal.
- Compara cada foto con otra de hace unos minutos, así nota una pieza que se ha movido o un espagueti que crece.
- Antes de pausar puede pedir confirmación a un segundo modelo.
- **Lo ves en vivo en Mainsail**: la cámara **ia** enseña la última foto revisada con la pieza (verde), el fallo (rojo)
  y el veredicto.
- Proveedores: Anthropic, OpenAI, Google, NVIDIA, Ollama (en tu PC, gratis) o cualquiera compatible con OpenAI.

Ejemplo real con una foto de espagueti (`tortillery-ai.py --test foto.jpg`):

```text
Proveedor nvidia, modelo nvidia/nemotron-3.5-super-vl-120b-a12b
{"fallo": true, "tipo": "espagueti", "confianza": 0.95,
 "motivo": "Exceso de filamento enredado alrededor del objeto impreso."}
```

Con `--test` también se guarda en `ia_prueba.jpg` lo que ha visto la IA, para comprobar que tu cámara encuadra bien.
Se configura en `tortillery_ai.cfg` desde Mainsail: [cómo hacerlo](tortillery_plus/README.md#detección-de-fallos-con-ia-opcional).

## ⚖️ Tortillery y Tortillery+

|                                                | Tortillery original | **Tortillery+** |
| ---------------------------------------------- | :-----------------: | :-------------: |
| Klipper, Moonraker y Mainsail en la eMMC       |         ✅          |       ✅        |
| Instalar sin SSH (asistente en pantalla)       |          —          |       ✅        |
| Claves SSH e identidad propias por impresora   |          —          |       ✅        |
| WiFi desde la pantalla                         |          —          |       ✅        |
| Calibración guiada (input shaper, PA…)         |          —          |       ✅        |
| Malla 5x5 a 9x9 y luz LED a medida             |          —          |       ✅        |
| Vigilancia con IA y Telegram                   |          —          |       ✅        |
| Actualizar desde Mainsail (versiones firmadas) |          —          |       ✅        |
| Apagado de calentadores en pausas largas       |          —          |       ✅        |

## 📦 Descarga

La imagen de la eMMC y el firmware de la pantalla pesan demasiado para GitHub y están en Terabox:

> **[⬇️ Descargar Tortillery+ (Terabox)](https://1024terabox.com/s/1VxnkAWIMICElKzex2T21og)**

**Versión actual: 1.1.5 (beta).** La imagen trae Klipper 0.14.0, Moonraker 0.11.0 y Mainsail 2.19.0. Descarga la carpeta
`Tortillery+_1.1.5`: dentro está la imagen (`IMAGEN_EMMC`) y la carpeta `USB`. Lo nuevo de cada versión, en
[Novedades](tortillery_plus/CAMBIOS.md).

## 🧰 Qué necesitas

- Una **Artillery Sidewinder X4 Pro o X4 Plus**.
- Un **lector de eMMC** (adaptador USB para el módulo eMMC de la placa) para grabar la imagen. Sin él hay un método
  avanzado y con riesgos: [Instalar sin adaptador](Actualizar%20sin%20adaptador/README.md).
- Un **pendrive FAT32**, solo para actualizar la pantalla y el firmware de la placa.
- Opcional: una **webcam USB** (cualquiera UVC) para fotos, timelapse y la IA.
- Opcional: una **clave de API** de IA (u Ollama en tu PC) y un **bot de Telegram** creado con
  [@BotFather](https://t.me/BotFather).

## 🚀 Instalación

<img src="assets/asistente.gif" alt="Asistente del primer arranque: modelo, idioma y bienvenida" width="200" align="right">

1. **Graba la imagen** en la eMMC de la impresora con [balenaEtcher](https://etcher.balena.io/) y deja que verifique.
2. **Enciende la impresora.** El primer arranque tarda unos minutos: graba la placa y la pantalla solo.
3. **En la pantalla**: elige X4 Pro o X4 Plus y el idioma.
4. **Bienvenida**: conecta el WiFi, nivela la cama y pulsa _Terminar_.

Para entrar en Mainsail, escribe en el navegador cualquiera de las dos:

- **`http://tortilleryplus.local`**: el nombre de la impresora en tu red, sin buscar nada.
- **`http://<IP de la impresora>`**: la IP aparece en la bienvenida y en _Ajustes_. Úsala si el nombre no funciona
  (algunos Android antiguos y algunas redes de empresa no lo resuelven).

> [!TIP]
> ¿Ya tienes la Tortillery original? Puedes actualizar sin volver a grabar la eMMC: mira
> [la guía de instalación](tortillery_plus/README.md).

## 🔄 Actualizar

- **Desde Mainsail**: _Máquina › Actualizar › `tortillery`_. Actualiza configs, macros y KlipperLCD a la última versión
  publicada. Tu calibración (PID, Z-offset, mallas, input shaper) se conserva.
- **Por USB, sin internet**: mira [Actualizar por USB](#-actualizar-por-usb-sin-internet).

## 💾 Actualizar por USB (sin internet)

La carpeta **[`USB`](USB)** de este repositorio es la última versión (ahora la **1.1.5 beta**), firmada. Sirve para
actualizar una impresora que ya tiene Tortillery+ sin internet: solo hace falta la red de casa para el paso 4. (Desde la
Tortillery original vale la misma carpeta, con los pasos de [la guía de instalación](tortillery_plus/README.md#pasar-de-la-tortillery-original-a-tortillery-sin-grabar-la-emmc).)

1. Descarga el repositorio: botón verde **Code › Download ZIP** y descomprímelo.
2. Copia **todo lo que hay dentro** de la carpeta `USB` a la raíz de un pendrive FAT32 (no la carpeta, su contenido).
   Opcional: pon también `wifi.cfg` o `telegram.cfg` ([ejemplos](ejemplos/usb)).
3. Con la impresora apagada, pon el pendrive y enciéndela. Graba sola la placa y la pantalla (solo si han cambiado) y
   la pantalla vuelve a arrancar. Tarda unos minutos: no la apagues.
4. Instala configs, macros y pantalla. Por SSH (`ssh mks@<IP>`; `tortilleryplus.local` solo si ya tenías la 1.1.5 o posterior):

   ```bash
   sudo bash ~/printer_data/gcodes/USB/tortillery_plus/install.sh PRO     # o PLUS
   sudo reboot
   ```

   Tu calibración (PID, Z-offset, mallas, input shaper) y la carpeta `ajustes` se conservan.
5. Quita el pendrive.

> [!NOTE]
> La impresora comprueba la firma (`SHA256SUMS.sig`) antes de grabar nada: si un archivo se ha cambiado o la copia
> está corrupta, no graba. Nunca actualiza mientras imprime. Lo que ha hecho queda en
> `journalctl -u tortillery-update` y `/var/log/tortillery-update.log`.

## 💻 Conectarse por SSH

No hace falta para usar la impresora, pero sirve para ver logs, reiniciar servicios o instalar extras.

1. Abre una terminal (en Windows, PowerShell ya trae `ssh`; también vale [PuTTY](https://www.putty.org/)).
2. Conéctate por el nombre de la impresora o por su IP (la ves en la pantalla, en _Ajustes_):

   ```bash
   ssh mks@tortilleryplus.local
   ```

   ```bash
   ssh mks@<IP de la impresora>
   ```

   El nombre `tortilleryplus.local` lo pone la 1.1.5: en una versión anterior, entra por la IP.

3. Usuario `mks`, contraseña `makerbase`. La primera vez te pregunta si confías en la impresora: escribe `yes`.

> [!IMPORTANT]
> Cambia la contraseña nada más entrar con `passwd`, sobre todo si abres la impresora a internet. `root` no puede
> entrar por SSH con contraseña: usa `mks` y `sudo`.

### Comandos útiles

| Para qué                                    | Comando                                                            |
| ------------------------------------------- | ------------------------------------------------------------------ |
| Ver la IP                                   | `hostname -I`                                                      |
| Estado de Klipper, Moonraker y la pantalla  | `systemctl status klipper moonraker KlipperLCD`                    |
| Reiniciar Klipper / la pantalla / Moonraker | `sudo systemctl restart klipper` · `KlipperLCD` · `moonraker`      |
| Log de Klipper en directo                   | `tail -f ~/printer_data/logs/klippy.log`                           |
| Log de la pantalla                          | `journalctl -u KlipperLCD -f`                                      |
| Log de la IA y Telegram                     | `journalctl -u tortillery-ai -f`                                   |
| Probar la IA con la cámara (o con una foto) | `python3 /usr/local/bin/tortillery-ai.py --test [foto.jpg]`        |
| Log de las actualizaciones                  | `journalctl -u tortillery-update -n 50`                            |
| Reparar o reinstalar Tortillery+            | `sudo bash ~/tortillery/tortillery_plus/install.sh PRO` (o `PLUS`) |
| Redes WiFi a la vista / configurar red      | `nmcli device wifi list` · `sudo nmtui`                            |
| Espacio libre                               | `df -h /`                                                          |
| Reiniciar / apagar                          | `sudo reboot` · `sudo poweroff`                                    |

**Extras opcionales** (se instalan uno a uno; volver a ejecutarlos solo los actualiza). La imagen no trae ningún extra
instalado: `config/extras/` está vacía hasta que instalas uno que use macros (timelapse o Shake&Tune).

```bash
sudo bash ~/tortillery/tortillery_plus/extras.sh tailscale   # Mainsail y SSH desde fuera de casa
bash ~/tortillery/tortillery_plus/extras.sh octoeverywhere    # acceso remoto y avisos desde la app
sudo bash ~/tortillery/tortillery_plus/extras.sh timelapse   # vídeo de cada impresión (necesita cámara)
bash ~/tortillery/tortillery_plus/extras.sh shaketune         # gráficas de correas y vibraciones
bash ~/tortillery/tortillery_plus/extras.sh mobileraker       # avisos push en el móvil
```

> [!CAUTION]
> No apagues ni reinicies mientras imprime, y no edites `printer.cfg` por SSH con una impresión en marcha.

## ❓ Preguntas frecuentes

<details>
<summary><b>¿Pierdo la calibración al actualizar?</b></summary>

No. El instalador conserva el bloque `SAVE_CONFIG` de `printer.cfg` (PID, Z-offset, mallas, input shaper),
`tortillery_vars.cfg` (pressure advance, aceleración, extrusor) y guarda una copia `.orig` de cada archivo que
reemplaza. Los cambios que hagas a mano en `printer.cfg` **sí se pierden**: ponlos en `config/ajustes/`
([cómo](printer/README.md)). Además, cada cambio de `printer.cfg` se copia solo en
`printer_data/backup` (y en el USB si está puesto).

</details>

<details>
<summary><b>¿La IA cuesta dinero?</b></summary>

Depende del proveedor. Con **Ollama** en tu PC no pagas nada. NVIDIA da créditos gratuitos para empezar. Anthropic,
OpenAI y Google cobran por uso; para ahorrar, la IA no envía fotos repetidas y solo mira mientras imprimes.

</details>

<details>
<summary><b>¿Necesito cámara?</b></summary>

Solo para la IA, las fotos de Telegram y el timelapse. Todo lo demás funciona sin cámara.

</details>

<details>
<summary><b>¿Puedo usar el mismo bot de Telegram en dos impresoras?</b></summary>

No. Telegram solo deja a un programa leer los mensajes de cada bot. Crea **un bot por impresora** con @BotFather.

</details>

<details>
<summary><b>¿Puedo volver a la Tortillery original o al firmware de Artillery?</b></summary>

Sí: graba en la eMMC la imagen que quieras, igual que grabaste esta. Antes, haz una copia de tu `printer.cfg` desde
Mainsail.

</details>

<details>
<summary><b>¿Qué versión tengo?</b></summary>

En la pantalla: _Ajustes › Información_. En Mainsail: _Máquina › Actualizar › `tortillery`_. Si es anterior a la 1.1.4,
actualiza desde Mainsail (pulsa ↻ si aún no la ve).

</details>

## 🔧 Problemas comunes

> [!WARNING]
> Muchas de las pantallas cogeladas las he solucionado apagando y encendiendo de nuevo.

| Lo que ves                                                  | Qué hacer                                                                                                                                                                                                                                      |
| ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| La pantalla no responde o se queda en el logo               | Espera al primer arranque (varios minutos). Si sigue igual, en SSH: `sudo systemctl restart KlipperLCD`. Si no, vuelve a pasar la carpeta `USB` de la descarga.                                                                                |
| Error de Klipper en la pantalla                             | La pantalla dice el motivo en español; pulsa _Reiniciar firmware_. El detalle está en Mainsail › _Máquina_ › `klippy.log`.                                                                                                                     |
| Mainsail muestra `tortillery` como **INVALID**              | Pasa en impresoras con la 1.0.1. En SSH: `sudo bash ~/tortillery/tortillery_plus/install.sh PRO` (o `PLUS`). Desde la 1.1.0 ya no ocurre.                                                                                                      |
| Telegram: `409 Conflict` en el log                          | Otro programa usa el mismo bot (otra impresora, otro script). Usa un bot por impresora.                                                                                                                                                        |
| La IA no detecta fallos                                     | Prueba con `python3 /usr/local/bin/tortillery-ai.py --test` y mira `config/ia_prueba.jpg`: si la cama no se ve, mueve la cámara o pon `recorte:` a mano en `tortillery_ai.cfg`. El log: `journalctl -u tortillery-ai -f`.                      |
| La IA pausa sin motivo                                      | Sube `umbral:` o `confirmaciones:` en `tortillery_ai.cfg`, o pon un `modelo_confirmar:`.                                                                                                                                                       |
| No aparece el USB                                           | Formatea el pendrive en FAT32 (o ext4). Sale en Mainsail y en la pantalla dentro de la carpeta `USB`.                                                                                                                                          |
| Al reanudar tras un corte, la pieza sigue desplazada en X/Y | Es el homing sin finales de carrera. En la consola de Mainsail: `PRUEBA_HOMING` y, si varía 0,30 mm o menos, `FIJAR_HOMING`. [Más detalles](tortillery_plus/README.md#homing-exacto-de-xy-recomendado-para-la-recuperación-tras-corte-de-luz). |
| El homing golpea el tope, suena a dientes saltando o se para antes de llegar | Sensibilidad del homing mal ajustada para tu impresora. [Guía para ajustarla](tortillery_plus/README.md#homing-exacto-de-xy-recomendado-para-la-recuperación-tras-corte-de-luz). |
| No empieza a imprimir: "Sin filamento"                      | El sensor no detecta filamento. Carga filamento o apaga el sensor para esa impresión: `SET_FILAMENT_SENSOR SENSOR=fila ENABLE=0`. |
| WiFi: contraseña mal escrita                                | Vuelve a conectar desde _Ajustes › WiFi_; las demás redes guardadas no se borran.                                                                                                                                                              |
| La actualización desde Mainsail no se instala               | Solo se instalan versiones firmadas y nunca imprimiendo. Mira `journalctl -u tortillery-update`.                                                                                                                                               |

## 🆘 Ayuda y contacto

¿Algo no funciona o tienes una idea? Abre una **[incidencia en GitHub](https://github.com/tecxion/tortillery-plus/issues)**
y cuenta:

- Modelo (X4 Pro o X4 Plus) y versión de Tortillery+.
- Qué hiciste, qué esperabas y qué pasó (una foto de la pantalla ayuda mucho).
- Los logs: `klippy.log` y `moonraker.log` (Mainsail › _Máquina_) y, si es la IA, `journalctl -u tortillery-ai -n 100`.

> [!WARNING]
> Antes de pegar un log o un archivo de config, **borra tus claves**: el token de Telegram y las API keys de la IA.

### 🎮 Tambien en Discord

- Si usáis discord también podeis poner vuestras dudas ahí he creado en mi canal un foro relacionado con Tortillery +.

[DISCORD](https://discord.gg/QAbVYzxPKk)

## 📁 Qué hay en este repositorio

```
tortillery_plus/   configs de Klipper, instalador, scripts, IA, Telegram y servicios
plr/               recuperación tras corte de luz y KlipperLCD (pantalla)
printer/           guía para personalizar printer.cfg, moonraker.conf, la IA y Telegram
telegram/          guía de Telegram: crear el bot, token, ID y órdenes
Actualizar sin adaptador/  instalar sin lector de eMMC (método avanzado, de Mustafa Yücel)
ejemplos/          archivos de ejemplo comentados (ajustes, IA, Telegram, Moonraker, cámara, laminador)
USB/               USB de actualización sin internet (última versión, firmada)
Traducido/         este README y la guía de personalizar, en inglés
assets/              imágenes del README
```

## 🙏 Agradecimientos

- **[CiareCw455/Tortillery](https://github.com/CiareCw455/Tortillery)** — la Tortillery original, de donde salió la idea, y
  el proyecto `.HMI` de la pantalla Tortillery v0.5.2 sobre el que está hecha la de Tortillery+. ¡Gracias!
- **[joakimtoe/KlipperLCD](https://github.com/joakimtoe/KlipperLCD)** (Apache-2.0) — el programa que une la pantalla con
  Klipper. Los archivos modificados están en `plr/KlipperLCD/` con su licencia.
- **JeroMod** y **Tortillery 2.0** (@UrtziDV) — ideas incorporadas.
- [Klipper](https://github.com/Klipper3d/klipper), [Moonraker](https://github.com/Arksine/moonraker),
  [Mainsail](https://github.com/mainsail-crew/mainsail), Crowsnest, KAMP, Shake&Tune, Moonraker-Timelapse, Mobileraker y
  Armbian.

## 📜 Licencia

Este proyecto incluye componentes con las siguientes licencias:

- GPL-2.0 or later (armbian-mkspi)
- Apache-2.0 (KlipperLCD)

Por compatibilidad, Tortillery+ en su conjunto está licenciado bajo [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html).

### 💰 ¿Quieres apoyar mi trabajo?

Si te gusta lo que hago y quieres ayudarme a seguir creciendo y creando contenido:

<div align="center">
<p align="center">
  <a href="https://paypal.me/jfmpkiko">
    <img src="https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Paypal">
  </a>
  &nbsp;&nbsp;
  <a href="https://coff.ee/tecxart">
    <img src="https://github.com/tecxion/TecXion/blob/main/Media/cafe1.png" alt="Ko-fi" height="40px">
  </a>
</p>

<p align="center">
  <img alt="GitHub watchers" src="https://img.shields.io/github/watchers/tecxion/tortillery-plus?style=flat-square">
  &nbsp;
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/tecxion/tortillery-plus?style=flat-square">
  &nbsp;
</p>
</div>

<div align="center">
<sub>Hecho en España 🇪🇸 para la comunidad de la Artillery X4</sub>
</div>
