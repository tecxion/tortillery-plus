#!/bin/bash
# Activa los avisos de Telegram (inicio, fin y error de impresion).
# Uso:  sudo bash telegram_setup.sh <TOKEN_DEL_BOT> [CHAT_ID]
#  - TOKEN: crealo hablando con @BotFather en Telegram (/newbot).
#  - CHAT_ID: si no lo sabes, omitelo: antes envia cualquier mensaje a tu bot y el script lo detecta.
set -e
[ "$(id -u)" = 0 ] || { echo "Ejecuta con sudo"; exit 1; }
TOKEN="$1"; CHAT="$2"
[ -n "$TOKEN" ] || { echo "Uso: sudo bash telegram_setup.sh <TOKEN> [CHAT_ID]"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
CFG=/home/mks/printer_data/config
SECRETS=/home/mks/printer_data/moonraker.secrets
API="https://api.telegram.org/bot$TOKEN"

if [ -z "$CHAT" ]; then
    CHAT=$(curl -s -m 15 "$API/getUpdates" | python3 -c '
import sys, json
ids = [u[k]["chat"]["id"] for u in json.load(sys.stdin).get("result", [])
       for k in ("message", "channel_post", "my_chat_member") if k in u]
print(ids[-1] if ids else "")')
    [ -n "$CHAT" ] || { echo "No encuentro el chat: envia un mensaje a tu bot y vuelve a ejecutarlo"; exit 1; }
fi

# The test message checks token and chat before saving anything
curl -sf -m 15 "$API/sendMessage" -d chat_id="$CHAT" \
     --data-urlencode text="✅ Tortillery+: avisos de impresión activados" >/dev/null \
    || { echo "Telegram rechazo el token o el chat ($CHAT)"; exit 1; }

# Token only in moonraker.secrets (600), never in the config files Mainsail shows/backs up
python3 - "$SECRETS" "tgram://$TOKEN/$CHAT" <<'EOF'
import sys, configparser
path, url = sys.argv[1:]
c = configparser.ConfigParser(interpolation=None)
c.read(path)
if not c.has_section("telegram"):
    c.add_section("telegram")
c.set("telegram", "url", url)
with open(path, "w") as f:
    c.write(f)
EOF
chown mks:mks "$SECRETS"; chmod 600 "$SECRETS"

CONF="$HERE/config/telegram.conf"
[ -f "$CONF" ] || CONF=/usr/local/share/tortillery/telegram.conf   # instalado como tortillery-telegram
install -m 644 -o mks -g mks "$CONF" "$CFG/telegram.conf"
grep -q '^\[include telegram.conf\]' "$CFG/moonraker.conf" \
    || printf '\n[include telegram.conf]\n' >> "$CFG/moonraker.conf"
systemctl restart moonraker
echo "Avisos de Telegram activados (chat $CHAT)."
