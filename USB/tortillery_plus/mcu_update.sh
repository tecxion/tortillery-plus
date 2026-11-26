#!/bin/sh
# mcu_update.sh (Tortillery+): same GPIO/DFU sequence as the original, but the
# exit code is the one from flash_usb.py so callers know if the flash worked.

#GPIO2_C6 86  BOOT0
#GPIO2_C3 83  RESET

[ -f /root/klipper.bin ] || { echo "no firmware"; exit 1; }

systemctl stop klipper.service
mv -f /root/klipper.bin /home/mks/

for pin in 83 86; do
    [ -d /sys/class/gpio/gpio$pin ] || echo $pin > /sys/class/gpio/export
    echo out > /sys/class/gpio/gpio$pin/direction
done

# enter DFU: BOOT0 + reset
echo 0 > /sys/class/gpio/gpio86/value
sleep 0.5
echo 0 > /sys/class/gpio/gpio83/value
sleep 0.5
echo 1 > /sys/class/gpio/gpio83/value
sleep 1

/home/mks/klipper/scripts/flash_usb.py -t stm32f4 -d 0483:df11 -s 0x08000000 /home/mks/klipper.bin
rc=$?

# back to normal mode + reset, whatever the result
echo 1 > /sys/class/gpio/gpio86/value
sleep 0.5
echo 0 > /sys/class/gpio/gpio83/value
sleep 0.5
echo 1 > /sys/class/gpio/gpio83/value

systemctl start --no-block klipper.service   # --no-block: desde el primer arranque (va antes de Klipper) se bloquearía
exit $rc
