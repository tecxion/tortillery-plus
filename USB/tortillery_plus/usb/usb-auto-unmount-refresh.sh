#!/bin/bash
# usb-auto-unmount-refresh.sh (Tortillery+). $1 = kernel name of the removed partition (sda1).
# Only unmounts gcodes/USB if that partition is the one removed (before: any removal unmounted).
# If the running print comes from the stick, it is paused (parked, heaters kept) instead of
# failing mid-move; re-inserting the stick lets it resume (see mount-usb.sh).
MOUNT_POINT="/home/mks/printer_data/gcodes/USB"
MOONRAKER_URL="http://127.0.0.1:7125"
exec >> /var/log/usb-automount.log 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Unmount] $*"; }

SRC=$(findmnt -nr -o SOURCE --mountpoint "$MOUNT_POINT")
[ -n "$SRC" ] || exit 0
if [ -n "$1" ] && [ "$SRC" != "/dev/$1" ]; then exit 0; fi

read -r STATE FILE <<< "$(curl -s -m 5 "$MOONRAKER_URL/printer/objects/query?print_stats=state,filename" \
    | python3 -c 'import sys,json; s=json.load(sys.stdin)["result"]["status"]["print_stats"]; print(s["state"], s["filename"])' 2>/dev/null)"
if [ "$STATE" = "printing" ] && [[ "$FILE" == USB/* ]]; then
    log "USB retirado imprimiendo $FILE: pausa"
    curl -s -m 10 -X POST "$MOONRAKER_URL/printer/print/pause" >/dev/null
    curl -s -m 10 -X POST -H "Content-Type: application/json" \
        -d '{"script": "M117 USB retirado: vuelve a meterlo y pulsa Reanudar"}' \
        "$MOONRAKER_URL/printer/gcode/script" >/dev/null
fi

umount -l "$MOUNT_POINT" && rmdir "$MOUNT_POINT" 2>/dev/null
log "$SRC desmontado de $MOUNT_POINT"
curl -s -m 10 -X POST -H "Content-Type: application/json" -d '{"path": "gcodes"}' \
    "$MOONRAKER_URL/server/files/scan_directory" >/dev/null
exit 0
