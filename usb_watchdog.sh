#!/bin/sh
# Watchdog for the Nibe RS-485 USB adapter (/dev/ttyUSB0).
#
# Run this on a schedule (e.g. every 10 minutes via cron). If the device
# is missing, it first tries a lightweight USB rebind (works when the
# adapter is wedged but still electrically present - e.g. driver stuck
# after a "ftdi_set_termios FAILED" type error). Only if that doesn't
# bring the device back does it escalate to a full reboot, since that's
# the only thing that reliably recovered a hard USB dropout on this Pi
# (dwc_otg controller failing to re-enumerate at all - "device
# descriptor read/64, error -71" / "attempt power cycle" in dmesg).
#
# A cooldown guards against reboot-looping if the adapter is genuinely
# dead (bad cable/port/hardware) - it won't auto-reboot more than once
# per REBOOT_COOLDOWN_SECONDS, so a truly stuck adapter just gets logged
# repeatedly instead of rebooting the Pi every 10 minutes forever.

DEVICE=/dev/ttyUSB0
USB_BUS=1-1
LOG=/home/admin/projects/NibeVVP/usb_watchdog.log
LAST_REBOOT_MARKER=/home/admin/projects/NibeVVP/.last_watchdog_reboot
REBOOT_COOLDOWN_SECONDS=3600

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG"
}

if [ -e "$DEVICE" ]; then
    exit 0
fi

log "Device $DEVICE missing - attempting USB rebind of bus $USB_BUS"

echo "$USB_BUS" | sudo tee /sys/bus/usb/drivers/usb/unbind > /dev/null 2>&1
sleep 2
echo "$USB_BUS" | sudo tee /sys/bus/usb/drivers/usb/bind > /dev/null 2>&1
sleep 3

if [ -e "$DEVICE" ]; then
    log "Device $DEVICE recovered after USB rebind"
    exit 0
fi

log "USB rebind did not recover $DEVICE"

now=$(date +%s)
if [ -f "$LAST_REBOOT_MARKER" ]; then
    last=$(cat "$LAST_REBOOT_MARKER")
    elapsed=$((now - last))
    if [ "$elapsed" -lt "$REBOOT_COOLDOWN_SECONDS" ]; then
        log "Skipping reboot - last auto-reboot was ${elapsed}s ago (cooldown ${REBOOT_COOLDOWN_SECONDS}s)"
        exit 1
    fi
fi

log "Rebooting to recover $DEVICE"
echo "$now" > "$LAST_REBOOT_MARKER"
sudo reboot
