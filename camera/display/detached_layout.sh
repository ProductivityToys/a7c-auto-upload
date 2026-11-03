#!/bin/ash
# One-shot observer. Run only from the existing, verified private debug tmpfs.
B=/bin/busybox
R=/setting/a7c-debug/ram
D=$R/ui-layout-once
UDC=/sys/class/udc/dwc3.0/state
mounted() { $B grep -q "^a7c-debug-ram $R tmpfs " /proc/mounts; }
mounted || exit 90
cd / || exit 90
umask 077
trap '' HUP
[ -d "$D" ] && [ -x "$D/ui-layout" ] || exit 90
if [ "${1:-}" = "--check" ]; then
    [ "$($B cat "$UDC")" = configured ] || exit 91
    echo OSD_COLLECTOR_CHECK_OK
    exit 0
fi
[ "$#" = 0 ] || exit 64
$B mkdir "$D/running" || exit 92
finish() {
    rc=$?
    if mounted; then
        $B cat /proc/uptime > "$D/finish-uptime"
        printf 'exit=%s\n' "$rc" > "$D/done"
        $B rmdir "$D/running"
    fi
}
trap finish EXIT
trap 'exit 93' TERM INT
echo "$$" > "$D/pid"
printf 'stage=waiting\n' > "$D/status"
$B cat /proc/uptime > "$D/start-uptime"
# This fixed query has already been verified in USB service mode.
# Observe USB state, but do not mistake a gadget state for physical disconnect.
# The operator leaves USB during this 90-second window. Returned layout IDs,
# timestamps and USB observations determine the actual context afterward.
seen=0
attempt=0
previous=unset
while [ "$attempt" -lt 90 ]; do
    mounted || exit 90
    [ ! -e "$D/cancel" ] || exit 94
    state=$($B cat "$UDC" 2>/dev/null) || state=unavailable
    if [ "$state" != "$previous" ]; then
        printf 'elapsed=%s\n' "$attempt" >> "$D/transitions"
        $B cat /proc/uptime >> "$D/transitions"
        printf 'usb=%s\n' "$state" >> "$D/transitions"
        previous=$state
    fi
    [ "$state" != configured ] || seen=1
    attempt=$((attempt+1))
    $B sleep 1
done
[ "$seen" = 1 ] || { echo stage=no-initial-connection > "$D/status"; exit 95; }
# Native dk was inspected: O_RDONLY / PROT_READ, fixed 32 KiB region.
# Installer verifies exact log-tool and configuration hashes before arming.
$B timeout -t 5 -s 9 /usr/bin/ulogio dk 0x034fd000 0x8000 "$D/before.bin"
[ "$?" = 0 ] && [ "$($B wc -c < "$D/before.bin")" -eq 32768 ] || exit 96
state=$($B cat "$UDC" 2>/dev/null) || exit 97
case "$state" in
    configured|default|"not attached") ;;
    *) exit 97;;
esac
printf '%s\n' "$state" > "$D/query-usb-state"
[ ! -e "$D/cancel" ] || exit 94
# Claim precedes the single request. Never retry, including after a timeout.
$B mkdir "$D/claimed" || exit 92
echo stage=query > "$D/status"
$B cat /proc/uptime > "$D/query-uptime"
"$D/ui-layout" > "$D/query.txt" 2>&1
rc=$?
printf '%s\n' "$rc" > "$D/query.rc"
[ "$rc" = 0 ] || exit 98
$B sleep 1
$B timeout -t 5 -s 9 /usr/bin/ulogio dk 0x034fd000 0x8000 "$D/after.bin"
[ "$?" = 0 ] && [ "$($B wc -c < "$D/after.bin")" -eq 32768 ] || exit 96
$B cat "$UDC" > "$D/end-usb-state"
$B cat /proc/uptime > "$D/end-uptime"
echo stage=captured > "$D/status"
exit 0
