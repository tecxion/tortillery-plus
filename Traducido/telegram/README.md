<div align="center">

# 💬 Telegram in Tortillery+

**Creating the bot, setting the token and the ID, its commands and the notifications the printer sends**

[⬅️ Back to the README](../README.md) · [`telegram.cfg` example](../../ejemplos/telegram.cfg) · [🇪🇸 Español](../../telegram/README.md)

</div>

---

The printer messages you on Telegram when a print starts, finishes, pauses or fails, and you can send it commands from
your phone (`/foto`, `/reanudar`…). It only obeys **your** chat.

> [!NOTE]
> The printer's messages and the command names are in Spanish. The command table below explains each one.

## 1. Create the bot (token)

1. In Telegram, look for **[@BotFather](https://t.me/BotFather)** (the official one, with the blue tick) and tap
   _Start_.
2. Send it `/newbot`.
3. It asks for a **name**: what you'll see in the chat, for example `My X4 Pro`.
4. It asks for a **username**: it must end in `bot` and not be taken, for example `my_x4pro_bot`.
5. It replies with the **token**, a line like this:

   ```text
   123456789:AAH4k-ExAmPlE_tOkEn_DoNoTuSe
   ```

   Copy it. It's the bot's password: whoever has it can write as the bot. Don't share it or paste it in a log.

> [!IMPORTANT]
> **One bot per printer.** Telegram lets only one program read each bot's messages: with two printers (or an n8n,
> Home Assistant… webhook) on the same bot, notifications arrive but buttons and commands don't (`409 Conflict` in the
> log).

## 2. Put it on the printer

1. **Send any message to your new bot** (for example `hi`). That's how the printer learns which chat is yours.
2. In Mainsail › **Machine**, open `telegram.cfg` and paste the token:

   ```ini
   [telegram]
   token: 123456789:AAH4k-ExAmPlE_tOkEn_DoNoTuSe
   chat_id:
   ```

3. _Save_ (no restart needed). In under a minute you get **"✅ Tortillery+: avisos de impresión activados"**
   (notifications enabled) and the bot's commands show up in its **/** menu.

Other ways, if you don't use Mainsail:

- **From the USB stick**: a `telegram.cfg` file at the root of the stick ([example](../../ejemplos/usb/telegram.cfg))
  with `TOKEN=...` and `CHAT_ID=` (empty). `install.sh` reads it when installing from the stick.
- **Over SSH**: `sudo tortillery-telegram <TOKEN> [CHAT_ID]`.

## 3. The chat ID (`chat_id`)

Usually **you don't need it**: if you leave it empty, the printer takes the chat from the first message you sent the
bot (step 2.1). Set it by hand only if you want the notifications in another chat (a group, for example) or if the
"enabled" message never arrives.

**Your personal ID**:

1. Send a message to your bot.
2. Open this address in your browser, with your token:

   ```text
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

3. Look for `"chat":{"id":` and copy the number (for example `123456789`).

The **[@userinfobot](https://t.me/userinfobot)** bot also tells you when you message it.

**A group** (so more people can see it):

1. Add your bot to the group and write something like `/estado@my_x4pro_bot` in the group.
2. Open the same `getUpdates` address: the group `id` is **negative** (for example `-1001234567890`).
3. Put it in `telegram.cfg`:

   ```ini
   chat_id: -1001234567890
   ```

Commands are only accepted from that chat: in a group, anyone in the group can pause or cancel.

## 4. The commands

Type them in the bot's chat or pick them from the **/** menu next to the text box.

| Command      | What it does                                                                                    |
| ------------ | ----------------------------------------------------------------------------------------------- |
| `/foto`      | Camera photo with the status: file, %, minutes printing, layer and temperatures.                |
| `/estado`    | The same without the photo (status).                                                            |
| `/reanudar`  | Resumes a paused print. If the sensor sees no filament, it won't resume and tells you.          |
| `/cancelar`  | Cancels the print (running or paused).                                                         |
| `/enfriar`   | While paused: turns off the nozzle only (cool down). The bed stays hot so the part doesn't come loose; it heats up again on resume. |
| `/continuar` | After a power cut: continues the print where it was (heats, goes back to its spot and carries on). |
| `/descartar` | After a power cut: forgets the interrupted print (discard).                                     |
| `/ayuda`     | The list of commands (help).                                                                    |

### Command menu (/)

Since 1.1.5 the printer sets the menu by itself on startup. If your version is older, or you deleted it, set it by
hand:

1. In [@BotFather](https://t.me/BotFather): `/setcommands`.
2. Pick your bot.
3. Paste this text exactly (the descriptions can be in English, the command names can't):

   ```text
   foto - Camera photo and status
   estado - Print status
   reanudar - Resume the paused print
   cancelar - Cancel the print
   enfriar - Turn off the nozzle (paused, out of filament)
   continuar - Continue the print after a power cut
   descartar - Discard the print cut by the power loss
   ayuda - List of commands
   ```

   The printer sets the Spanish descriptions again when it restarts.

With `/setuserpic` in @BotFather you can give the bot a picture, and with `/setdescription` an intro text.

## 5. Notifications

| When                          | What you get                                                                                    |
| ----------------------------- | ----------------------------------------------------------------------------------------------- |
| A print starts                | ▶️ The file name.                                                                               |
| It pauses                     | ⏸️ Photo and buttons **Reanudar** (resume), **Cancelar** (cancel) and **Otra foto** (another photo). |
| The AI sees a failure         | 🤖 Photo, what it saw and the same buttons (with `accion: pausar` it's already paused).         |
| Out of filament               | 🧵 Photo and buttons **Enfriar** (cool down), **Reanudar** and **Cancelar**. Temperatures don't drop on their own. |
| Power comes back after a cut  | ⚡ When it went, how far the print got and buttons **Continuar** (continue) and **Descartar** (discard). |
| It's cancelled                | ⏹️ Also when you cancel from the screen.                                                        |
| It finishes                   | ✅ Photo and how long it took.                                                                  |
| Klipper error                 | ❌ The reason.                                                                                  |
| Timelapse (if installed)      | 🎬 The video.                                                                                   |
| Maintenance (every 200 h)     | 🔧 Grease the lead screws and check the belts.                                                  |

Telegram and the screen stay in step: if you continue a power cut from Telegram, the question disappears from the
screen, and the other way round.

On the screen, _Utilities › More… › Telegram QR_ shows a QR code that opens the bot on your phone.

## 6. Troubleshooting

| What happens                                        | What to do                                                                                      |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| "Activados" (enabled) never arrives                 | Send the bot a message and wait a minute. Check the token is complete, with no spaces.          |
| The log says Telegram rejected the token or the chat | Token copied wrong or wrong `chat_id`. Fix it in `telegram.cfg` and save.                      |
| Notifications arrive, but not the buttons or commands | Another program uses the same bot (`409 Conflict`). Use a bot of its own for this printer.   |
| No photos                                           | Check the camera shows in Mainsail.                                                             |
| A command does nothing                              | It only obeys the configured `chat_id`. In a group type `/command@bot_username`.                |

The Telegram (and AI) log: over SSH, `journalctl -u tortillery-ai -f`.

> [!WARNING]
> The token is stored in `telegram.cfg`: anyone with access to your Mainsail can see it. If it leaks, use `/revoke`
> in @BotFather to change it and put the new one in `telegram.cfg`.
