#!/bin/bash
# MANTENIMIENTO_ESTADO / MANTENIMIENTO_HECHO. Same counter file KlipperLCD uses for its reminder
# (tortillery.py): total print seconds (Moonraker history) at the last maintenance.
FILE=/home/mks/printer_data/tortillery_maintenance
EVERY=200   # hours, same as MAINTENANCE_HOURS in KlipperLCD/tortillery.py

TOTAL=$(curl -s -m 5 http://127.0.0.1:7125/server/history/totals \
    | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["result"]["job_totals"]["total_print_time"]))' 2>/dev/null)
[ -n "$TOTAL" ] || { echo "No se pudo leer el historial de Moonraker"; exit 1; }

if [ "$1" = "reset" ] || [ ! -f "$FILE" ]; then
    echo "$TOTAL" > "$FILE"
    echo "Contador de mantenimiento a 0 (proximo aviso en $EVERY h de impresion)"
else
    BASE=$(cut -d. -f1 "$FILE")
    H=$(( (TOTAL - ${BASE:-0}) / 3600 ))
    echo "Horas de impresion desde el ultimo mantenimiento: $H h (aviso cada $EVERY h)"
fi
