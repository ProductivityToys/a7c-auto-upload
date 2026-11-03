#!/bin/ash
# No timer-driven display or power hold. Only authenticated PROBE can draw.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90
cd / || exit 90
umask 077
trap '' HUP
if [ "${1:-}" = --check ]; then
    for n in capture redraw listener; do [ -x "$D/$n" ] || exit 91; done
    for n in boot-id native.pid native.base native.mode native.timer; do [ -s "$D/$n" ] || exit 91; done
    if [ -f "$D/diagnose-only" ] || [ -f "$D/shooting-overlay" ]; then
        [ -x "$D/ui-layout" ] || exit 91
    fi
    if [ -f "$D/continuous-blink" ]; then
        [ -x "$D/blink-launch" ] && [ -f "$D/blink-worker.sh" ] || exit 91
        /bin/ash -n "$D/blink-worker.sh" || exit 91
    fi
    /bin/ash -n "$D/action.sh" || exit 91
    /bin/ash -n "$D/manage.sh" || exit 91
    echo DDS_COLLECTOR_CHECK_OK
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
# Passive poll has no idle wakeups or power hold. Keep the manually installed
# entry available until explicit cleanup/power loss; blink worker is bounded.
"$D/listener"
