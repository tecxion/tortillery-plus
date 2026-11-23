# Recuperación tras corte de luz (PLR) – Artillery X4 Pro/Plus (Tortillery)

## Cómo funciona
- `plr.py` (módulo de Klipper) guarda cada 5 s, mientras imprime, el archivo, el byte exacto del G-code
  y el estado (posición X/Y/Z/E, modos, offset Z, temperaturas, ventilador, velocidad/flujo).
  Escribe de forma atómica y con `fsync`: el rootfs está montado con `commit=120`, así que sin
  `fsync` se podrían perder hasta 2 minutos de datos al cortarse la luz.
- Al arrancar, KlipperLCD muestra la pantalla "¿Imprimir este archivo?" con el nombre del trabajo
  interrumpido: **Confirmar** → `RESUME_INTERRUPTED`, **Cancelar** → `PLR_CLEAR`.
- `RESUME_INTERRUPTED`: calienta, sube Z 5 mm, hace home de X/Y (Z **no**, la sonda chocaría con la
  pieza), purga, vuelve al punto guardado y continúa el archivo desde ese byte.
- Los datos se borran solos cuando la impresión termina o se cancela. Si se pausa, se conserva el último
  punto guardado antes de la pausa.

## Instalación
Se instala con `tortillery_plus/install.sh` (ver `tortillery_plus/INSTALAR.md`). Las configs de `tortillery_plus/config/` ya
llevan `[include plr.cfg]`.

Moonraker marcará el repositorio de Klipper como "dirty" por el archivo nuevo. Si actualizas Klipper,
vuelve a copiar `plr.py`.

## Limitaciones (importante)
- **Z no se re-homea**: se asume que el pórtico no se movió con la máquina apagada (husillos). Si se
  movió a mano, no reanudes.
- Puede quedar un pequeño hueco o una gota en el punto de reanudación (se guarda cada 5 s y Klipper
  lleva ~1-2 s de movimientos en cola). Baja `interval` en `plr.cfg` si quieres más precisión.
- Se carga la malla guardada `default`, no una calibrada al inicio de esa impresión y no guardada.
- El G-code tiene que seguir en el USB y el USB tiene que estar montado al reanudar.
- Los objetos excluidos (`EXCLUDE_OBJECT`) antes del corte vuelven a imprimirse.

## Otras mejoras que encontré revisando la imagen
1. **Seguridad térmica**: `min_temp: -100` (extrusor y cama) y `min_extrude_temp: 0` desactivan la
   detección de termistor desconectado. Con `verify_heater` muy permisivo (`max_error: 120`,
   `heating_gain: 1`), un termistor suelto puede acabar en una fuga térmica. Recomendado: `min_temp: 0`,
   `min_extrude_temp: 170`.
2. **Tortillery reflashea en cada arranque**: si el USB con `tortillery.update` se queda puesto, cada
   arranque para Klipper, vuelve a flashear la MCU y la pantalla (udev lanza "add" también al arrancar).
   Además, si se inserta durante una impresión, la arruina. Ahora mismo eso rompe también la
   recuperación tras el corte. Solución: comprobar que no se está imprimiendo y comparar un hash del
   `klipper.bin` con el último flasheado antes de actualizar.
3. **`CANCEL_PRINT` nunca llama a `BASE_CANCEL_PRINT`**: el trabajo queda como "standby" en vez de
   "cancelled" (afecta al historial de Moonraker). Además `G28 X` dentro de cancelar pasa por
   `homing_override`, que pone Z=0 y pierde la referencia de Z.
4. `idle_timeout` de 10 h: tras una pausa los calentadores pueden quedarse encendidos 10 h.
5. `usb-wifi.sh` borra **todas** las redes WiFi guardadas cada vez que se inserta un USB con
   `wifi.cfg`, y la contraseña va en texto plano en el USB.
6. `M300` ignora los parámetros `S`/`P` (siempre 1 kHz/100 ms).
7. `printer.cfg` suelto de esta carpeta es la versión de serie de 2024 (incluye un `plr.cfg` que no
   existe); la configuración real de la imagen es `artillery_X4_PRO.cfg` + `macros.cfg` (este último
   tampoco está en la imagen).
