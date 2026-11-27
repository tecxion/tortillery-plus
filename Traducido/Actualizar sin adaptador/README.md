<div align="center">

# 🔌 Installing Tortillery+ without an eMMC adapter

**For printers with Artillery's stock system: write the image to the eMMC from the printer itself**

[⬅️ Back to the README](../README.md) · [🇪🇸 Español](../../Actualizar%20sin%20adaptador/README.md)

</div>

---

> [!NOTE]
> **Where this guide comes from.** The whole method is by **Mustafa Yücel**, who published it in Turkish on
> 12 October 2026 and tested it on an X4 Pro with the original Tortillery image:
> **[Artillery Sidewinder X4 Pro ve X4 Plus için Adaptörsüz Tortillery Kurulumu](https://yucellmustafa.com.tr/blog/swx4-tortillery)**.
> This page is only a translation, adapted to the Tortillery+ image. All the credit is his; if something doesn't match,
> his guide wins.

> [!CAUTION]
> ## ⚠️ Read this before you start
>
> This is an **advanced method with a real risk of leaving the printer unable to boot**. If you have an eMMC reader,
> use the [normal installation](../README.md#-installation): it's simpler and safer.
>
> - **It erases the whole eMMC.** The `dd` command in step 10 writes over the printer's entire system.
> - **One wrong disk breaks everything.** Mix up `/dev/mmcblk1` (the eMMC) and `/dev/sda` (the USB stick), or the
>   other way round, and you can wipe the wrong one. `dd` doesn't ask or warn. Check the names with `lsblk` at every
>   step.
> - **Don't cut the power** while the eMMC or the board is being written. If it's cut halfway, the printer may not boot
>   again, and only an eMMC reader can fix it.
> - **You edit the printer's boot setup** (`extlinux.conf`). One badly written line can stop it from booting. Keep the
>   copy from step 2.
> - **The backup doesn't keep everything.** Step 8 copies the eMMC system, but not the board firmware or the screen
>   firmware. Also, nobody has tested restoring from that backup.
> - **Only for Artillery's stock system**, the one that boots with `/boot/extlinux/extlinux.conf`. **Don't use it if
>   your printer already runs Tortillery or Tortillery+**: those boot differently and have the same disk identifiers as
>   the USB stick. For them, update [from Mainsail or by USB](../README.md#-updating).
> - **Only tested on an X4 Pro**, by the author and with the original Tortillery. Not tested on the X4 Plus or with the
>   Tortillery+ image.
> - You do it **at your own risk**.

## 1. What you need

- The printer switched on with its stock system and idle: no printing, no axis moves, no heating.
- A Windows PC and a **data USB-C cable** (not a charge-only one) for the board's serial console.
- A **64 GB USB stick** you can erase.
- [PuTTY](https://www.putty.org/) for the serial console, [balenaEtcher](https://etcher.balena.io/) to write the USB
  stick and [WinSCP](https://winscp.net/) or `scp` to copy the image over WiFi.
- The `Tortillery+_1.1.5.img` image from the [download](../README.md#-download).

Disk names on the printer (always check them with `lsblk`):

| Disk             | What it is                                            |
| ---------------- | ----------------------------------------------------- |
| `/dev/mmcblk1`   | the printer's eMMC (7,818,182,656 bytes)              |
| `/dev/mmcblk1p1` | eMMC boot partition (256 MB)                          |
| `/dev/mmcblk1p2` | eMMC system partition                                 |
| `/dev/sda`       | the USB stick                                         |
| `/dev/sda1`      | USB stick boot partition                              |
| `/dev/sda2`      | USB stick system partition (enlarged in step 7)       |

In `dd`, `if=` is what's read and `of=` is what **gets erased and overwritten**.

## 2. Serial console

1. Connect the PC to the printer with the USB-C cable. In Windows _Device Manager_, see which COM port it gets. If it
   doesn't show up, install the CH341 driver.
2. In PuTTY: _Serial_, that COM port, speed **1500000**, 8 data bits, 1 stop bit, no parity and no flow control.
3. Log in with your system's user and password (on the stock system usually `mks` / `makerbase`) and check its state:

   ```bash
   lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT
   findmnt /
   findmnt /boot
   cat /boot/extlinux/extlinux.conf
   sudo blockdev --getsize64 /dev/mmcblk1
   ```

   `/` must be on `/dev/mmcblk1p2` and the eMMC must be **7818182656** bytes. **If `/boot/extlinux/extlinux.conf`
   doesn't exist or the size is different, stop here:** this guide isn't for your printer.

4. Keep a copy of the boot setup:

   ```bash
   sudo cp -n /boot/extlinux/extlinux.conf /boot/extlinux/extlinux.conf.backup
   ```

## 3. Write the image to the USB stick

1. In PowerShell, note the image's checksum. It must match the `.sha256` file next to it:

   ```powershell
   Get-FileHash -Algorithm SHA256 "C:\path\Tortillery+_1.1.5.img"
   ```

2. With balenaEtcher, write the image **to the USB stick**. Double-check the target disk's size before pressing
   _Flash_. If Windows then asks to format the stick, **cancel**.
3. Plug the stick into the printer, still running its own system. **Don't restart it yet.**

The Tortillery+ image has these identifiers, the same ones the original guide used:

| Partition   | Type  | Label        | UUID                                   |
| ----------- | ----- | ------------ | -------------------------------------- |
| `/dev/sda1` | vfat  | `armbi_boot` | `35AE-B672`                            |
| `/dev/sda2` | ext4  | `armbi_root` | `f68704c3-ba62-4911-a703-ecf77de52d7a` |

Check them with `lsblk -o NAME,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT`.

## 4. Mount the USB stick to read it

If the printer mounted the stick on its own, this block unmounts it and mounts both partitions again, read-only.
Copy it **whole**:

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

Check that the boot files are there and that the eMMC boot partition has room (about 52 MB is needed):

```bash
ls -lh /mnt/tortillery-boot/Image /mnt/tortillery-boot/uInitrd /mnt/tortillery-boot/dtb/rockchip/rk3328-mkspi.dtb
cat /mnt/tortillery-root/etc/fstab
df -h /boot
```

If you get `already mounted` or can't see the files, see [If something goes wrong](#12-if-something-goes-wrong).

## 5. Add booting from the USB stick

Copy the USB stick's kernel to the eMMC boot partition:

```bash
sudo mkdir -p /boot/tortillery-usb
sudo cp /mnt/tortillery-boot/Image /boot/tortillery-usb/
sudo cp /mnt/tortillery-boot/uInitrd /boot/tortillery-usb/
sudo cp /mnt/tortillery-boot/dtb/rockchip/rk3328-mkspi.dtb /boot/tortillery-usb/
```

Open the boot setup with `sudo nano /boot/extlinux/extlinux.conf`. **Without deleting what's there**, leave a single
`TIMEOUT` line and a single `DEFAULT` line and add the `TortilleryUSB` entry:

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

- `DEFAULT` must be the `label` of the entry you already had, here `Armbian`. That way, if you don't pick anything,
  your usual system boots.
- The `append` line must be **a single line**.
- `TIMEOUT 600` gives you 60 seconds to choose in the menu.

Save (Ctrl+O, Enter, Ctrl+X) and check:

```bash
sync
cat /boot/extlinux/extlinux.conf
ls -lh /boot/tortillery-usb/
```

## 6. Boot from the USB stick

```bash
sudo poweroff
```

Once it has shut down, switch the printer off and on with the power switch. Open PuTTY again (_Restart Session_). In
the menu, type the number of `TortilleryUSB` (usually `2`) and press Enter.

> [!WARNING]
> The USB stick carries Tortillery+, so this boot is its **first boot**: it flashes the board and the screen, and the
> screen asks for the model. Wait about 5 minutes and **don't touch the screen**. If you choose the model, the printer
> restarts and boots from the eMMC again.

Log in (`mks` / `makerbase`) and check you're on the USB stick:

```bash
findmnt /
findmnt /boot
```

`/` must be on **`/dev/sda2`** and `/boot` on **`/dev/sda1`**. If you see `/dev/mmcblk1p2`, you're on the eMMC:
don't go on.

## 7. Enlarge the USB stick

The image takes about 7 GB of the stick, and you need room for the eMMC backup and for the image:

```bash
sudo fdisk -l /dev/sda
sudo dd if=/dev/sda of=/home/mks/usb-partition-table-before.bin bs=512 count=1
sudo /usr/sbin/parted /dev/sda
```

Inside `parted`, type `resizepart 2 100%`, answer `Yes` to the partition-in-use warning and then type `quit`. Then:

```bash
sudo /usr/sbin/resize2fs /dev/sda2
df -h /
```

`sda2` must be the last partition on the stick. If `fdisk` shows anything else, don't do it.

## 8. Back up the eMMC

Check you're still on the USB stick and that the eMMC isn't mounted. The last two commands must print nothing:

```bash
findmnt /
findmnt -rn -S /dev/mmcblk1p1
findmnt -rn -S /dev/mmcblk1p2
```

Copy the eMMC to a file on the stick and compare them byte by byte:

```bash
sudo dd if=/dev/mmcblk1 of=/home/mks/emmc-original-backup.img bs=4M status=progress conv=fsync
sudo cmp /dev/mmcblk1 /home/mks/emmc-original-backup.img && echo "BACKUP VERIFIED"
```

Don't go on unless you see `BACKUP VERIFIED`.

## 9. Copy the image to the printer

1. Connect the USB system to WiFi with `sudo nmtui` (_Activate a connection_) and get its IP with `hostname -I`.
2. From the PC, copy the image to `/home/mks/tortillery.img`, with WinSCP (SFTP, port 22, user `mks`) or with
   PowerShell:

   ```powershell
   scp "C:\path\Tortillery+_1.1.5.img" mks@<IP>:/home/mks/tortillery.img
   ```

3. On the printer, check it arrived whole. The size must be 7818182656 and the checksum the same as in step 3:

   ```bash
   stat -c '%n : %s bytes' /home/mks/tortillery.img
   sha256sum /home/mks/tortillery.img
   ```

## 10. Write the image to the eMMC

> [!CAUTION]
> This is the step that **erases the eMMC**. Don't cut the power. It takes about 3 minutes, and the check at the end
> can sit for a while without printing anything.

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT
```

If the disks match the ones in this guide, copy this block **whole**. It stops by itself if you're not on the USB
stick, if the eMMC is mounted or if the sizes don't match:

```bash
(
set -e
if [ "$(findmnt -n -o SOURCE /)" != "/dev/sda2" ]; then
    echo "STOPPED: not running from the USB stick."
    exit 1
fi
if findmnt -rn -S /dev/mmcblk1p1 ||
   findmnt -rn -S /dev/mmcblk1p2; then
    echo "STOPPED: the eMMC is mounted."
    exit 1
fi
EMMC_BYTES="$(sudo blockdev --getsize64 /dev/mmcblk1)"
IMAGE_BYTES="$(stat -c %s /home/mks/tortillery.img)"
BACKUP_BYTES="$(stat -c %s /home/mks/emmc-original-backup.img)"
if [ "$IMAGE_BYTES" != "$EMMC_BYTES" ] ||
   [ "$BACKUP_BYTES" != "$EMMC_BYTES" ]; then
    echo "STOPPED: the image, the backup and the eMMC are not the same size."
    exit 1
fi
sudo dd if=/home/mks/tortillery.img of=/dev/mmcblk1 \
    bs=4M status=progress conv=fsync
echo "Written. Checking..."
sudo cmp /home/mks/tortillery.img /dev/mmcblk1
sync
echo "EMMC WRITTEN AND VERIFIED"
)
```

Don't go on until you see `EMMC WRITTEN AND VERIFIED`.

## 11. Boot from the eMMC

```bash
sudo poweroff
```

Once it has shut down: switch it off with the power switch, **remove the USB stick** and switch it on. The stick and
the eMMC now have the same identifiers, so **don't boot with the stick plugged in**.

From here on it's the [normal installation](../README.md#-installation): the first boot flashes the board and the
screen, you choose the language and the model (the printer restarts by itself once), and then you connect to WiFi and
level the bed. With Tortillery+ you don't need to flash the board or the screen by hand or copy `printer.cfg`: the
image does steps 11 to 13 of the original guide by itself.

Keep the USB stick unformatted: `/home/mks/emmc-original-backup.img` on it is the backup of the stock system. Copy it
to your PC too when you can.

## 12. If something goes wrong

| What happens                                                  | What to do                                                                                                     |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| No COM port, or garbled characters                            | Data USB-C cable, CH341 driver and PuTTY at 1500000. After power-on, _Restart Session_.                         |
| It boots from the eMMC instead of the USB stick               | You didn't choose in the menu in time. Check `TIMEOUT 600` and pick `TortilleryUSB` on the next boot.          |
| The console shows `=>`                                        | You're in U-Boot, not Linux. Type `boot`.                                                                      |
| `already mounted`, or the USB stick's files don't show        | The printer mounted both partitions on the same folder. Check with `findmnt -rn -o SOURCE,TARGET,FSTYPE \| grep /dev/sda`, unmount those folders with `sudo umount` and repeat step 4. |
| Windows asks to format the USB stick                          | Cancel. Windows can't read the Linux part.                                                                     |
| The SHA256 checksums don't match                              | The image arrived damaged. Copy it again and **don't write the eMMC**.                                         |
| The step 10 block stops                                       | Read the reason (`STOPPED: ...`). Don't remove the checks to force it.                                         |
| `dd` or `cmp` report an error                                 | Don't switch off. Stay on the USB stick and ask for help before booting from the eMMC.                         |

---

<sub>Original method: [Mustafa Yücel](https://yucellmustafa.com.tr/blog/swx4-tortillery) (12 October 2026).
Translated and adapted to Tortillery+.</sub>
