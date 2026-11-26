#!/bin/bash
# tortillery-model.sh PRO|PLUS  (Tortillery+)
# printer.cfg y macros.cfg del modelo elegido, conservando la calibración de esta impresora (PID, Z-offset, mallas,
# input shaper) del bloque SAVE_CONFIG. Las plantillas las copia install.sh a printer_data/config.
# Lo usan install.sh y el asistente de primer arranque de la pantalla (KlipperLCD, vía sudo).
# Los archivos de config/ los maneja mks, no root: es una carpeta de mks y este script se puede lanzar con sudo sin
# contraseña, así que como root un enlace dejado ahí (printer.cfg.orig -> /etc/...) escribiría o leería fuera.
set -e
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo"; exit 1; }
MODEL="${1^^}"
[ "$MODEL" = PRO ] || [ "$MODEL" = PLUS ] || { echo "Uso: $0 PRO|PLUS"; exit 2; }

runuser -u mks -- bash -s "$MODEL" <<'EOF'
set -e
MODEL=$1
CFG=/home/mks/printer_data/config
MARK='#*# <---------------------- SAVE_CONFIG ---------------------->'
TPL="$CFG/artillery_X4_$MODEL.cfg"
[ -f "$TPL" ] && [ -f "$CFG/macros_X4_$MODEL.cfg" ] || { echo "Faltan las plantillas en $CFG (ejecuta install.sh)"; exit 1; }

mark_line() { grep -nF "$MARK" "$1" 2>/dev/null | head -n1 | cut -d: -f1; }
backup() { [ -f "$1" ] && [ ! -f "$1.orig" ] && cp -p "$1" "$1.orig"; return 0; }

NEW=$(mktemp)
n=$(mark_line "$TPL")
head -n $((n - 1)) "$TPL" > "$NEW"
m=$(mark_line "$CFG/printer.cfg")
if [ -n "$m" ]; then
    tail -n +"$m" "$CFG/printer.cfg" >> "$NEW"
    echo "  (calibracion de printer.cfg conservada)"
else
    tail -n +"$n" "$TPL" >> "$NEW"
fi
backup "$CFG/printer.cfg"
install -m 644 "$NEW" "$CFG/printer.cfg"
rm -f "$NEW"
backup "$CFG/macros.cfg"
install -m 644 "$CFG/macros_X4_$MODEL.cfg" "$CFG/macros.cfg"
echo "  $CFG/printer.cfg y macros.cfg: X4 $MODEL"
EOF
echo "$MODEL" > /etc/tortillery-model
[ "$2" = --restart ] && systemctl restart klipper   # asistente de la pantalla
exit 0
