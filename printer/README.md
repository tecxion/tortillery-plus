<div align="center">

# 🛠️ Personalizar la impresora

**Qué archivos de configuración puedes cambiar en Tortillery+, cómo hacerlo sin perderlo al actualizar y ejemplos**

[⬅️ Volver al README](../README.md) · [Guía completa](../tortillery_plus/README.md) · [🇬🇧 English](../Traducido/printer/README.md)

</div>

---

> [!TIP]
> En **[ejemplos](../ejemplos/README.md)** tienes cada archivo de esta guía comentado, listo para copiar.

Todos los archivos están en Mainsail › **Máquina** (carpeta `config`). Se editan ahí mismo: _Guardar y reiniciar_
aplica el cambio.

> [!CAUTION]
> No cambies nada con una impresión en marcha. Si Klipper no arranca después de un cambio, la pantalla y Mainsail dicen
> el motivo: deshaz el cambio (o borra el archivo que creaste) y reinicia el firmware.

## 📋 Qué se conserva al actualizar

Cada actualización (desde Mainsail o reinstalando) vuelve a escribir los archivos de Tortillery+. Esto es lo que pasa
con cada uno:

| Archivo                                   | ¿Se conserva?                         | Para qué                                                     |
| ----------------------------------------- | ------------------------------------- | ------------------------------------------------------------ |
| **`ajustes/*.cfg`**                       | ✅ Siempre                            | **Tus cambios de Klipper.** Ver abajo.                       |
| `printer.cfg` (bloque `SAVE_CONFIG`)      | ✅ Siempre                            | PID, Z-offset, mallas, input shaper, fase del homing.        |
| `printer.cfg` (el resto)                  | ❌ Se reescribe                       | Configuración de la X4 de serie.                             |
| `macros.cfg`, `plr.cfg`, `utilidades.cfg`, `kamp_tortillery.cfg`, `calibracion.cfg` | ❌ Se reescriben | Macros de Tortillery+.          |
| `tortillery_vars.cfg`                     | ✅ Siempre                            | Lo que guarda la calibración de la pantalla.                 |
| `moonraker.conf`                          | ✅ (solo se le añaden secciones)      | Cámara, actualizaciones, accesos.                            |
| `crowsnest.conf`                          | ✅ (solo cambia la línea `device:`)   | Resolución y fps de la cámara.                               |
| `tortillery_ai.cfg`                       | ✅ Siempre                            | Vigilancia con IA.                                           |
| `telegram.cfg`                            | ✅ Siempre                            | Bot de Telegram.                                             |
| `telegram.conf`                           | ❌ Se reescribe                       | Plantilla de los mensajes de Moonraker.                      |
| `ia_marcas.json`                          | ✅ Siempre                            | Las marcas de la cámara de `http://tortilleryplus.local/ia`. |
| `extras/*.cfg`                            | ✅ (lo gestiona `extras.sh`)          | Timelapse, Shake&Tune…                                       |

Además, cada cambio de `printer.cfg` se copia solo en `printer_data/backup` (y en el USB si está puesto).

## ⭐ La carpeta `ajustes`: tus cambios de Klipper

`printer.cfg` lee al final todos los archivos `config/ajustes/*.cfg`. Lo que pongas ahí **gana** sobre lo de arriba y
las actualizaciones no lo tocan.

1. En Mainsail › Máquina, entra en la carpeta `ajustes` (si no la ves, créala con _Crear carpeta_).
2. Crea un archivo, por ejemplo `mis_ajustes.cfg`.
3. Escribe **solo la sección y la opción que cambias**. Lo demás de esa sección sigue como en `printer.cfg`:

   ```ini
   [printer]
   max_velocity: 500

   [idle_timeout]
   timeout: 3600
   ```

4. _Guardar y reiniciar_.

Tienes un archivo con todas estas opciones comentadas en [`ejemplos/ajustes/mis_ajustes.cfg`](../ejemplos/ajustes/mis_ajustes.cfg).

Para volver a lo de serie, borra la línea (o el archivo) y reinicia el firmware.

> [!IMPORTANT]
> Dos cosas que **no** van en `ajustes`:
> - **Lo que guarda `SAVE_CONFIG`**: PID (`pid_kp`…), `z_offset` de `[probe]`, `[bed_mesh …]`, `shaper_freq_*` /
>   `shaper_type_*` y `[endstop_phase …]`. Si lo pones, Klipper se niega a guardar ("conflicts with included value").
>   Esos se calibran desde la pantalla o con sus órdenes (`PID_CALIBRATE`, `PROBE_CALIBRATE`…).
> - **Lo que guarda la pantalla en `tortillery_vars.cfg`**: `max_accel`, `pressure_advance` y la `rotation_distance`
>   del extrusor. Se aplican al arrancar y ganan sobre `ajustes`. Para cambiarlos, repite la calibración o borra su
>   línea de `tortillery_vars.cfg`.

## 🖨️ Cambios habituales en Klipper (`ajustes/*.cfg`)

Los valores de serie son los de la X4 Pro; donde la X4 Plus es distinta, se indica.

### Velocidad y aceleración

```ini
[printer]
max_velocity: 500           # de serie 1000 mm/s
max_accel: 8000             # de serie 10000; si calibraste el input shaper, manda el de tortillery_vars.cfg
square_corner_velocity: 5.0
```

Más bajo = más silencio y menos fallos en piezas altas. El laminador nunca podrá superar estos límites.

### Calentadores que se apagan solos

```ini
[idle_timeout]
timeout: 3600               # segundos sin actividad (de serie 1800 = 30 min)
```

Aplica en reposo y en las pausas normales. En **sin filamento** las temperaturas no bajan nunca solas (para eso está
_Enfriar_ en Telegram).

### Boquilla de otro tamaño o hotend distinto

```ini
[extruder]
nozzle_diameter: 0.600
max_temp: 300               # de serie 330
```

Después repite en la pantalla el PID de la boquilla y el pressure advance.

### Retracción del firmware (G10/G11)

Solo si en el laminador activas "usar retracción del firmware":

```ini
[firmware_retraction]
retract_length: 0.6         # de serie 0.8 mm
retract_speed: 35           # de serie 40 mm/s
```

Se puede probar sin reiniciar desde la consola: `SET_RETRACTION RETRACT_LENGTH=0.6`.

### Sensibilidad del homing de X/Y

Si el homing golpea el tope o se para antes de llegar. Cómo encontrar tu valor:
[guía del homing](../tortillery_plus/README.md#homing-exacto-de-xy-recomendado-para-la-recuperación-tras-corte-de-luz).

```ini
[tmc2209 stepper_x]
driver_SGTHRS: 50           # de serie 45

[tmc2209 stepper_y]
driver_SGTHRS: 75           # de serie 70
```

Después, `PRUEBA_HOMING` y, si sale bien, `FIJAR_HOMING`.

### Sonda: más precisión al medir

```ini
[probe]
samples: 5                  # Tortillery+ 3 toques por punto (se queda con la mediana)
samples_tolerance: 0.02     # Tortillery+ 0.03 mm
```

La malla tarda más. Desde la 1.1.5 la sonda ya baja a 3 mm/s y usa la mediana de 3 toques, como propone
[grumat](https://github.com/grumat/artillery-x4-pro_config/wiki/The-Inductive-Z%E2%80%90Probe): según sus medidas, varía menos de la mitad.

### Ventilador de capa

```ini
[fan]
max_power: 1.0              # de serie 0.8 (el 100 % del laminador es el 80 % real)
```

### Purga y aparcado (macros de Tortillery+)

Las opciones `variable_` de una macro también se cambian así, sin copiar la macro entera:

```ini
[gcode_macro LINE_PURGE]
variable_length: 60         # mm de línea (de serie 40)
variable_amount: 30         # mm de filamento (de serie 25)
variable_margin: 8          # distancia por delante de las piezas

[gcode_macro SMART_PARK]
variable_z: 10              # altura de aparcado mientras calienta
```

`LINE_PURGE` y `SMART_PARK` solo actúan si el G-code lleva etiquetas de objetos; sin ellas se usa la línea de
Artillery (`draw_line`).

### Recuperación tras corte de luz

```ini
[plr]
interval: 10                # segundos entre guardados (de serie 5); más alto = menos escrituras en la eMMC
```

### Sensor de filamento

Para apagarlo solo durante una impresión (por ejemplo con un filamento que el sensor no detecta), en la consola de
Mainsail:

```text
SET_FILAMENT_SENSOR SENSOR=fila ENABLE=0
```

Vuelve a encenderse al reiniciar Klipper.

### ⛔ Lo que no conviene tocar

- `step_pin`, `dir_pin`, `enable_pin` y demás pines: son los de la placa de la X4.
- `microsteps` de X/Y: con más de 16 el homing sin finales de carrera deja de notar el choque.
- `position_min`, `position_endstop` y `position_max`: los límites de la máquina.
- `rotation_distance` de X, Y y Z.
- `run_current` de los motores: más corriente calienta motores y drivers, y cambia la sensibilidad del homing.
- `x_offset` / `y_offset` de `[probe]`, salvo que hayas cambiado el cabezal.

## 🌙 Moonraker (`moonraker.conf`)

Este archivo **se conserva**: las actualizaciones solo le añaden lo que falte. Cambios habituales:

**Entrar en Mainsail desde otra red** (por ejemplo una VPN). Añade su rango en `[authorization]`:

```ini
[authorization]
trusted_clients:
    192.168.1.0/24
    100.64.0.0/10           # Tailscale
```

**Tiempo exacto de cada G-code** (Klipper Estimator), ya activado:

```ini
[analysis]
enable_auto_analysis: True  # False para desactivarlo
```

**Etiquetas de objetos** en los archivos que subes (necesarias para la malla y la purga junto a la pieza):

```ini
[file_manager]
enable_object_processing: True
```

**Cámaras en Mainsail**: `[webcam camara]` es la webcam y `[webcam ia]` lo último que ha revisado la IA. Puedes
cambiarles el nombre o borrar `[webcam ia]` si no usas la IA (la reinstalación la vuelve a añadir).

> [!NOTE]
> Al actualizar se fuerza `channel: stable` en `[update_manager]` y se reajusta `[update_manager tortillery]`: no
> cambies esas dos.

## 📷 Cámara (`crowsnest.conf`)

Tortillery+ elige sola la webcam conectada y solo cambia la línea `device:`. El resto es tuyo:

```ini
[cam 1]
resolution: 1280x720        # la de tu cámara
max_fps: 15
```

Si la IA ve mal la pieza, una resolución mayor ayuda más que más fps.

## 🤖 Vigilancia con IA (`tortillery_ai.cfg`)

Se aplica sola en menos de un minuto, sin reiniciar. Prueba con la cámara apuntando a la cama:
`python3 /usr/local/bin/tortillery-ai.py --test` (por SSH) y mira `ia_prueba.jpg`.

| Opción             | Qué hace                                                                                  | Ejemplo                    |
| ------------------ | ----------------------------------------------------------------------------------------- | -------------------------- |
| `proveedor`        | `anthropic`, `openai`, `google`, `nvidia`, `ollama` u `openai_compatible`.                | `anthropic`                |
| `api_key`          | La clave del proveedor (Ollama no la necesita).                                           |                            |
| `modelo`           | Modelo con visión. Vacío: el de serie del proveedor (no vale en `openai` ni `nvidia`).    | `claude-haiku-5-5`         |
| `modelo_confirmar` | Un segundo modelo, mejor, que solo se consulta cuando el primero ve un fallo.             | `claude-opus-5-5`          |
| `url`              | Solo `ollama` y `openai_compatible`: la dirección del servidor.                           | `http://192.168.1.50:11434`|
| `accion`           | Qué hacer con un fallo: `pausar` (recomendado), `avisar` o `cancelar`.                    | `pausar`                   |
| `intervalo`        | Segundos entre fotos (mínimo 30). Menos = detecta antes, pero gasta más.                  | `120`                      |
| `confirmaciones`   | Fotos seguidas con fallo antes de actuar.                                                 | `2`                        |
| `umbral`           | Confianza mínima (0 a 1) para contar una foto como fallo.                                 | `0.7`                      |
| `espera_inicio`    | Segundos de impresión antes de empezar a mirar.                                           | `60`                       |
| `camara`           | Describe tu cámara a la IA: dónde está y qué piezas salen.                                | ver abajo                  |
| `recorte`          | Vacío (recomendado): busca la cama o usa tus marcas. `no`: la foto entera. O fijo en %.   | `0,10,70,100`              |

Ejemplos:

```ini
# Barato y sin pausas en falso: vigila uno pequeño y confirma uno grande
proveedor: anthropic
modelo: claude-haiku-5-5
modelo_confirmar: claude-opus-5-5

# Gratis, con Ollama en tu PC (tiene que estar encendido)
proveedor: ollama
url: http://192.168.1.50:11434
modelo: qwen2.5vl

# Cámara en el cabezal
camara: cámara en el cabezal muy cerca de la boquilla; la pieza naranja de la izquierda es el conducto del ventilador
```

**Si pausa sin motivo**: sube `umbral` (0.8) o `confirmaciones` (3), o pon un `modelo_confirmar`.
**Si no ve los fallos**: marca la cámara en `http://tortilleryplus.local/ia`, describe la cámara en `camara` o baja
`intervalo`.

> [!WARNING]
> La `api_key` queda en este archivo: cualquiera con acceso a tu Mainsail puede verla. Bórrala antes de compartir el
> archivo o un log.

### Marcas de la cámara (`ia_marcas.json`)

Las crea la página `http://tortilleryplus.local/ia`. No se edita a mano: si mueves la cámara, repite las 4 fotos.
Para dejar de usarlas, bórralas desde esa misma página (o borra el archivo) y la IA vuelve a buscar la cama sola.

## 💬 Telegram (`telegram.cfg`)

```ini
[telegram]
token: 123456:ABC...        # el de @BotFather
chat_id:                    # vacío: se detecta solo con el primer mensaje que le mandes al bot
```

Se aplica solo en menos de un minuto. Un bot por impresora. Paso a paso: [guía de Telegram](../telegram/README.md). `telegram.conf` (al lado) es la plantilla de los mensajes:
se reescribe al actualizar, no lo edites.

## 🎯 Calibraciones guardadas (`tortillery_vars.cfg`)

Lo escribe la pantalla (_Nivelar › Calibración_) y se aplica al arrancar Klipper:

| Línea                                  | Lo guarda                                    |
| -------------------------------------- | -------------------------------------------- |
| `max_accel`                            | El input shaper (la aceleración recomendada) |
| `pressure_advance`                     | El patrón de pressure advance (el último)    |
| `pa_pla`, `pa_petg`, `pa_abs`, `pa_tpu`| El pressure advance de cada material         |
| `rotation_distance`                    | La calibración del extrusor (100 mm)         |

Para volver al valor de `printer.cfg`, borra la línea y reinicia el firmware. Mejor repetir la calibración que
escribir el valor a mano.

## 🧾 G-code de inicio del laminador

`PRINT_START` hace todo el inicio si le pasas las temperaturas:

- **OrcaSlicer**: `PRINT_START BED=[bed_temperature_initial_layer_single] EXTRUDER=[nozzle_temperature_initial_layer] MATERIAL=[filament_type]`
- **Cura**: `PRINT_START BED={material_bed_temperature_layer_0} EXTRUDER={material_print_temperature_layer_0} MATERIAL={material_type}`

Añade `PURGE=0` para no hacer la línea de purga. Más en la
[guía completa](../tortillery_plus/README.md#g-code-de-inicio-en-el-laminador-opcional-recomendado).
