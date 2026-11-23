#!/bin/bash
# Tortillery+: Mainsail actualizó el repo (~/tortillery, [update_manager tortillery]) -> aplica la versión nueva con
# install.sh del propio repo y el modelo de esta impresora. Lo lanza tortillery-update.path.
# Nunca imprimiendo: espera a que termine (Moonraker ya no actualiza imprimiendo, pero por si acaso).
REPO=/home/mks/tortillery
exec >> /var/log/tortillery-update.log 2>&1
echo "[$(date '+%F %T')] [Tortillery] repo actualizado: $(git -C "$REPO" describe --tags --always 2>/dev/null)"
while curl -s -m 5 'http://127.0.0.1:7125/printer/objects/query?print_stats' | grep -q '"state": *"\(printing\|paused\)"'; do
    sleep 60
done
MODEL=$(cat /etc/tortillery-model 2>/dev/null)
[ -n "$MODEL" ] || { echo "Sin /etc/tortillery-model: elige el modelo en la pantalla primero"; exit 1; }
bash "$REPO/tortillery_plus/install.sh" "$MODEL"
