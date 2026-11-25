#!/bin/bash
# Tortillery+ installer. Run on the printer:  sudo bash install.sh PRO   (or PLUS)
# Expects this folder next to ../plr (same layout as in the project).
# Every replaced file is backed up as <file>.orig (only the first time).
set -e
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo"; exit 1; }
VERSION="1.1.2"
REPO_URL="https://github.com/tecxion/tortillery-plus.git"   # repo público de Tortillery+ (update_manager)
MODEL="${1^^}"
[ "$MODEL" = PRO ] || [ "$MODEL" = PLUS ] || { echo "Uso: sudo bash install.sh PRO|PLUS"; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
PLR="$HERE/../plr"
CFG=/home/mks/printer_data/config
MARK='#*# <---------------------- SAVE_CONFIG ---------------------->'

put() {  # put <src> <dest> <mode> <owner>
    [ -f "$2" ] && [ ! -f "$2.orig" ] && cp -p "$2" "$2.orig"
    install -m "$3" -o "$4" -g "$4" "$1" "$2"
    echo "  $2"
}

echo "Instalando Tortillery+ ($MODEL)..."
put "$HERE/tortillery-automount.sh" /usr/local/bin/tortillery-automount.sh 755 root
put "$HERE/mcu_update.sh"           /root/mcu_update.sh                    755 root
put "$HERE/usb/mount-usb.sh"        /usr/local/bin/mount-usb.sh            755 root
put "$HERE/usb/usb-auto-unmount-refresh.sh" /usr/local/bin/usb-auto-unmount-refresh.sh 755 root
put "$HERE/usb/usb-wifi.sh"         /opt/usb-wifi/usb-wifi.sh              755 root
put "$HERE/usb/99-custom-usb.rules" /etc/udev/rules.d/99-custom-usb.rules  644 root
# WiFi desde la pantalla: KlipperLCD (mks) solo puede ejecutar este script como root
put "$HERE/usb/tortillery-wifi.sh"  /usr/local/bin/tortillery-wifi.sh     755 root
SUDO_WIFI=$(mktemp)
{ echo 'mks ALL=(root) NOPASSWD: /usr/local/bin/tortillery-wifi.sh'
  echo 'mks ALL=(root) NOPASSWD: /usr/local/bin/tortillery-model.sh'; } > "$SUDO_WIFI"
visudo -cf "$SUDO_WIFI" >/dev/null && install -m 440 -o root -g root "$SUDO_WIFI" /etc/sudoers.d/tortillery-wifi \
    && echo "  /etc/sudoers.d/tortillery-wifi"
rm -f "$SUDO_WIFI"
udevadm control --reload-rules || true
# El USB ya flasheó la MCU y la pantalla al arrancar (paso 3, script de la imagen): el actualizador nuevo
# los da por hechos y no vuelve a flashearlos en el siguiente reinicio
mkdir -p /root/.tortillery
for pair in klipper.bin:mcu 800_480.tft:tft; do
    f="$HERE/../${pair%%:*}"
    [ -f "$f" ] && sha256sum "$f" | cut -d' ' -f1 > "/root/.tortillery/${pair##*:}.sha256" \
        && echo "  ${pair%%:*} del USB marcado como ya flasheado" || true
done
echo "Tortillery+ $VERSION" > /etc/tortillery-release
put "$PLR/plr.py"                   /home/mks/klipper/klippy/extras/plr.py 644 mks
put "$PLR/plr.cfg"                  "$CFG/plr.cfg"                         644 mks
put "$PLR/KlipperLCD/lcd.py"        /home/mks/KlipperLCD/lcd.py            644 mks
put "$PLR/KlipperLCD/main.py"       /home/mks/KlipperLCD/main.py           644 mks
put "$PLR/KlipperLCD/tortillery.py" /home/mks/KlipperLCD/tortillery.py     644 mks
put "$HERE/config/utilidades.cfg"   "$CFG/utilidades.cfg"                  644 mks
put "$HERE/config/kamp_tortillery.cfg" "$CFG/kamp_tortillery.cfg"         644 mks
put "$HERE/config/calibracion.cfg"  "$CFG/calibracion.cfg"                 644 mks
install -d -o mks -g mks "$CFG/extras"   # complementos de extras.sh (printer.cfg incluye extras/*.cfg)
put "$HERE/utils/tortillery-backup.sh"      /usr/local/bin/tortillery-backup.sh      755 root
put "$HERE/utils/tortillery-maintenance.sh" /usr/local/bin/tortillery-maintenance.sh 755 root
# Model templates stay in config/ so they can be renamed again later
for f in artillery_X4_PRO.cfg artillery_X4_PLUS.cfg macros_X4_PRO.cfg macros_X4_PLUS.cfg; do
    put "$HERE/config/$f" "$CFG/$f" 644 mks
done

# printer.cfg + macros.cfg del modelo, conservando la calibración (mismo script que usa el asistente de la pantalla)
put "$HERE/tortillery-model.sh"     /usr/local/bin/tortillery-model.sh     755 root
/usr/local/bin/tortillery-model.sh "$MODEL"

# Primer arranque de una imagen Tortillery+ (identidad propia, MCU_ID, firmware de la placa y la pantalla) y sellado
put "$HERE/firstboot/tortillery-firstboot.sh" /usr/local/bin/tortillery-firstboot.sh 755 root
put "$HERE/firstboot/tortillery-firstboot.service" /etc/systemd/system/tortillery-firstboot.service 644 root
put "$HERE/firstboot/tortillery-seal.sh" /usr/local/bin/tortillery-seal.sh 755 root
systemctl daemon-reload
systemctl enable tortillery-firstboot.service >/dev/null 2>&1   # no hace nada si ya se ejecutó (marca en /var/lib)
mkdir -p /var/lib/tortillery && touch /var/lib/tortillery/firstboot.done   # esta impresora ya está configurada
# firmware que grabará el primer arranque de una imagen sellada desde esta impresora
mkdir -p /opt/tortillery/firmware
for f in klipper.bin 800_480.tft; do
    [ -f "$HERE/../$f" ] && install -m 644 "$HERE/../$f" "/opt/tortillery/firmware/$f" && echo "  /opt/tortillery/firmware/$f"
done

# Cámara: crowsnest usa la webcam USB/USB-C que haya (no una fija) y Mainsail la ve sin configurar nada
SYS="$HERE/system"
put "$SYS/tortillery-camera.sh" /usr/local/bin/tortillery-camera.sh 755 root
put "$SYS/99-tortillery-camera.rules" /etc/udev/rules.d/99-tortillery-camera.rules 644 root
mkdir -p /etc/systemd/system/crowsnest.service.d /etc/systemd/system/klipper.service.d
put "$SYS/crowsnest-tortillery.conf" /etc/systemd/system/crowsnest.service.d/tortillery.conf 644 root
/usr/local/bin/tortillery-camera.sh
if ! grep -q '^\[webcam' "$CFG/moonraker.conf"; then
    printf '\n[webcam camara]\nservice: mjpegstreamer-adaptive\nstream_url: /webcam/?action=stream\nsnapshot_url: /webcam/?action=snapshot\n' \
        >> "$CFG/moonraker.conf"
    echo "  [webcam camara] anadida a moonraker.conf"
fi
# Klipper con prioridad sobre el resto y CPU siempre a su frecuencia (Armbian lee GOVERNOR al arrancar)
put "$SYS/klipper-tortillery.conf" /etc/systemd/system/klipper.service.d/tortillery.conf 644 root
if [ -f /etc/default/cpufrequtils ]; then
    sed -i 's/^GOVERNOR=.*/GOVERNOR=performance/' /etc/default/cpufrequtils
    for g in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; do echo performance > "$g" 2>/dev/null || true; done
    echo "  CPU en modo performance"
fi
# Copia automática de la config al cambiar printer.cfg (printer_data/backup y USB si está puesto)
put "$SYS/tortillery-backup.path" /etc/systemd/system/tortillery-backup.path 644 root
put "$SYS/tortillery-backup.service" /etc/systemd/system/tortillery-backup.service 644 root
systemctl daemon-reload
systemctl enable --now tortillery-backup.path >/dev/null 2>&1 && echo "  tortillery-backup.path activado"
# Watchdog: KlipperLCD se reinicia si se cuelga; la placa se reinicia si se cuelga el sistema
mkdir -p /etc/systemd/system/KlipperLCD.service.d /etc/systemd/system.conf.d
put "$SYS/klipperlcd-tortillery.conf" /etc/systemd/system/KlipperLCD.service.d/tortillery.conf 644 root
put "$SYS/watchdog-tortillery.conf" /etc/systemd/system.conf.d/tortillery-watchdog.conf 644 root
# Vigilancia con IA (no hace nada hasta rellenar config/tortillery_ai.cfg desde Mainsail)
put "$SYS/tortillery-ai.py" /usr/local/bin/tortillery-ai.py 755 root
put "$SYS/tortillery-ai.service" /etc/systemd/system/tortillery-ai.service 644 root
mkdir -p /usr/local/share/tortillery
install -m 644 "$SYS/tortillery_ai.cfg" /usr/local/share/tortillery/tortillery_ai.cfg
# Telegram also from the eMMC image (no USB needed): sudo tortillery-telegram <TOKEN>
install -m 644 "$HERE/config/telegram.conf" /usr/local/share/tortillery/telegram.conf
[ -f "$CFG/telegram.conf" ] && install -m 644 -o mks -g mks "$HERE/config/telegram.conf" "$CFG/telegram.conf"   # ya activado: avisos nuevos
install -m 755 "$HERE/telegram_setup.sh" /usr/local/bin/tortillery-telegram
# ...or editing config/telegram.cfg in Mainsail (tortillery-ai.service applies it)
install -m 644 "$SYS/telegram.cfg" /usr/local/share/tortillery/telegram.cfg
install -m 644 "$SYS/tortillery_release.pub" /usr/local/share/tortillery/tortillery_release.pub   # firma del USB
install -m 644 "$SYS/tortillery_allowed_signers" /usr/local/share/tortillery/tortillery_allowed_signers   # firma de versiones (Mainsail)
[ -f "$CFG/telegram.cfg" ] || install -m 644 -o mks -g mks "$SYS/telegram.cfg" "$CFG/telegram.cfg"
[ -f "$CFG/tortillery_ai.cfg" ] || install -m 644 -o mks -g mks "$SYS/tortillery_ai.cfg" "$CFG/tortillery_ai.cfg"
systemctl daemon-reload
systemctl enable tortillery-ai.service >/dev/null 2>&1 && echo "  tortillery-ai.service activado"
systemctl restart tortillery-ai.service 2>/dev/null || true

# Things that must not run in the middle of a print / are not used
for unit in unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer \
            openvpn.service rpcbind.service rpcbind.socket vnstat.service; do
    systemctl disable --now "$unit" >/dev/null 2>&1 && echo "  desactivado $unit" || true
done

# Kernel y arranque de la placa (mkspi) retenidos: una actualización de Armbian puede dejarla sin arrancar
KPKGS=$(dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' 'linux-image-*' 'linux-dtb-*' 'linux-u-boot-*' \
        'armbian-firmware*' 2>/dev/null | awk '$1 == "ii" {print $2}' || true)
if [ -n "$KPKGS" ]; then
    apt-mark hold $KPKGS >/dev/null && echo "  kernel retenido: $(echo $KPKGS)"
fi
# root ya no entra por SSH con contraseña (se usa mks + sudo)
if grep -q '^PermitRootLogin yes' /etc/ssh/sshd_config; then
    sed -i 's/^PermitRootLogin yes/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
    systemctl reload ssh 2>/dev/null || true
    echo "  SSH: root solo con clave (entra como mks)"
fi

# Moonraker: object labels on upload (EXCLUDE_OBJECT + adaptive mesh with any slicer)
if ! grep -q '^\[file_manager\]' "$CFG/moonraker.conf"; then
    [ -f "$CFG/moonraker.conf.orig" ] || cp -p "$CFG/moonraker.conf" "$CFG/moonraker.conf.orig"
    printf '\n[file_manager]\nenable_object_processing: True\n' >> "$CFG/moonraker.conf"
    echo "  [file_manager] enable_object_processing anadido a moonraker.conf"
fi

# Klipper, Moonraker y Mainsail desde Mainsail solo en versiones estables (la imagen traía channel: dev)
sed -i '/^\[update_manager\]$/,/^\[/ s/^channel: dev$/channel: stable/' "$CFG/moonraker.conf"
# Actualizar Tortillery+ desde Mainsail (Máquina > Actualizar): repo público, solo versiones etiquetadas (stable).
# Si el repo aún no existe o no hay internet, se salta: se reintenta al volver a ejecutar install.sh.
put "$HERE/utils/tortillery-update.sh" /usr/local/bin/tortillery-update.sh 755 root
put "$SYS/tortillery-update.path" /etc/systemd/system/tortillery-update.path 644 root
put "$SYS/tortillery-update.service" /etc/systemd/system/tortillery-update.service 644 root
REPO_DIR=/home/mks/tortillery
systemctl stop tortillery-update.path 2>/dev/null || true   # que tocar el repo aquí no lance una actualización
G="sudo -u mks env GIT_TERMINAL_PROMPT=0 git -C $REPO_DIR"
if [ ! -d "$REPO_DIR/.git" ] && sudo -u mks env GIT_TERMINAL_PROMPT=0 timeout 120 git clone -q "$REPO_URL" "$REPO_DIR" 2>/dev/null; then
    echo "  repo $REPO_URL en $REPO_DIR"
fi
# Moonraker necesita la rama main siguiendo a origin (no una etiqueta suelta, "HEAD desacoplado"): main se pone en la
# última versión estable y Mainsail ofrece las siguientes. Arregla también los repos de la 1.0.x.
if [ -d "$REPO_DIR/.git" ] && ! $G symbolic-ref -q HEAD >/dev/null; then
    $G checkout -q -B main origin/main
fi
if [ -d "$REPO_DIR/.git" ] && [ "$($G rev-parse HEAD)" = "$($G rev-parse origin/main)" ]; then
    TAG=$($G describe --tags --abbrev=0 2>/dev/null || true)
    [ -n "$TAG" ] && $G reset -q --hard "$TAG" && echo "  repo en $TAG (rama main)"
fi
if [ -d "$REPO_DIR/.git" ]; then
    if ! grep -q '^\[update_manager tortillery\]' "$CFG/moonraker.conf"; then
        printf '\n[update_manager tortillery]\ntype: git_repo\nchannel: stable\npath: %s\norigin: %s\nprimary_branch: main\nis_system_service: False\n' \
            "$REPO_DIR" "$REPO_URL" >> "$CFG/moonraker.conf"
        echo "  [update_manager tortillery] anadido a moonraker.conf"
    fi
    # no es un servicio que Moonraker deba reiniciar (lo aplica tortillery-update.path): sin el aviso de moonraker.asvc
    sed -i '/^\[update_manager tortillery\]$/,/^\[/{/^is_system_service:/d}' "$CFG/moonraker.conf"
    sed -i 's/^\[update_manager tortillery\]$/&\nis_system_service: False/' "$CFG/moonraker.conf"
    systemctl daemon-reload
    systemctl enable --now tortillery-update.path >/dev/null 2>&1 && echo "  tortillery-update.path activado"
else
    echo "  (sin repo $REPO_URL: actualizar desde Mainsail no se activa)"
fi

# Telegram: telegram.cfg next to this folder (TOKEN=..., CHAT_ID=... optional), like wifi.cfg
TG="$HERE/../telegram.cfg"
if [ -f "$TG" ]; then
    TOKEN=$(grep -i '^TOKEN=' "$TG" | cut -d= -f2- | tr -d '\r ')
    CHAT=$(grep -i '^CHAT_ID=' "$TG" | cut -d= -f2- | tr -d '\r ')
    bash "$HERE/telegram_setup.sh" "$TOKEN" "$CHAT" || echo "AVISO: Telegram no configurado (ver mensaje anterior)"
fi

sync
systemctl restart klipper KlipperLCD moonraker
systemctl restart crowsnest 2>/dev/null || true
echo "Listo. Log de actualizaciones USB: /var/log/tortillery-update.log"
