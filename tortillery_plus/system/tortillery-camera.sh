#!/bin/bash
# tortillery-camera.sh (Tortillery+): crowsnest usa la primera webcam USB/USB-C (UVC) conectada.
# La imagen original traía en crowsnest.conf el id de UNA cámara concreta: cualquier otra no daba imagen.
#   tortillery-camera.sh            ajusta crowsnest.conf (antes de arrancar crowsnest, drop-in del servicio)
#   tortillery-camera.sh --restart  ajusta y reinicia crowsnest (al enchufar una cámara, regla de udev)
CONF=/home/mks/printer_data/config/crowsnest.conf
[ -f "$CONF" ] || exit 0
[ "$1" = --restart ] && sleep 2   # udev: los enlaces /dev/v4l/by-id aparecen justo después del evento
CAM=$(ls /dev/v4l/by-id/*-video-index0 2>/dev/null | head -n1)
[ -n "$CAM" ] || exit 0           # sin cámara: no se toca nada
CUR=$(sed -n 's/^device:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$CONF" | head -n1)
if [ "$CUR" != "$CAM" ]; then
    TMP=$(mktemp)
    sed "0,/^device:/s|^device:.*|device: $CAM   # elegida por tortillery-camera.sh|" "$CONF" > "$TMP" \
        && cat "$TMP" > "$CONF"   # cat: conserva dueño (mks) y permisos del archivo
    rm -f "$TMP"
    echo "crowsnest: cámara $CAM"
fi
[ "$1" = --restart ] && systemctl restart crowsnest.service
exit 0
