<div align="center">

# 🔌 Instalar Tortillery+ sin adaptador de eMMC

**Para impresoras con el sistema de fábrica de Artillery: graba la imagen en la eMMC desde la propia impresora**

[⬅️ Volver al README](../README.md) · [🇬🇧 English](../Traducido/Actualizar%20sin%20adaptador/README.md)

</div>

---

> [!NOTE]
> **De dónde sale esta guía.** Todo el método es de **Mustafa Yücel**, que lo publicó en turco el 12 de octubre de 2026 y
> lo probó en una X4 Pro con la imagen de la Tortillery original:
> **[Artillery Sidewinder X4 Pro ve X4 Plus için Adaptörsüz Tortillery Kurulumu](https://yucellmustafa.com.tr/blog/swx4-tortillery)**.
> Aquí solo está traducido y adaptado a la imagen de Tortillery+. Todo el mérito es suyo; si algo no cuadra, manda su
> guía.

> [!CAUTION]
> ## ⚠️ Lee esto antes de empezar
>
> Es un método **avanzado y con riesgo real de dejar la impresora sin arrancar**. Si tienes un lector de eMMC, usa la
> [instalación normal](../README.md#-instalación): es más sencilla y segura.
>
> - **Borra la eMMC entera.** El comando `dd` del paso 10 escribe encima de todo el sistema que tiene la impresora.
> - **Un disco equivocado lo rompe todo.** Si confundes `/dev/mmcblk1` (la eMMC) con `/dev/sda` (el pendrive), o al
>   revés, puedes borrar lo que no querías. `dd` no pregunta ni avisa. Comprueba los nombres con `lsblk` en cada paso.
> - **No cortes la luz** mientras se escribe la eMMC o se graba la placa. Si se corta a medias, la impresora puede no
>   volver a arrancar y solo se arregla con un lector de eMMC.
> - **Tocas el arranque de la impresora** (`extlinux.conf`). Una línea mal escrita puede dejarla sin arrancar. Guarda
>   la copia del paso 2.
> - **La copia de seguridad no lo guarda todo.** El paso 8 copia el sistema de la eMMC, pero no el firmware de la placa
>   ni el de la pantalla. Además, volver atrás con esa copia no lo ha probado nadie.
> - **Solo para el sistema de fábrica de Artillery**, el que arranca con `/boot/extlinux/extlinux.conf`. **No lo uses
>   si tu impresora ya tiene la Tortillery o Tortillery+**: esas arrancan de otra forma y tienen los mismos
>   identificadores de disco que el pendrive. Para ellas, actualiza [desde Mainsail o por USB](../README.md#-actualizar).
> - **Solo está probado en una X4 Pro**, por el autor y con la Tortillery original. En la X4 Plus y con la imagen de
>   Tortillery+ no está probado.
> - Lo haces **bajo tu responsabilidad**.

## 1. Qué necesitas

- La impresora encendida con su sistema de fábrica y sin imprimir, sin mover ejes ni calentar.
- Un PC con Windows y un cable **USB-C de datos**, no solo de carga, para la consola serie de la placa.
- Un **pendrive de 64 GB** que puedas borrar.
- [PuTTY](https://www.putty.org/) para la consola serie, [balenaEtcher](https://etcher.balena.io/) para grabar el
  pendrive y [WinSCP](https://winscp.net/) o `scp` para pasar la imagen por WiFi.
- La imagen `Tortillery+_1.1.5.img` de la [descarga](../README.md#-descarga).

Nombres de los discos en la impresora (compruébalos siempre con `lsblk`):

| Disco            | Qué es                                                |
| ---------------- | ----------------------------------------------------- |
| `/dev/mmcblk1`   | la eMMC de la impresora (7 818 182 656 bytes)         |
| `/dev/mmcblk1p1` | arranque de la eMMC (256 MB)                          |
| `/dev/mmcblk1p2` | sistema de la eMMC                                    |
| `/dev/sda`       | el pendrive                                           |
| `/dev/sda1`      | arranque del pendrive                                 |
| `/dev/sda2`      | sistema del pendrive (lo agrandas en el paso 7)       |

En `dd`, `if=` es lo que se lee y `of=` es lo que **se borra y se sobrescribe**.

## 2. Consola serie

1. Conecta el PC a la impresora con el cable USB-C. En el _Administrador de dispositivos_ de Windows mira qué puerto
   COM le da. Si no aparece, instala el driver CH341.
2. En PuTTY: _Serial_, ese puerto COM, velocidad **1500000**, 8 bits de datos, 1 de parada, sin paridad y sin control
   de flujo.
3. Entra con el usuario y la contraseña de tu sistema (en el de fábrica, normalmente `mks` / `makerbase`) y mira cómo
   está:

   ```bash
   lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT
   findmnt /
   findmnt /boot
   cat /boot/extlinux/extlinux.conf
   sudo blockdev --getsize64 /dev/mmcblk1
   ```

   `/` tiene que estar en `/dev/mmcblk1p2` y la eMMC tiene que medir **7818182656**. **Si no existe
   `/boot/extlinux/extlinux.conf` o el tamaño es otro, para aquí:** esta guía no vale para tu impresora.

4. Guarda una copia del arranque:

   ```bash
   sudo cp -n /boot/extlinux/extlinux.conf /boot/extlinux/extlinux.conf.backup
   ```

## 3. Graba la imagen en el pendrive

1. En PowerShell, apunta la huella de la imagen. Debe coincidir con el `.sha256` que la acompaña:

   ```powershell
   Get-FileHash -Algorithm SHA256 "C:\ruta\Tortillery+_1.1.5.img"
   ```

2. Con balenaEtcher graba la imagen **en el pendrive**. Comprueba bien el tamaño del disco de destino antes de pulsar
   _Flash_. Si después Windows pide formatear el pendrive, **cancela**.
3. Pon el pendrive en la impresora, que sigue encendida con su sistema. **No la reinicies todavía.**

La imagen de Tortillery+ tiene estos identificadores, los mismos que usaba la guía original:

| Partición   | Tipo  | Etiqueta     | UUID                                   |
| ----------- | ----- | ------------ | -------------------------------------- |
| `/dev/sda1` | vfat  | `armbi_boot` | `35AE-B672`                            |
| `/dev/sda2` | ext4  | `armbi_root` | `f68704c3-ba62-4911-a703-ecf77de52d7a` |

Compruébalo con `lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT`.

## 4. Monta el pendrive para leerlo

Si la impresora montó el pendrive sola, este bloque lo desmonta y vuelve a montar las dos particiones, solo para
leer. Cópialo **entero**:

```bash
(
set -e
test "$(findmnt -n -o SOURCE /)" = "/dev/mmcblk1p2"
if findmnt -rn -S /dev/sda1 >/dev/null; then
    sudo umount /dev/sda1
fi
if findmnt -rn -S /dev/sda2 >/dev/null; then
    sudo umount /dev/sda2
fi
sudo mkdir -p /mnt/tortillery-boot /mnt/tortillery-root
sudo mount -o ro /dev/sda1 /mnt/tortillery-boot
sudo mount -o ro /dev/sda2 /mnt/tortillery-root
)
```

Comprueba que están los archivos de arranque y que queda sitio en el arranque de la eMMC (hacen falta unos 52 MB):

```bash
ls -lh /mnt/tortillery-boot/Image /mnt/tortillery-boot/uInitrd /mnt/tortillery-boot/dtb/rockchip/rk3328-mkspi.dtb
cat /mnt/tortillery-root/etc/fstab
df -h /boot
```

Si te sale `already mounted` o no ves los archivos, mira [Si algo falla](#12-si-algo-falla).

## 5. Añade el arranque desde el pendrive

Copia el núcleo del pendrive al arranque de la eMMC:

```bash
sudo mkdir -p /boot/tortillery-usb
sudo cp /mnt/tortillery-boot/Image /boot/tortillery-usb/
sudo cp /mnt/tortillery-boot/uInitrd /boot/tortillery-usb/
sudo cp /mnt/tortillery-boot/dtb/rockchip/rk3328-mkspi.dtb /boot/tortillery-usb/
```

Abre el arranque con `sudo nano /boot/extlinux/extlinux.conf`. **Sin borrar lo que hay**, deja una sola línea
`TIMEOUT` y una sola `DEFAULT` y añade la entrada `TortilleryUSB`:

```text
TIMEOUT 600
DEFAULT Armbian
MENU TITLE Boot Menu
label TortilleryUSB
  kernel /tortillery-usb/Image
  initrd /tortillery-usb/uInitrd
  fdt /tortillery-usb/rk3328-mkspi.dtb
  append root=UUID=f68704c3-ba62-4911-a703-ecf77de52d7a rootwait rootfstype=ext4 rw console=tty1 console=ttyS2,1500000 consoleblank=0 loglevel=4
```

- `DEFAULT` tiene que ser la etiqueta (`label`) de la entrada que ya tenías, aquí `Armbian`. Así, si no eliges nada,
  arranca el sistema de siempre.
- La línea `append` va **en una sola línea**.
- `TIMEOUT 600` te da 60 segundos para elegir en el menú.

Guarda (Ctrl+O, Intro, Ctrl+X) y comprueba:

```bash
sync
cat /boot/extlinux/extlinux.conf
ls -lh /boot/tortillery-usb/
```

## 6. Arranca desde el pendrive

```bash
sudo poweroff
```

Cuando se apague, apaga y enciende la impresora con el interruptor. Vuelve a abrir PuTTY (_Restart Session_). En el
menú escribe el número de `TortilleryUSB` (normalmente `2`) e Intro.

> [!WARNING]
> El pendrive lleva Tortillery+, así que en este arranque hace su **primer arranque**: graba la placa y la pantalla y
> la pantalla pide el modelo. Espera unos 5 minutos y **no toques la pantalla**. Si eliges el modelo, la impresora se
> reinicia y vuelve a arrancar desde la eMMC.

Entra (`mks` / `makerbase`) y comprueba que estás en el pendrive:

```bash
findmnt /
findmnt /boot
```

Tiene que salir `/` en **`/dev/sda2`** y `/boot` en **`/dev/sda1`**. Si sale `/dev/mmcblk1p2`, estás en la eMMC: no
sigas.

## 7. Agranda el pendrive

La imagen ocupa unos 7 GB del pendrive y hace falta sitio para la copia de la eMMC y para la imagen:

```bash
sudo fdisk -l /dev/sda
sudo dd if=/dev/sda of=/home/mks/usb-partition-table-before.bin bs=512 count=1
sudo /usr/sbin/parted /dev/sda
```

Dentro de `parted` escribe `resizepart 2 100%`, contesta `Yes` al aviso de partición en uso y después escribe `quit`.
Luego:

```bash
sudo /usr/sbin/resize2fs /dev/sda2
df -h /
```

`sda2` tiene que ser la última partición del pendrive. Si `fdisk` te enseña otra cosa, no lo hagas.

## 8. Copia de seguridad de la eMMC

Comprueba que sigues en el pendrive y que la eMMC no está montada. Los dos últimos comandos no deben sacar nada:

```bash
findmnt /
findmnt -rn -S /dev/mmcblk1p1
findmnt -rn -S /dev/mmcblk1p2
```

Copia la eMMC a un archivo del pendrive y compárala byte a byte:

```bash
sudo dd if=/dev/mmcblk1 of=/home/mks/emmc-original-backup.img bs=4M status=progress conv=fsync
sudo cmp /dev/mmcblk1 /home/mks/emmc-original-backup.img && echo "COPIA COMPROBADA"
```

No sigas si no sale `COPIA COMPROBADA`.

## 9. Pasa la imagen a la impresora

1. Conecta el WiFi del pendrive con `sudo nmtui` (_Activate a connection_) y mira la IP con `hostname -I`.
2. Desde el PC, pasa la imagen a `/home/mks/tortillery.img`, con WinSCP (SFTP, puerto 22, usuario `mks`) o con
   PowerShell:

   ```powershell
   scp "C:\ruta\Tortillery+_1.1.5.img" mks@<IP>:/home/mks/tortillery.img
   ```

3. Comprueba en la impresora que llegó entera. El tamaño tiene que ser 7818182656 y la huella la misma del paso 3:

   ```bash
   stat -c '%n : %s bytes' /home/mks/tortillery.img
   sha256sum /home/mks/tortillery.img
   ```

## 10. Escribe la imagen en la eMMC

> [!CAUTION]
> Este es el paso que **borra la eMMC**. No cortes la luz. Tarda unos 3 minutos y la comprobación del final puede
> estar un rato sin mostrar nada.

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT
```

Si los discos coinciden con los de esta guía, copia este bloque **entero**. Se para solo si no estás en el pendrive,
si la eMMC está montada o si los tamaños no coinciden:

```bash
(
set -e
if [ "$(findmnt -n -o SOURCE /)" != "/dev/sda2" ]; then
    echo "PARADO: no estas en el pendrive."
    exit 1
fi
if findmnt -rn -S /dev/mmcblk1p1 ||
   findmnt -rn -S /dev/mmcblk1p2; then
    echo "PARADO: la eMMC esta montada."
    exit 1
fi
EMMC_BYTES="$(sudo blockdev --getsize64 /dev/mmcblk1)"
IMAGE_BYTES="$(stat -c %s /home/mks/tortillery.img)"
BACKUP_BYTES="$(stat -c %s /home/mks/emmc-original-backup.img)"
if [ "$IMAGE_BYTES" != "$EMMC_BYTES" ] ||
   [ "$BACKUP_BYTES" != "$EMMC_BYTES" ]; then
    echo "PARADO: la imagen, la copia y la eMMC no miden lo mismo."
    exit 1
fi
sudo dd if=/home/mks/tortillery.img of=/dev/mmcblk1 \
    bs=4M status=progress conv=fsync
echo "Escrita. Comprobando..."
sudo cmp /home/mks/tortillery.img /dev/mmcblk1
sync
echo "EMMC ESCRITA Y COMPROBADA"
)
```

No sigas hasta que salga `EMMC ESCRITA Y COMPROBADA`.

## 11. Arranca desde la eMMC

```bash
sudo poweroff
```

Cuando se apague: apaga con el interruptor, **quita el pendrive** y enciende. El pendrive y la eMMC tienen ahora los
mismos identificadores, así que **no arranques con el pendrive puesto**.

A partir de aquí es la [instalación normal](../README.md#-instalación): el primer arranque graba la placa y la
pantalla, eliges el idioma y el modelo (la impresora se reinicia sola una vez) y después conectas el WiFi y nivelas
la cama. Con Tortillery+ no hace falta grabar a mano la placa ni la pantalla ni copiar `printer.cfg`: los pasos 11 a
13 de la guía original los hace la imagen sola.

Guarda el pendrive sin formatear: en `/home/mks/emmc-original-backup.img` tiene la copia del sistema de fábrica.
Cuando puedas, pásala también a tu PC.

## 12. Si algo falla

| Lo que pasa                                                   | Qué hacer                                                                                                      |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| No aparece el puerto COM o salen símbolos raros               | Cable USB-C de datos, driver CH341 y PuTTY a 1500000. Tras encender, _Restart Session_.                         |
| Arranca desde la eMMC y no del pendrive                       | No elegiste a tiempo en el menú. Comprueba `TIMEOUT 600` y elige `TortilleryUSB` en el siguiente arranque.     |
| La consola muestra `=>`                                       | Estás en U-Boot, no en Linux. Escribe `boot`.                                                                  |
| `already mounted` o no se ven los archivos del pendrive       | La impresora montó las dos particiones en la misma carpeta. Mira con `findmnt -rn -o SOURCE,TARGET,FSTYPE \| grep /dev/sda`, desmonta esas carpetas con `sudo umount` y repite el paso 4. |
| Windows pide formatear el pendrive                            | Cancela. La parte de Linux no se puede leer desde Windows.                                                     |
| Las huellas SHA256 no coinciden                               | La imagen llegó mal. Vuelve a pasarla y **no escribas la eMMC**.                                               |
| El bloque del paso 10 se para                                 | Lee el motivo (`PARADO: ...`). No quites las comprobaciones para forzarlo.                                     |
| `dd` o `cmp` dan error                                        | No apagues. Sigue en el pendrive y pide ayuda antes de arrancar desde la eMMC.                                 |

---

<sub>Método original: [Mustafa Yücel](https://yucellmustafa.com.tr/blog/swx4-tortillery) (12 de octubre de 2026).
Traducido y adaptado a Tortillery+.</sub>
