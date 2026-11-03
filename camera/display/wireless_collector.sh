#!/bin/ash
# Temporary listener only. Native query requires a separate authenticated PROBE.
B=/bin/busybox
D=/setting/a7c-debug/ram/ui-layout-once
$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90
cd / || exit 90
umask 077
trap '' HUP
if [ "${1:-}" = "--check" ]; then
    [ -x "$D/ui-layout" ] && [ -x "$D/listener" ] || exit 91
    /bin/ash -n "$D/action.sh" || exit 91
    echo OSD_COLLECTOR_CHECK_OK
    exit 0
fi
[ "$#" = 0 ] || exit 64
$B mkdir "$D/running" || exit 92
finish() {
    rc=$?
    printf 'exit=%s\n' "$rc" > "$D/listener.done"
    $B rmdir "$D/running"
}
trap finish EXIT
trap 'exit 93' TERM INT
echo "$$" > "$D/pid"
echo stage=waiting > "$D/status"
# Lifetime of the listener is shorter than the outer launcher deadline.
$B timeout -t 540 -s TERM "$D/listener"
