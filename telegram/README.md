<div align="center">

# 💬 Telegram en Tortillery+

**Crear el bot, ponerle el token y el ID, sus órdenes y los avisos que manda la impresora**

[⬅️ Volver al README](../README.md) · [Ejemplo de `telegram.cfg`](../ejemplos/telegram.cfg) · [🇬🇧 English](../Traducido/telegram/README.md)

</div>

---

La impresora te escribe por Telegram cuando empieza, termina, se pausa o falla una impresión, y le puedes mandar
órdenes desde el móvil (`/foto`, `/reanudar`…). Solo obedece a **tu** chat.

## 1. Crear el bot (token)

1. En Telegram, busca **[@BotFather](https://t.me/BotFather)** (el oficial, con la marca azul) y pulsa _Iniciar_.
2. Escríbele `/newbot`.
3. Te pide un **nombre**: el que verás en el chat, por ejemplo `Mi X4 Pro`.
4. Te pide un **usuario**: tiene que acabar en `bot` y no estar cogido, por ejemplo `mi_x4pro_bot`.
5. Te contesta con el **token**, una línea así:

   ```text
   123456789:AAH4k-EjEmPlO_dE_tOkEn_NoLoUsEs
   ```

   Cópialo. Es la contraseña del bot: quien lo tenga puede escribir como él. No lo compartas ni lo pegues en un log.

> [!IMPORTANT]
> **Un bot por impresora.** Telegram solo deja a un programa leer los mensajes de cada bot: con dos impresoras (o un
> webhook de n8n, Home Assistant…) en el mismo bot, los avisos llegan pero los botones y las órdenes no
> (`409 Conflict` en el log).

## 2. Ponerlo en la impresora

1. **Mándale cualquier mensaje a tu bot nuevo** (por ejemplo `hola`). Así la impresora sabe cuál es tu chat.
2. En Mainsail › **Máquina**, abre `telegram.cfg` y pega el token:

   ```ini
   [telegram]
   token: 123456789:AAH4k-EjEmPlO_dE_tOkEn_NoLoUsEs
   chat_id:
   ```

3. _Guardar_ (no hace falta reiniciar). En menos de un minuto te llega **"✅ Tortillery+: avisos de impresión
   activados"** y en el menú **/** del bot aparecen sus órdenes.

Otras formas, si no usas Mainsail:

- **Desde el USB**: un archivo `telegram.cfg` en la raíz del pendrive ([ejemplo](../ejemplos/usb/telegram.cfg)) con
  `TOKEN=...` y `CHAT_ID=` (vacío). Lo lee `install.sh` al instalar desde el USB.
- **Por SSH**: `sudo tortillery-telegram <TOKEN> [CHAT_ID]`.

## 3. El ID del chat (`chat_id`)

Normalmente **no hace falta**: si lo dejas vacío, la impresora coge el chat del primer mensaje que le mandaste al bot
(paso 2.1). Ponlo a mano solo si quieres los avisos en otro chat (un grupo, por ejemplo) o si no llega el mensaje de
"activados".

**Tu ID personal**:

1. Mándale un mensaje a tu bot.
2. Abre en el navegador, con tu token:

   ```text
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

3. Busca `"chat":{"id":` y copia el número (por ejemplo `123456789`).

También te lo da el bot **[@userinfobot](https://t.me/userinfobot)** al escribirle.

**Un grupo** (para que lo vea más gente):

1. Añade tu bot al grupo y escribe en el grupo algo como `/estado@mi_x4pro_bot`.
2. Abre la misma dirección `getUpdates`: el `id` del grupo es **negativo** (por ejemplo `-1001234567890`).
3. Ponlo en `telegram.cfg`:

   ```ini
   chat_id: -1001234567890
   ```

Las órdenes solo se aceptan desde ese chat: en un grupo, cualquiera del grupo puede pausar o cancelar.

## 4. Las órdenes

Escríbelas en el chat del bot o elígelas en el menú **/**, junto al cuadro de texto.

| Orden        | Qué hace                                                                                        |
| ------------ | ----------------------------------------------------------------------------------------------- |
| `/foto`      | Foto de la cámara con el estado: archivo, %, minutos imprimiendo, capa y temperaturas.          |
| `/estado`    | Lo mismo sin foto.                                                                              |
| `/reanudar`  | Reanuda la impresión en pausa. Si el sensor no detecta filamento, no reanuda y te lo dice.      |
| `/cancelar`  | Cancela la impresión (en marcha o en pausa).                                                    |
| `/enfriar`   | En pausa: apaga solo la boquilla. La cama sigue caliente para que la pieza no se despegue; al reanudar se vuelve a calentar. |
| `/continuar` | Tras un corte de luz: sigue la impresión por donde iba (calienta, vuelve a su sitio y sigue).   |
| `/descartar` | Tras un corte de luz: olvida la impresión cortada.                                              |
| `/ayuda`     | La lista de órdenes.                                                                            |

### Menú de órdenes (/)

Desde la 1.1.5 la impresora pone el menú sola al arrancar. Si tu versión es anterior, o lo borraste, ponlo a mano:

1. En [@BotFather](https://t.me/BotFather): `/setcommands`.
2. Elige tu bot.
3. Pega este texto tal cual:

   ```text
   foto - Foto de la cámara y estado
   estado - Cómo va la impresión
   reanudar - Reanudar la impresión en pausa
   cancelar - Cancelar la impresión
   enfriar - Apagar la boquilla (en pausa, sin filamento)
   continuar - Seguir la impresión tras un corte de luz
   descartar - Descartar la impresión cortada por la luz
   ayuda - Lista de órdenes
   ```

Con `/setuserpic` en @BotFather le puedes poner una foto al bot, y con `/setdescription` un texto de presentación.

## 5. Los avisos

| Cuándo                        | Qué llega                                                                                       |
| ----------------------------- | ----------------------------------------------------------------------------------------------- |
| Empieza una impresión         | ▶️ Nombre del archivo.                                                                          |
| Se pausa                      | ⏸️ Foto y botones **Reanudar**, **Cancelar** y **Otra foto**.                                   |
| La IA ve un fallo             | 🤖 Foto, qué ha visto y los mismos botones (con `accion: pausar`, ya está en pausa).            |
| Se queda sin filamento        | 🧵 Foto y botones **Enfriar**, **Reanudar** y **Cancelar**. Las temperaturas no bajan solas.    |
| Vuelve la luz tras un corte   | ⚡ Cuándo se fue, por dónde iba y botones **Continuar** y **Descartar**.                        |
| Se cancela                    | ⏹️ También si cancelas desde la pantalla.                                                       |
| Termina                       | ✅ Foto y el tiempo que ha tardado.                                                             |
| Error de Klipper              | ❌ El motivo.                                                                                   |
| Timelapse (si lo instalaste)  | 🎬 El vídeo.                                                                                    |
| Mantenimiento (cada 200 h)    | 🔧 Engrasar husillos y revisar correas.                                                         |

Lo que pulses en Telegram y en la pantalla va a la par: si continúas un corte desde Telegram, la pregunta desaparece de
la pantalla, y al revés.

En la pantalla, _Utilidades › Más… › QR de Telegram_ enseña un QR que abre el bot en el móvil.

## 6. Si algo no va

| Lo que pasa                                         | Qué hacer                                                                                       |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| No llega "avisos activados"                         | Mándale un mensaje al bot y espera un minuto. Revisa que el token esté entero, sin espacios.    |
| El log dice que Telegram rechazó el token o el chat | Token mal copiado o `chat_id` equivocado. Corrígelo en `telegram.cfg` y guarda.                 |
| Llegan los avisos, pero no los botones ni las órdenes | Otro programa usa el mismo bot (`409 Conflict`). Usa un bot propio para esta impresora.      |
| No llegan las fotos                                 | Comprueba que la cámara se ve en Mainsail.                                                      |
| La orden no hace nada                               | Solo obedece al `chat_id` configurado. En un grupo escribe `/orden@usuario_del_bot`.            |

El log de Telegram (y de la IA): por SSH, `journalctl -u tortillery-ai -f`.

> [!WARNING]
> El token queda en `telegram.cfg`: cualquiera con acceso a tu Mainsail puede verlo. Si se filtra, en @BotFather usa
> `/revoke` para cambiarlo y pon el nuevo en `telegram.cfg`.
