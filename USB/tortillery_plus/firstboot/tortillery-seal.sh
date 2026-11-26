#!/bin/bash
# tortillery-seal.sh (Tortillery+): deja ESTA impresora lista para copiar su eMMC como imagen Tortillery+ para otros.
#   sudo tortillery-seal.sh SELLAR
# Antes: install.sh desde el USB del RELEASE (copia klipper.bin y 800_480.tft a /opt/tortillery/firmware).
# Borra todo lo propio de esta impresora: claves SSH, machine-id, redes WiFi, printer.cfg/MCU_ID.cfg (con su
# calibración), historial de impresiones, logs, gcodes e historiales de comandos. Al acabar se APAGA:
# saca la eMMC y cópiala a .img con un lector USB (ver INSTALAR.md). Si la vuelves a encender sin copiarla, hará el
# primer arranque (asistente incluido) como una impresora nueva.
set -e
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo"; exit 1; }
[ "$1" = SELLAR ] || { echo "Esto borra la configuración y la calibración de esta impresora. Para seguir: sudo $0 SELLAR"; exit 1; }
FW=/opt/tortillery/firmware
PD=/home/mks/printer_data
for f in klipper.bin 800_480.tft; do
    [ -f "$FW/$f" ] || { echo "Falta $FW/$f: ejecuta antes install.sh desde el USB del RELEASE"; exit 1; }
done
[ -x /usr/local/bin/tortillery-firstboot.sh ] || { echo "Falta tortillery-firstboot.sh: ejecuta antes install.sh"; exit 1; }

echo "Sellando..."
systemctl stop KlipperLCD klipper moonraker 2>/dev/null || true
# configuración propia: el asistente vuelve a elegir modelo y MCU_ID se rehace con la placa nueva
rm -f "$PD/config/printer.cfg" "$PD/config/printer.cfg.orig" "$PD/config/macros.cfg" "$PD/config/macros.cfg.orig" \
      "$PD/config/printer-"*.cfg "$PD/config/MCU_ID.cfg" /etc/tortillery-model
rm -f "$PD/tortillery_errors.log" "$PD/tortillery_maintenance" "$PD/plr_state"*
rm -rf "$PD/database/"* "$PD/logs/"* "$PD/timelapse/"* "$PD/backup"   # backup: copias con claves y token
# gcodes sin tocar gcodes/USB: puede ser el pendrive montado
find "$PD/gcodes" -mindepth 1 -maxdepth 1 ! -name USB -exec rm -rf {} +
grep -q '^\[telegram\]' "$PD/moonraker.secrets" 2>/dev/null && rm -f "$PD/moonraker.secrets"
# IA: plantilla limpia (la api_key de esta impresora fuera)
[ -f /usr/local/share/tortillery/tortillery_ai.cfg ] \
    && install -m 644 -o mks -g mks /usr/local/share/tortillery/tortillery_ai.cfg "$PD/config/tortillery_ai.cfg"
[ -f /usr/local/share/tortillery/telegram.cfg ] \
    && install -m 644 -o mks -g mks /usr/local/share/tortillery/telegram.cfg "$PD/config/telegram.cfg"
# firmware: el primer arranque graba placa y pantalla
rm -f /root/.tortillery/*.sha256 /root/klipper.bin
# redes WiFi guardadas (incluida la contraseña)
nmcli -t -f NAME,TYPE connection show | awk -F: '$2 == "802-11-wireless" {print $1}' | while IFS= read -r c; do
    nmcli connection delete "$c" >/dev/null && echo "  WiFi olvidada: $c"
done
rm -f /etc/NetworkManager/system-connections/*.nmconnection
# identidad: el primer arranque genera machine-id y claves SSH nuevas
rm -f /etc/ssh/ssh_host_*
: > /etc/machine-id
rm -f /var/lib/dbus/machine-id
# historiales y logs
rm -f /root/.bash_history /root/.lesshst /home/mks/.bash_history /home/mks/.lesshst /home/mks/.zsh_history \
      /root/debug_mcu-id.log /tmp/KlipperLCD.log
rm -rf /root/.cache/pip /home/mks/.cache/pip
find /var/log -type f \( -name '*.gz' -o -name '*.[0-9]' -o -name '*.old' \) -delete
find /var/log -type f -exec truncate -s 0 {} +
journalctl --rotate >/dev/null 2>&1 || true
journalctl --vacuum-time=1s >/dev/null 2>&1 || true
apt-get clean
# primer arranque armado: identidad/firmware (servicio) y asistente en la pantalla (KlipperLCD)
install -m 644 -o mks -g mks /dev/null "$PD/tortillery_setup.pending"
rm -f /var/lib/tortillery/firstboot.done
systemctl enable tortillery-firstboot.service
sync
[ -n "$TORTILLERY_IMAGE_BUILD" ] && { echo "Sellada (build_image.sh)."; exit 0; }
echo "Sellada. Se apaga en 10 s: saca la eMMC y copiala a .img (no la enciendas antes)."
sleep 10
poweroff
