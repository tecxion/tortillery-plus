#!/bin/bash
# Complementos opcionales de Tortillery+ (fase 4). Se ejecutan por SSH cuando se quieran, uno a uno:
#   sudo bash extras.sh tailscale [CLAVE_AUTH]  -> acceso remoto seguro (Mainsail y SSH desde fuera de casa)
#   bash extras.sh octoeverywhere               -> acceso remoto, avisos y cámara desde la app (SIN sudo)
#   sudo bash extras.sh timelapse               -> vídeos timelapse de cada impresión (necesita cámara)
#   bash extras.sh shaketune                    -> gráficas de correas y vibraciones (Shake&Tune) en Mainsail (SIN sudo)
#   bash extras.sh mobileraker                  -> avisos push en la app Mobileraker (Android/iOS) (SIN sudo)
# Volver a ejecutar uno ya instalado no rompe nada (solo actualiza).
set -e
CFG=/home/mks/printer_data/config
MOON="$CFG/moonraker.conf"
need_root() { [ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo: sudo bash $0 $1"; exit 1; }; }
add_section() {  # add_section <nombre> <texto>: añade la sección a moonraker.conf si no está
    grep -q "^\[$1\]" "$MOON" && return 0
    [ -f "$MOON.orig" ] || cp -p "$MOON" "$MOON.orig"
    printf '\n%s\n' "$2" >> "$MOON"
    echo "  [$1] anadido a moonraker.conf"
}

case "$1" in
tailscale)
    need_root tailscale
    command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
    systemctl enable --now tailscaled
    # Moonraker debe confiar en la red de Tailscale (100.64.0.0/10) o Mainsail no conecta desde fuera
    if grep -q '^trusted_clients:' "$MOON" && ! grep -q '100.64.0.0/10' "$MOON"; then
        [ -f "$MOON.orig" ] || cp -p "$MOON" "$MOON.orig"
        sed -i '/^trusted_clients:/a\    100.64.0.0/10' "$MOON"
        echo "  100.64.0.0/10 anadido a trusted_clients"
        systemctl restart moonraker
    fi
    echo "Abre el enlace que sale a continuacion para iniciar sesion en Tailscale (o pasa una clave de autenticacion)."
    tailscale up --hostname=tortillery ${2:+--authkey="$2"}
    echo "Listo. Mainsail desde fuera: http://$(tailscale ip -4 | head -n1)  (con la app de Tailscale en el movil/PC)"
    ;;
octoeverywhere)
    # Su instalador pide sudo cuando lo necesita y debe ejecutarse como el usuario de Klipper (mks)
    [ "$(id -u)" != 0 ] || { echo "Ejecutalo SIN sudo (como mks): bash $0 octoeverywhere"; exit 1; }
    if [ -d ~/octoeverywhere/.git ]; then
        git -C ~/octoeverywhere pull --ff-only
    else
        git clone https://github.com/QuinnDamerell/OctoPrint-OctoEverywhere.git ~/octoeverywhere
    fi
    cd ~/octoeverywhere && ./install.sh   # muestra el enlace para vincular la impresora a tu cuenta
    ;;
timelapse)
    need_root timelapse
    ls /dev/video* >/dev/null 2>&1 || echo "AVISO: no se ve ninguna camara (/dev/video*). Se instala igualmente."
    command -v ffmpeg >/dev/null || apt-get install -y ffmpeg
    [ -d /home/mks/moonraker/moonraker/components ] || { echo "No encuentro Moonraker en /home/mks/moonraker"; exit 1; }
    REPO=/home/mks/moonraker-timelapse
    if [ -d "$REPO/.git" ]; then
        sudo -u mks git -C "$REPO" pull --ff-only
    else
        sudo -u mks git clone https://github.com/mainsail-crew/moonraker-timelapse.git "$REPO"
    fi
    # lo mismo que su 'make install': el componente dentro de Moonraker y las macros en la config
    sudo -u mks ln -sf "$REPO/component/timelapse.py" /home/mks/moonraker/moonraker/components/timelapse.py
    sudo -u mks mkdir -p "$CFG/extras" /home/mks/printer_data/timelapse
    sudo -u mks ln -sf "$REPO/klipper_macro/timelapse.cfg" "$CFG/extras/timelapse.cfg"   # printer.cfg incluye extras/*.cfg
    add_section timelapse "[timelapse]
output_path: ~/printer_data/timelapse/
frame_path: /tmp/timelapse/printer"
    add_section "update_manager timelapse" "[update_manager timelapse]
type: git_repo
primary_branch: main
path: ~/moonraker-timelapse
origin: https://github.com/mainsail-crew/moonraker-timelapse.git
managed_services: klipper moonraker"
    systemctl restart moonraker klipper
    echo "Listo. En el laminador, G-code de cambio de capa: TIMELAPSE_TAKE_FRAME"
    echo "(OrcaSlicer: Impresora > G-code de maquina > 'Antes del cambio de capa'). Videos en Mainsail > Timelapse."
    ;;
shaketune)
    # Klippain Shake&Tune: AXES_SHAPER_CALIBRATION, COMPARE_BELTS_RESPONSES... con gráficas (usa el ADXL345 del
    # cabezal). Su instalador clona el repo, lo enlaza en Klipper y añade su [update_manager]; corre como mks.
    [ "$(id -u)" != 0 ] || { echo "Ejecutalo SIN sudo (como mks): bash $0 shaketune"; exit 1; }
    wget -O - https://raw.githubusercontent.com/Frix-x/klippain-shaketune/main/install.sh | bash
    mkdir -p "$CFG/extras"
    # printer.cfg incluye extras/*.cfg
    [ -f "$CFG/extras/shaketune.cfg" ] || cat > "$CFG/extras/shaketune.cfg" <<'EOF'
[shaketune]
result_folder: ~/printer_data/config/ShakeTune_results
number_of_results_to_keep: 3
EOF
    sudo systemctl restart klipper
    echo "Listo. En Mainsail: COMPARE_BELTS_RESPONSES (correas) y AXES_SHAPER_CALIBRATION; las graficas quedan en"
    echo "config/ShakeTune_results."
    ;;
mobileraker)
    # Mobileraker Companion: manda los avisos push de la app (progreso, fin, errores) aunque la app esté cerrada.
    # Su instalador crea el servicio y su [update_manager]; corre como mks y pide sudo cuando lo necesita.
    [ "$(id -u)" != 0 ] || { echo "Ejecutalo SIN sudo (como mks): bash $0 mobileraker"; exit 1; }
    REPO=/home/mks/mobileraker_companion
    if [ -d "$REPO/.git" ]; then git -C "$REPO" pull --ff-only; else
        git clone https://github.com/Clon1998/mobileraker_companion.git "$REPO"; fi
    bash "$REPO/scripts/install.sh"
    echo "Listo. Instala Mobileraker en el movil, anade la impresora (http://<IP>) y activa las notificaciones."
    ;;
*)
    echo "Uso: sudo bash $0 tailscale [CLAVE_AUTH] | bash $0 octoeverywhere | sudo bash $0 timelapse | bash $0 shaketune | bash $0 mobileraker"
    exit 2
    ;;
esac
