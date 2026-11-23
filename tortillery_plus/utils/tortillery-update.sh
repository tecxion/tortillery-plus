#!/bin/bash
# Tortillery+: Mainsail actualizó ~/tortillery ([update_manager tortillery]) -> instala la última versión FIRMADA con el
# modelo de esta impresora. Lo lanza tortillery-update.path.
# Seguridad: ~/tortillery es de mks y root NUNCA ejecuta nada de ahí ni corre git dentro. Root tiene su propia copia
# (/opt/tortillery/repo) bajada de GitHub, comprueba la firma de la etiqueta con la clave pública de Tortillery+ y solo
# entonces ejecuta su install.sh. Una etiqueta sin firma válida no se instala.
URL=${TORTILLERY_URL:-https://github.com/tecxion/tortillery-plus.git}
DIR=${TORTILLERY_DIR:-/opt/tortillery/repo}
SIGNERS=${TORTILLERY_SIGNERS:-/usr/local/share/tortillery/tortillery_allowed_signers}
DONE=${TORTILLERY_DONE:-/opt/tortillery/installed_tag}
MODEL_FILE=${TORTILLERY_MODEL_FILE:-/etc/tortillery-model}
exec >> "${TORTILLERY_LOG:-/var/log/tortillery-update.log}" 2>&1
log() { echo "[$(date '+%F %T')] [Tortillery] $*"; }
G() { git -C "$DIR" -c gpg.ssh.allowedSignersFile="$SIGNERS" -c advice.detachedHead=false "$@"; }

if [ ! -d "$DIR/.git" ]; then
    mkdir -p "$(dirname "$DIR")"
    git clone -q --no-checkout "$URL" "$DIR" || { log "no se pudo descargar $URL"; exit 1; }
fi
G fetch -q --tags --force origin || { log "sin conexión con $URL"; exit 1; }
TAG=$(G tag -l 'v*' --sort=-v:refname | head -1)
[ -n "$TAG" ] || { log "no hay versiones en $URL"; exit 1; }
[ "$TAG" = "$(cat "$DONE" 2>/dev/null)" ] && { log "$TAG ya instalada"; exit 0; }
G verify-tag "$TAG" || { log "ERROR: $TAG no tiene una firma válida de Tortillery+: no se instala"; exit 1; }

# Nunca imprimiendo: espera a que termine (Moonraker ya no actualiza imprimiendo, pero por si acaso)
while curl -s -m 5 'http://127.0.0.1:7125/printer/objects/query?print_stats' | grep -q '"state": *"\(printing\|paused\)"'; do
    sleep 60
done
MODEL=$(cat "$MODEL_FILE" 2>/dev/null)
[ -n "$MODEL" ] || { log "Sin $MODEL_FILE: elige el modelo en la pantalla primero"; exit 1; }
G checkout -q --force "$TAG" && G clean -qfdx || { log "ERROR: no se pudo preparar $TAG"; exit 1; }
log "instalando $TAG (firma comprobada) para $MODEL"
bash "$DIR/tortillery_plus/install.sh" "$MODEL" && echo "$TAG" > "$DONE" && log "$TAG instalada"
