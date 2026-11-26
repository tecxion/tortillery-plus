#!/bin/bash
# usb-wifi.sh (Tortillery+): connects to the WiFi in wifi.cfg (SSID=..., PASSWORD=...) on a USB stick.
# $1 = partition (/dev/sda1); without it (boot), all /dev/sd*1 are checked.
# Changes vs. original: does not delete the other saved networks (before, a wrong password left
# the printer offline), does not restart networking, and reads the file from mount-usb.sh's mount
# instead of mounting the partition a second time (EBUSY races).
LOG_FILE="/var/log/usb-wifi.log"
exec >> "$LOG_FILE" 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WiFi] $*"; }

# Directory where $1 is mounted; waits for mount-usb.sh, then mounts read-only itself as fallback
usb_dir() {
    local mp
    for _ in $(seq 1 15); do
        mp=$(findmnt -nr -o TARGET -S "$1" | head -n1)
        [ -n "$mp" ] && { echo "$mp"; return 0; }
        sleep 1
    done
    mp="/media/wifi-$(basename "$1")"
    mkdir -p "$mp" && mount -o ro "$1" "$mp" && { echo "$mp"; return 0; }
    rmdir "$mp" 2>/dev/null; return 1
}

if [ -n "$1" ]; then DEVICES="$1"; else DEVICES=$(ls /dev/sd*1 2>/dev/null); fi
CFG=""
for dev in $DEVICES; do
    [ -b "$dev" ] || continue
    dir=$(usb_dir "$dev") || continue
    if [ -f "$dir/wifi.cfg" ]; then CFG="$dir/wifi.cfg"; break; fi
    case "$dir" in /media/wifi-*) umount "$dir"; rmdir "$dir" ;; esac
done
[ -n "$CFG" ] || { log "Sin wifi.cfg en ${DEVICES:-ningun USB}"; exit 0; }

SSID=$(grep -i '^SSID=' "$CFG" | cut -d= -f2- | tr -d '\r')
PASSWORD=$(grep -i '^PASSWORD=' "$CFG" | cut -d= -f2- | tr -d '\r')
case "$CFG" in /media/wifi-*) umount "$(dirname "$CFG")"; rmdir "$(dirname "$CFG")" ;; esac
[ -n "$SSID" ] || { log "ERROR: SSID vacio en wifi.cfg"; exit 1; }
[ -n "$PASSWORD" ] || { log "ERROR: PASSWORD vacio en wifi.cfg"; exit 1; }

if [ "$(iwgetid -r)" = "$SSID" ]; then log "Ya conectado a $SSID"; exit 0; fi

nmcli device wifi rescan >/dev/null 2>&1; sleep 3
if nmcli -t -f NAME connection show | grep -qxF "$SSID"; then
    # Known network: just update the password and connect
    nmcli connection modify "$SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASSWORD" \
        && nmcli connection up "$SSID" >/dev/null 2>&1
else
    nmcli device wifi connect "$SSID" password "$PASSWORD" name "$SSID" >/dev/null 2>&1
fi
if [ $? -eq 0 ]; then
    log "Conectado a $SSID"
else
    log "FALLO al conectar a $SSID; las redes guardadas siguen disponibles"
fi
