# 📂 Ejemplos comentados / Commented examples

Archivos de ejemplo con cada opción explicada en español y en inglés. Ábrelos, copia lo que necesites y pégalo en tu
impresora (Mainsail › **Máquina**). Cómo funciona cada archivo: [Personalizar la impresora](../printer/README.md).

_Example files with every option explained in Spanish and English. Open them, copy what you need and paste it on your
printer (Mainsail › **Machine**). How each file works: [Customising the printer](../Traducido/printer/README.md)._

| Ejemplo / Example                                | Dónde va en la impresora / Where it goes on the printer         | Para qué / What for                                      |
| ------------------------------------------------ | --------------------------------------------------------------- | -------------------------------------------------------- |
| [`ajustes/mis_ajustes.cfg`](ajustes/mis_ajustes.cfg) | `config/ajustes/mis_ajustes.cfg` (archivo nuevo / new file) | Tus cambios de Klipper, que no se pierden al actualizar. _Your Klipper changes, kept on update._ |
| [`tortillery_ai.cfg`](tortillery_ai.cfg)         | `config/tortillery_ai.cfg`                                      | Vigilancia con IA, con un ejemplo por proveedor. _AI monitoring, one example per provider._ |
| [`telegram.cfg`](telegram.cfg)                   | `config/telegram.cfg`                                           | Bot de Telegram. _Telegram bot._                         |
| [`moonraker.conf`](moonraker.conf)               | `config/moonraker.conf` (solo el fragmento / only the snippet) | Acceso desde otra red, cámaras… _Remote network access, cameras…_ |
| [`crowsnest.conf`](crowsnest.conf)               | `config/crowsnest.conf` (solo el fragmento / only the snippet) | Resolución y fps de la cámara. _Camera resolution and fps._ |
| [`laminador.txt`](laminador.txt)                 | En el laminador / In the slicer                                 | G-code de inicio y fin (OrcaSlicer, Cura). _Start and end G-code._ |
| [`usb/wifi.cfg`](usb/wifi.cfg)                   | Raíz del pendrive / Root of the USB stick                       | Conectar el WiFi al arrancar con el USB. _WiFi when booting with the stick._ |
| [`usb/telegram.cfg`](usb/telegram.cfg)           | Raíz del pendrive / Root of the USB stick                       | Telegram al instalar desde el USB. _Telegram when installing from the stick._ |

> [!TIP]
> En los `.cfg` y `.conf`, una línea que empieza por `#` no hace nada. Para usar una opción, quítale la `#` a la
> sección (`[printer]`) y a la opción (`max_velocity: 500`).
>
> _In `.cfg` and `.conf` files, a line starting with `#` does nothing. To use an option, remove the `#` from the section
> (`[printer]`) and from the option (`max_velocity: 500`)._

> [!WARNING]
> No copies un ejemplo entero encima de tu `moonraker.conf` o `crowsnest.conf`: copia solo el fragmento. Y no pegues
> nunca tu token ni tu `api_key` en un archivo que vayas a compartir.
>
> _Don't paste a whole example over your `moonraker.conf` or `crowsnest.conf`: copy only the snippet. And never put
> your token or `api_key` in a file you are going to share._
