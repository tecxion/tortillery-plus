#!/bin/bash
# tortillery-firstboot.sh (Tortillery+): primer arranque de una imagen sellada con tortillery-seal.sh.
# Va antes de SSH, Klipper y KlipperLCD y solo se ejecuta una vez (marca en /var/lib/tortillery):
#  1. Identidad propia: machine-id y claves SSH nuevas (si no, todas las impresoras de la imagen comparten
#     claves SSH y, por el machine-id, pueden recibir la misma IP).
#  2. Graba la placa (klipper.bin) y la pantalla (800_480.tft) que lleva la imagen: no hace falta USB.
#  3. MCU_ID.cfg con el número de serie de ESTA placa.
# Después KlipperLCD muestra el asistente: modelo PRO/PLUS, WiFi, nivelación.
MARK=/var/lib/tortillery/firstboot.done
FW=/opt/tortillery/firmware
exec >> /var/log/tortillery-firstboot.log 2>&1
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [primer arranque] $*"; }
[ -f "$MARK" ] && exit 0
log "=== Inicio ==="

# 1. Identidad
# el sellado deja /etc/machine-id vacío: systemd genera uno al arrancar y aquí se guarda
systemd-machine-id-setup --commit >/dev/null 2>&1 || true
[ -s /etc/machine-id ] || systemd-machine-id-setup
ln -sf /etc/machine-id /var/lib/dbus/machine-id
log "machine-id $(cut -c1-8 /etc/machine-id)..."
ls /etc/ssh/ssh_host_*_key >/dev/null 2>&1 || { ssh-keygen -A && log "claves SSH nuevas"; }

# 2. Firmware de la placa y de la pantalla (mismo actualizador que el USB; solo graba lo que no esté ya grabado)
if [ -d "$FW" ]; then
    /usr/local/bin/tortillery-automount.sh --dir "$FW"
    log "firmware: ver /var/log/tortillery-update.log"
fi

# 3. MCU_ID.cfg (si no se grabó la placa, mcu_update no lo ha hecho); mcu-id.sh espera sin límite a la placa
[ -x /root/mcu-id.sh ] && timeout 60 /root/mcu-id.sh && log "MCU_ID.cfg: $(grep serial /home/mks/printer_data/config/MCU_ID.cfg)"
chown mks:mks /home/mks/printer_data/config/MCU_ID.cfg 2>/dev/null

# la marca solo cuando placa y pantalla constan grabadas: si algo falló se reintenta en el siguiente arranque
# (todo lo anterior se puede repetir sin daño)
for f in mcu:klipper.bin tft:800_480.tft; do
    [ "$(cat "/root/.tortillery/${f%%:*}.sha256" 2>/dev/null)" = "$(sha256sum "$FW/${f#*:}" | cut -d' ' -f1)" ] || {
        log "=== Fin: ${f#*:} sin grabar, se reintenta en el proximo arranque ==="; exit 0; }
done
mkdir -p "$(dirname "$MARK")" && date > "$MARK"
log "=== Fin ==="
exit 0
