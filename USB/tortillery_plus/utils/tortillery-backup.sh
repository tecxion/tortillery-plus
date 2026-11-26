#!/bin/bash
# COPIA_SEGURIDAD_USB: printer_data/config -> USB/tortillery_backup_<fecha>.tar.gz
# "auto" (tortillery-backup.path, cada vez que cambia printer.cfg, p. ej. tras SAVE_CONFIG): copia en
# printer_data/backup y, si hay USB, en USB/tortillery_backup/; se quedan las 5 últimas de cada sitio.
# Ojo: config/ incluye tortillery_ai.cfg y telegram.cfg (con tu clave y tu token): guarda el USB.
PD=${TORTILLERY_PD:-/home/mks/printer_data}   # variable solo para las pruebas
USB=$PD/gcodes/USB
KEEP=5
NAME="tortillery_backup_$(date +%Y%m%d_%H%M%S).tar.gz"

save() {  # save <carpeta>: copia y deja solo las $KEEP últimas
    mkdir -p "$1" || return 1
    if tar -czf "$1/$NAME" -C "$PD" config && sync; then
        ls -1t "$1"/tortillery_backup_*.tar.gz | tail -n +$((KEEP + 1)) | xargs -r rm -f
        echo "Copia guardada: $1/$NAME"
    else
        rm -f "$1/$NAME"; echo "ERROR al guardar la copia en $1"; return 1
    fi
}

if [ "$1" = auto ]; then
    save "$PD/backup" && chown -R mks:mks "$PD/backup"
    mountpoint -q "$USB" && save "$USB/tortillery_backup"
    exit 0
fi
mountpoint -q "$USB" || { echo "No hay ningun USB conectado"; exit 1; }
if tar -czf "$USB/$NAME" -C "$PD" config && sync; then
    echo "Copia guardada en el USB: $NAME"
else
    echo "ERROR al guardar la copia en el USB"; rm -f "$USB/$NAME"; exit 1
fi
