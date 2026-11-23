#!/bin/bash
# mount-usb.sh (Tortillery+): the ONLY script that mounts the USB stick.
# Mounted at gcodes/USB (before: over gcodes/, hiding the local G-codes).
# tortillery-automount.sh and usb-wifi.sh read the files from this mount:
# mounting the same vfat partition a second time with other options (ro)
# fails with EBUSY, which made the stick "sometimes not show up".
DEVICE="$1"
MOUNT_POINT="/home/mks/printer_data/gcodes/USB"
MOONRAKER_URL="http://127.0.0.1:7125"
exec >> /var/log/usb-automount.log 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Mount] $*"; }

sleep 1
[ -b "$DEVICE" ] || { log "ERROR: $DEVICE no es un dispositivo de bloques"; exit 1; }
if mountpoint -q "$MOUNT_POINT"; then
    log "Ya hay un USB en $MOUNT_POINT; $DEVICE no se monta"; exit 0
fi

mkdir -p "$MOUNT_POINT"
TYPE=$(blkid -o value -s TYPE "$DEVICE")
case "$TYPE" in
    # FAT has no owners: give the files to mks (Moonraker) via mount options
    vfat|exfat) OPTS="rw,noatime,uid=$(id -u mks),gid=$(id -g mks),umask=022" ;;
    *)          OPTS="rw,noatime" ;;   # ext4 & co. reject uid=/umask=
esac
if ! out=$(mount -o "$OPTS" "$DEVICE" "$MOUNT_POINT" 2>&1); then
    log "ERROR al montar $DEVICE ($TYPE): $out"; rmdir "$MOUNT_POINT"; exit 1
fi
log "$DEVICE ($TYPE) montado en $MOUNT_POINT"

curl -s -m 10 -X POST -H "Content-Type: application/json" -d '{"path": "gcodes"}' \
    "$MOONRAKER_URL/server/files/scan_directory" >/dev/null

# A print paused because this stick was pulled out: point it at the new mount
read -r STATE FILE <<< "$(curl -s -m 5 "$MOONRAKER_URL/printer/objects/query?print_stats=state,filename" \
    | python3 -c 'import sys,json; s=json.load(sys.stdin)["result"]["status"]["print_stats"]; print(s["state"], s["filename"])' 2>/dev/null)"
if [ "$STATE" = "paused" ] && [[ "$FILE" == USB/* ]]; then
    log "Impresion en pausa desde el USB ($FILE): SDCARD_REOPEN"
    curl -s -m 10 -X POST -H "Content-Type: application/json" -d '{"script": "SDCARD_REOPEN"}' \
        "$MOONRAKER_URL/printer/gcode/script" >/dev/null
fi
exit 0
