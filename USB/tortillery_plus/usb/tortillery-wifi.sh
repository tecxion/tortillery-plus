#!/bin/bash
# tortillery-wifi.sh (Tortillery+): WiFi desde la pantalla. Lo llama KlipperLCD (usuario mks) con sudo
# (regla en /etc/sudoers.d/tortillery-wifi, solo para este script).
#   tortillery-wifi.sh rescan          -> pide un escaneo nuevo
#   tortillery-wifi.sh connect "SSID"  -> contraseña por la entrada estándar (no aparece en ps ni en logs)
#   tortillery-wifi.sh forget "SSID"   -> borra la red guardada (y se desconecta si era la activa)
# Igual que usb-wifi.sh: no borra las demás redes guardadas ni reinicia la red.
LOG_FILE="/var/log/usb-wifi.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WiFi pantalla] $*" >> "$LOG_FILE"; }

case "$1" in
rescan)
    nmcli device wifi rescan >/dev/null 2>&1
    exit 0
    ;;
connect)
    SSID="$2"
    [ -n "$SSID" ] || { echo "SSID vacio"; exit 2; }
    IFS= read -r PASSWORD || true
    if nmcli -t -f NAME connection show | grep -qxF "$SSID"; then
        if [ -n "$PASSWORD" ]; then
            nmcli connection modify "$SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASSWORD" >/dev/null 2>&1
        fi
        out=$(nmcli connection up "$SSID" 2>&1)
    elif [ -n "$PASSWORD" ]; then
        out=$(nmcli device wifi connect "$SSID" password "$PASSWORD" name "$SSID" 2>&1)
    else
        out=$(nmcli device wifi connect "$SSID" name "$SSID" 2>&1)  # red abierta
    fi
    rc=$?
    if [ $rc -eq 0 ]; then
        log "Conectado a $SSID"
    else
        log "FALLO al conectar a $SSID: $out"
        # una conexión nueva que falla no se queda guardada con la contraseña mala
        nmcli -t -f NAME,TIMESTAMP connection show | grep -qxF "$SSID:0" && nmcli connection delete "$SSID" >/dev/null 2>&1
    fi
    echo "$out" | tail -n 1
    exit $rc
    ;;
forget)
    SSID="$2"
    nmcli -t -f NAME connection show | grep -qxF "$SSID" || { echo "Esa red no estaba guardada"; exit 1; }
    out=$(nmcli connection delete "$SSID" 2>&1); rc=$?
    log "Olvidada $SSID ($rc)"
    echo "$out" | tail -n 1
    exit $rc
    ;;
*)
    echo "Uso: $0 rescan | connect SSID (contraseña por stdin) | forget SSID"; exit 2
    ;;
esac
