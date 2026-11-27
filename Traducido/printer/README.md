<div align="center">

# 🛠️ Customising the printer

**Which Tortillery+ config files you can change, how to keep your changes across updates, and examples**

[⬅️ Back to the README](../README.md) · [Full guide (Spanish)](../../tortillery_plus/README.md) · [🇪🇸 Español](../../printer/README.md)

</div>

---

> [!TIP]
> In **[examples](../../ejemplos/README.md)** every file in this guide is commented (Spanish and English), ready to copy.

All the files are in Mainsail › **Machine** (the `config` folder). Edit them right there: _Save & Restart_ applies the
change.

> [!CAUTION]
> Don't change anything while a print is running. If Klipper doesn't start after a change, the screen and Mainsail
> show the reason: undo the change (or delete the file you created) and restart the firmware.

## 📋 What survives an update

Every update (from Mainsail or by reinstalling) rewrites the Tortillery+ files. This is what happens to each one:

| File                                      | Kept?                                 | What for                                                     |
| ----------------------------------------- | ------------------------------------- | ------------------------------------------------------------ |
| **`ajustes/*.cfg`**                       | ✅ Always                             | **Your Klipper changes.** See below.                         |
| `printer.cfg` (`SAVE_CONFIG` block)       | ✅ Always                             | PID, Z-offset, meshes, input shaper, homing phase.           |
| `printer.cfg` (everything else)           | ❌ Rewritten                          | The stock X4 configuration.                                  |
| `macros.cfg`, `plr.cfg`, `utilidades.cfg`, `kamp_tortillery.cfg`, `calibracion.cfg` | ❌ Rewritten | Tortillery+ macros.                   |
| `tortillery_vars.cfg`                     | ✅ Always                             | What the screen calibration saves.                           |
| `moonraker.conf`                          | ✅ (sections are only added)          | Camera, updates, access.                                     |
| `crowsnest.conf`                          | ✅ (only the `device:` line changes)  | Camera resolution and fps.                                   |
| `tortillery_ai.cfg`                       | ✅ Always                             | AI monitoring.                                               |
| `telegram.cfg`                            | ✅ Always                             | Telegram bot.                                                |
| `telegram.conf`                           | ❌ Rewritten                          | Template for Moonraker's messages.                           |
| `ia_marcas.json`                          | ✅ Always                             | The camera marks from `http://tortilleryplus.local/ia`.      |
| `extras/*.cfg`                            | ✅ (managed by `extras.sh`)           | Timelapse, Shake&Tune…                                       |

On top of that, every change to `printer.cfg` is copied automatically to `printer_data/backup` (and to the USB stick if
one is plugged in).

## ⭐ The `ajustes` folder: your Klipper changes

`printer.cfg` reads every `config/ajustes/*.cfg` file at the end. Whatever you put there **overrides** what comes
before it, and updates never touch it.

1. In Mainsail › Machine, open the `ajustes` folder (if you don't see it, create it with _Create folder_).
2. Create a file, for example `my_settings.cfg`.
3. Write **only the section and the option you change**. The rest of that section stays as in `printer.cfg`:

   ```ini
   [printer]
   max_velocity: 500

   [idle_timeout]
   timeout: 3600
   ```

4. _Save & Restart_.

There's a file with all these options commented in [`ejemplos/ajustes/mis_ajustes.cfg`](../../ejemplos/ajustes/mis_ajustes.cfg).

To go back to stock, delete the line (or the file) and restart the firmware.

> [!IMPORTANT]
> Two things that **don't** go in `ajustes`:
> - **What `SAVE_CONFIG` stores**: PID (`pid_kp`…), `z_offset` in `[probe]`, `[bed_mesh …]`, `shaper_freq_*` /
>   `shaper_type_*` and `[endstop_phase …]`. If you put them there, Klipper refuses to save ("conflicts with included
>   value"). Calibrate those from the screen or with their commands (`PID_CALIBRATE`, `PROBE_CALIBRATE`…).
> - **What the screen saves in `tortillery_vars.cfg`**: `max_accel`, `pressure_advance` and the extruder
>   `rotation_distance`. They are applied at startup and override `ajustes`. To change them, run the calibration again
>   or delete their line from `tortillery_vars.cfg`.

## 🖨️ Common Klipper changes (`ajustes/*.cfg`)

The stock values are the X4 Pro ones; where the X4 Plus differs, it says so.

### Speed and acceleration

```ini
[printer]
max_velocity: 500           # stock 1000 mm/s
max_accel: 8000             # stock 10000; if you calibrated the input shaper, the one in tortillery_vars.cfg wins
square_corner_velocity: 5.0
```

Lower = quieter and fewer failures on tall parts. The slicer can never go past these limits.

### Heaters that turn off on their own

```ini
[idle_timeout]
timeout: 3600               # seconds without activity (stock 1800 = 30 min)
```

Applies when idle and during normal pauses. When **out of filament**, temperatures never drop on their own (that's
what the Telegram _Enfriar_ button is for).

### A different nozzle size or hotend

```ini
[extruder]
nozzle_diameter: 0.600
max_temp: 300               # stock 330
```

Then run the nozzle PID and the pressure advance again from the screen.

### Firmware retraction (G10/G11)

Only if you enable "use firmware retraction" in the slicer:

```ini
[firmware_retraction]
retract_length: 0.6         # stock 0.8 mm
retract_speed: 35           # stock 40 mm/s
```

You can try it without restarting from the console: `SET_RETRACTION RETRACT_LENGTH=0.6`.

### X/Y homing sensitivity

If homing hits the end or stops before getting there. How to find your value:
[homing guide (Spanish)](../../tortillery_plus/README.md#homing-exacto-de-xy-recomendado-para-la-recuperación-tras-corte-de-luz).

```ini
[tmc2209 stepper_x]
driver_SGTHRS: 50           # stock 45

[tmc2209 stepper_y]
driver_SGTHRS: 75           # stock 70
```

Then run `PRUEBA_HOMING` and, if it looks good, `FIJAR_HOMING`.

### Probe: more accurate measuring

```ini
[probe]
samples: 5                  # Tortillery+ 3 touches per point (keeps the median)
samples_tolerance: 0.02     # Tortillery+ 0.03 mm
```

The mesh takes longer. Since 1.1.5 the probe already moves down at 3 mm/s and uses the median of 3 touches, as
[grumat](https://github.com/grumat/artillery-x4-pro_config/wiki/The-Inductive-Z%E2%80%90Probe) suggests: according to
his measurements, it varies less than half as much.

### Part cooling fan

```ini
[fan]
max_power: 1.0              # stock 0.8 (the slicer's 100 % is really 80 %)
```

### Purge and parking (Tortillery+ macros)

A macro's `variable_` options can be changed the same way, without copying the whole macro:

```ini
[gcode_macro LINE_PURGE]
variable_length: 60         # mm of line (stock 40)
variable_amount: 30         # mm of filament (stock 25)
variable_margin: 8          # distance in front of the parts

[gcode_macro SMART_PARK]
variable_z: 10              # parking height while heating
```

`LINE_PURGE` and `SMART_PARK` only work if the G-code has object labels; without them, Artillery's line
(`draw_line`) is used.

### Power-loss recovery

```ini
[plr]
interval: 10                # seconds between saves (stock 5); higher = fewer writes to the eMMC
```

### Filament sensor

To turn it off for a single print only (for example with a filament the sensor doesn't detect), in the Mainsail
console:

```text
SET_FILAMENT_SENSOR SENSOR=fila ENABLE=0
```

It turns back on when Klipper restarts.

### ⛔ Better not to touch

- `step_pin`, `dir_pin`, `enable_pin` and other pins: they are the X4 board's.
- X/Y `microsteps`: above 16, homing without endstops stops noticing the hit.
- `position_min`, `position_endstop` and `position_max`: the machine limits.
- X, Y and Z `rotation_distance`.
- Motor `run_current`: more current heats motors and drivers, and changes the homing sensitivity.
- `x_offset` / `y_offset` in `[probe]`, unless you changed the toolhead.

## 🌙 Moonraker (`moonraker.conf`)

This file **is kept**: updates only add what's missing. Common changes:

**Opening Mainsail from another network** (for example a VPN). Add its range to `[authorization]`:

```ini
[authorization]
trusted_clients:
    192.168.1.0/24
    100.64.0.0/10           # Tailscale
```

**Accurate time for every G-code** (Klipper Estimator), already enabled:

```ini
[analysis]
enable_auto_analysis: True  # False to turn it off
```

**Object labels** in the files you upload (needed for the mesh and the purge next to the part):

```ini
[file_manager]
enable_object_processing: True
```

**Cameras in Mainsail**: `[webcam camara]` is the webcam and `[webcam ia]` is the last photo the AI checked. You can
rename them, or delete `[webcam ia]` if you don't use the AI (reinstalling adds it back).

> [!NOTE]
> Updates force `channel: stable` in `[update_manager]` and reset `[update_manager tortillery]`: don't change those
> two.

## 📷 Camera (`crowsnest.conf`)

Tortillery+ picks the connected webcam by itself and only changes the `device:` line. The rest is yours:

```ini
[cam 1]
resolution: 1280x720        # your camera's
max_fps: 15
```

If the AI struggles to see the part, a higher resolution helps more than more fps.

## 🤖 AI monitoring (`tortillery_ai.cfg`)

It applies by itself in under a minute, with no restart. Test it with the camera pointing at the bed:
`python3 /usr/local/bin/tortillery-ai.py --test` (over SSH) and look at `ia_prueba.jpg`.

The option names and values are in Spanish; keep them exactly as written.

| Option             | What it does                                                                               | Example                    |
| ------------------ | ------------------------------------------------------------------------------------------ | -------------------------- |
| `proveedor`        | Provider: `anthropic`, `openai`, `google`, `nvidia`, `ollama` or `openai_compatible`.      | `anthropic`                |
| `api_key`          | The provider's key (Ollama doesn't need one).                                              |                            |
| `modelo`           | Vision model. Empty: the provider's default (not allowed for `openai` or `nvidia`).        | `claude-haiku-5-5`         |
| `modelo_confirmar` | A second, better model that is only asked when the first one sees a failure.               | `claude-opus-5-5`          |
| `url`              | Only for `ollama` and `openai_compatible`: the server address.                             | `http://192.168.1.50:11434`|
| `accion`           | What to do on a failure: `pausar` (pause, recommended), `avisar` (notify) or `cancelar`.   | `pausar`                   |
| `intervalo`        | Seconds between photos (minimum 30). Lower = detects sooner, but costs more.               | `120`                      |
| `confirmaciones`   | Consecutive failure photos before acting.                                                  | `2`                        |
| `umbral`           | Minimum confidence (0 to 1) to count a photo as a failure.                                 | `0.7`                      |
| `espera_inicio`    | Seconds of printing before it starts watching.                                             | `60`                       |
| `camara`           | Describe your camera to the AI (English or Spanish): where it is and which parts show.     | see below                  |
| `recorte`          | Empty (recommended): finds the bed or uses your marks. `no`: whole photo. Or fixed, in %.  | `0,10,70,100`              |

Examples:

```ini
# Cheap with no false pauses: a small model watches and a big one confirms
proveedor: anthropic
modelo: claude-haiku-5-5
modelo_confirmar: claude-opus-5-5

# Free, with Ollama on your PC (it has to be on)
proveedor: ollama
url: http://192.168.1.50:11434
modelo: qwen2.5vl

# Camera on the toolhead
camara: camera on the toolhead very close to the nozzle; the orange part on the left is the fan duct
```

**If it pauses for no reason**: raise `umbral` (0.8) or `confirmaciones` (3), or set a `modelo_confirmar`.
**If it misses failures**: mark the camera at `http://tortilleryplus.local/ia`, describe it in `camara` or lower
`intervalo`.

> [!WARNING]
> The `api_key` is stored in this file: anyone with access to your Mainsail can see it. Remove it before sharing the
> file or a log.

### Camera marks (`ia_marcas.json`)

Created by the `http://tortilleryplus.local/ia` page. Don't edit it by hand: if you move the camera, take the 4 photos
again. To stop using them, delete them from that same page (or delete the file) and the AI goes back to finding the bed
by itself.

## 💬 Telegram (`telegram.cfg`)

```ini
[telegram]
token: 123456:ABC...        # the one from @BotFather
chat_id:                    # empty: detected automatically from the first message you send the bot
```

It applies by itself in under a minute. One bot per printer. Step by step: [Telegram guide](../telegram/README.md). `telegram.conf` (next to it) is the message template: it
is rewritten on update, don't edit it.

## 🎯 Saved calibrations (`tortillery_vars.cfg`)

Written by the screen (_Level › Calibration_) and applied when Klipper starts:

| Line                                   | Saved by                                     |
| -------------------------------------- | -------------------------------------------- |
| `max_accel`                            | The input shaper (recommended acceleration)  |
| `pressure_advance`                     | The pressure advance pattern (the last one)  |
| `pa_pla`, `pa_petg`, `pa_abs`, `pa_tpu`| The pressure advance for each material       |
| `rotation_distance`                    | The extruder calibration (100 mm)            |

To go back to the `printer.cfg` value, delete the line and restart the firmware. Running the calibration again is
better than writing the value by hand.

## 🧾 Slicer start G-code

`PRINT_START` does the whole start sequence if you pass it the temperatures:

- **OrcaSlicer**: `PRINT_START BED=[bed_temperature_initial_layer_single] EXTRUDER=[nozzle_temperature_initial_layer] MATERIAL=[filament_type]`
- **Cura**: `PRINT_START BED={material_bed_temperature_layer_0} EXTRUDER={material_print_temperature_layer_0} MATERIAL={material_type}`

Add `PURGE=0` to skip the purge line. More in the
[full guide (Spanish)](../../tortillery_plus/README.md#g-code-de-inicio-en-el-laminador-opcional-recomendado).
