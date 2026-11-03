#!/bin/ash
# Fixed one-shot UI query, dispatched by the temporary authenticated listener.
B=/bin/busybox
D=/setting/a7c-debug/ram/ui-layout-once
mounted() { $B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts; }
mounted || exit 90
cd / || exit 90
umask 077
case "$1" in
 STATUS)
    echo A7C_DEBUG_V2
    for name in status query.rc query.txt query-uptime query-usb-state done; do
        if [ -f "$D/$name" ]; then
            echo FILE=$name
            $B cat "$D/$name"
        fi
    done
    for phase in before after; do
        if [ -f "$D/$phase.bin" ]; then
            echo LAYOUT_TEXT=$phase
            $B grep -E 'Display LayoutList|Display WidgetList|Physical:|groupID:|widgetID:|Close Animation Layout' "$D/$phase.bin"
        fi
    done
    echo A7C_DEBUG_END;;
 PROBE)
    [ ! -e "$D/cancel" ] || exit 94
    # Claim even a failed attempt; never automatically resend a native event.
    $B mkdir "$D/claimed" || exit 92
    finish() { rc=$?; mounted && printf 'exit=%s\n' "$rc" > "$D/done"; }
    trap finish EXIT
    echo stage=baseline > "$D/status"
    $B timeout -t 3 -s 9 /usr/bin/ulogio dk 0x034fd000 0x8000 "$D/before.bin"
    [ "$?" = 0 ] && [ "$($B wc -c < "$D/before.bin")" -eq 32768 ] || exit 96
    [ ! -e "$D/cancel" ] || exit 94
    $B cat /proc/uptime > "$D/query-uptime"
    $B cat /sys/class/udc/dwc3.0/state > "$D/query-usb-state"
    echo stage=query > "$D/status"
    "$D/ui-layout" > "$D/query.txt" 2>&1
    rc=$?
    printf '%s\n' "$rc" > "$D/query.rc"
    [ "$rc" = 0 ] || exit 98
    $B sleep 1
    $B timeout -t 3 -s 9 /usr/bin/ulogio dk 0x034fd000 0x8000 "$D/after.bin"
    [ "$?" = 0 ] && [ "$($B wc -c < "$D/after.bin")" -eq 32768 ] || exit 96
    echo stage=captured > "$D/status";;
 *) exit 64;;
esac
