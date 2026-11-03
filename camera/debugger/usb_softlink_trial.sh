#!/bin/ash
# One RAM-only USB link trial. Launch detached; never install at boot.
# The operator must exit service mode and unmount host disks during the delay.
B=/bin/busybox
D=/setting/a7c-debug/ram/usb-softlink
NODE=/sys/class/udc/dwc3.0/soft_connect
STATE=/sys/class/udc/dwc3.0/state
DELAY=60
RESTORE=90
trap '' HUP
umask 077
$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90
[ -w "$NODE" ] && [ -r "$STATE" ] && [ -d "$D" ] || exit 91
$B mkdir "$D/claim" || exit 92
exec >> "$D/events.log" 2>&1
log() { echo "$1"; $B cat /proc/uptime; }
snapshot() { $B cat "$STATE" /proc/net/route; }
log TRIAL_ARMED
snapshot
# A separate process restores the data link even if the disconnect writer dies.
(
 echo "$$" > "$D/guardian.ready"
 $B sleep "$RESTORE"
 if [ -e "$D/attempted" ]; then
  log RECONNECT_BEGIN
  echo connect > "$NODE"; rc=$?
  log "RECONNECT_RETURN rc=$rc"
  snapshot
 fi
 : > "$D/finished"
) &
guardian=$!
echo "$guardian" > "$D/guardian.pid"
while [ ! -e "$D/guardian.ready" ]; do $B sleep 1; done
echo "$$" > "$D/writer.pid"
$B sleep "$DELAY"
if [ -e "$D/cancel" ]; then log TRIAL_CANCELLED; exit 0; fi
[ "$($B cat "$STATE")" = configured ] || { log NOT_CONFIGURED; exit 93; }
log DISCONNECT_BEGIN
: > "$D/attempted"
echo disconnect > "$NODE"; rc=$?
log "DISCONNECT_RETURN rc=$rc"
snapshot
for n in 1 2 3 4 5 6 7 8 9 10; do
 $B sleep 2
 snapshot
done
wait "$guardian"
log TRIAL_FINISHED
