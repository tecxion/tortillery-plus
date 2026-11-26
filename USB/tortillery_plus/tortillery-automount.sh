#!/bin/bash
# tortillery-automount.sh (Tortillery+)
# Updates MCU firmware (klipper.bin) and screen (800_480.tft) from a USB stick
# that contains tortillery.update. Device path in $1 (e.g. /dev/sda1).
# Or from a folder:  tortillery-automount.sh --dir /opt/tortillery/firmware  (primer arranque de la imagen)
#
# Changes vs. original:
#  - Never runs while printing/paused (inserting the stick used to kill the print).
#  - Only flashes files that differ from the last successful flash (sha256), so a
#    stick left plugged in no longer reflashes MCU + screen on every boot.
#  - Klipper and KlipperLCD are always started again, even if nothing/failed.
#  - The MCU hash is only recorded once the MCU is back on USB.

DEVICE_PATH="$1"
MOUNTPOINT="/media/tortillery"
STATE_DIR="/root/.tortillery"
MOONRAKER_URL="http://127.0.0.1:7125"
LOG_FILE="/var/log/tortillery-update.log"
TFT_FLASHER="/root/uart-921600"

exec >> "$LOG_FILE" 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Tortillery] $*"; }
log "=== Inicio para $DEVICE_PATH ==="

[ -n "$DEVICE_PATH" ] || { log "ERROR: falta el dispositivo (uso: $0 /dev/sdXN | --dir CARPETA)"; exit 1; }

# Print state from Moonraker. Empty if Moonraker/Klipper are not up yet (boot):
# then nothing can be printing.
print_state() {
    curl -s -m 5 "$MOONRAKER_URL/printer/objects/query?print_stats" \
        | grep -o '"state": *"[a-z]*"' | head -n1 | sed 's/.*"\([a-z]*\)"$/\1/'
}

# Returns 0 if file $1 differs from the hash stored under name $2
changed() { [ "$(sha256sum "$1" | cut -d' ' -f1)" != "$(cat "$STATE_DIR/$2.sha256" 2>/dev/null)" ]; }
remember() { mkdir -p "$STATE_DIR"; sha256sum "$1" | cut -d' ' -f1 > "$STATE_DIR/$2.sha256"; sync; }

# Read the files from mount-usb.sh's mount (gcodes/USB): a second mount of the same
# vfat partition with other options fails with EBUSY. Own read-only mount only as fallback.
if [ "$DEVICE_PATH" = --dir ]; then
    USB="$2"; trap 'log "=== Fin ==="' EXIT
else
for _ in $(seq 1 15); do
    USB=$(findmnt -nr -o TARGET -S "$DEVICE_PATH" | head -n1)
    [ -n "$USB" ] && break
    sleep 1
done
if [ -n "$USB" ]; then
    trap 'log "=== Fin ==="' EXIT
else
    USB="$MOUNTPOINT"
    mkdir -p "$USB"
    if ! mount -o ro "$DEVICE_PATH" "$USB"; then
        log "ERROR al montar $DEVICE_PATH"; rmdir "$USB" 2>/dev/null; exit 1
    fi
    trap 'umount "$USB"; rmdir "$USB" 2>/dev/null; log "=== Fin ==="' EXIT
fi

[ -f "$USB/tortillery.update" ] || { log "Sin tortillery.update, nada que hacer"; exit 0; }
fi

# Firma (build_release.py con la clave privada del PC): mala -> no se flashea; sin firma -> se acepta y se apunta
PUB=/usr/local/share/tortillery/tortillery_release.pub
if [ -f "$USB/SHA256SUMS.sig" ]; then
    if [ -f "$PUB" ] && [ -f "$USB/SHA256SUMS" ] && openssl pkeyutl -verify -pubin -inkey "$PUB" -rawin \
            -in "$USB/SHA256SUMS" -sigfile "$USB/SHA256SUMS.sig" >/dev/null 2>&1; then
        for f in klipper.bin 800_480.tft; do   # firmado: todo lo que se flashea tiene que estar en la lista
            [ ! -f "$USB/$f" ] || tr -d '\r' < "$USB/SHA256SUMS" | grep -q "  $f$" \
                || { log "ERROR: $f no esta en SHA256SUMS firmado. No se flashea nada."; exit 1; }
        done
        log "Firma del USB correcta"
    else
        log "ERROR: la firma del USB no es valida (no es de Tortillery+ o se ha modificado). No se flashea nada."
        exit 1
    fi
elif [ "$DEVICE_PATH" != --dir ]; then
    log "AVISO: USB sin firma (SHA256SUMS.sig); se acepta igualmente"
fi

# Optional integrity check: SHA256SUMS made with "sha256sum klipper.bin 800_480.tft > SHA256SUMS"
if [ -f "$USB/SHA256SUMS" ] && ! (cd "$USB" && tr -d '\r' < SHA256SUMS | sha256sum -c --ignore-missing --quiet); then
    log "ERROR: los archivos del USB no coinciden con SHA256SUMS (copia corrupta). No se flashea nada."
    exit 1
fi

STATE=$(print_state)
if [ "$STATE" = "printing" ] || [ "$STATE" = "paused" ]; then
    log "Impresora en estado '$STATE': actualizacion cancelada. Reinserta el USB al terminar."
    exit 0
fi

BIN="$USB/klipper.bin"
TFT="$USB/800_480.tft"
FLASH_MCU=0; FLASH_TFT=0
[ -f "$BIN" ] && changed "$BIN" mcu && FLASH_MCU=1
[ -f "$TFT" ] && changed "$TFT" tft && FLASH_TFT=1
if [ $FLASH_MCU = 0 ] && [ $FLASH_TFT = 0 ]; then
    log "Firmware y pantalla ya actualizados (mismo sha256). No se flashea nada."
    exit 0
fi

if [ $FLASH_MCU = 1 ]; then
    log "Flasheando MCU con klipper.bin nuevo..."
    systemctl stop klipper.service
    cp "$BIN" /root/klipper.bin
    /root/mcu_update.sh 2>&1 | tee /tmp/tortillery-mcu.out
    FLASH_RC=${PIPESTATUS[0]}
    # dfu-util suele fallar en el "leave" final (can't detach / get_status) aunque la placa quede grabada
    grep -q "File downloaded successfully" /tmp/tortillery-mcu.out && FLASH_RC=0
    # Wait for the MCU to come back as Klipper over USB
    for _ in $(seq 1 30); do
        ls /dev/serial/by-id/usb-Klipper_* >/dev/null 2>&1 && break
        sleep 1
    done
    if [ $FLASH_RC = 0 ] && ls /dev/serial/by-id/usb-Klipper_* >/dev/null 2>&1; then
        /root/mcu-id.sh
        remember "$BIN" mcu
        log "MCU actualizada"
    else
        log "ERROR: fallo el flasheo (codigo $FLASH_RC) o la MCU no aparece; se reintentara en la proxima insercion"
    fi
    systemctl start --no-block klipper.service   # --no-block: el primer arranque va antes de Klipper
fi

if [ $FLASH_TFT = 1 ]; then
    if [ -x "$TFT_FLASHER" ]; then
        log "Flasheando pantalla con 800_480.tft nuevo..."
        systemctl stop KlipperLCD.service
        # uart-921600 ignora el argumento: siempre lee /root/800_480.tft, y sale con 0 aunque falle
        cp "$TFT" /root/800_480.tft && sync
        "$TFT_FLASHER" 2>&1 | tee /tmp/tortillery-tft.out
        if grep -q "open file ok" /tmp/tortillery-tft.out && ! grep -q -i -E "fail|error" /tmp/tortillery-tft.out; then
            remember "$TFT" tft
            log "Pantalla actualizada"
        else
            log "ERROR: fallo al flashear la pantalla; se reintentara"
        fi
        systemctl start --no-block KlipperLCD.service
    else
        log "ERROR: $TFT_FLASHER no existe o no es ejecutable"
    fi
fi
