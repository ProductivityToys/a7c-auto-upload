#!/bin/ash
# RAM-only, one attempt per boot. Never replaces the uploader or its consumer.
# START_TRACE runs this synchronously so every probe stage reaches the operator.
B=/bin/busybox
D=/setting/a7c-debug/ram/maint
U=/setting/a7c-uploader/ram
N=/setting/a7c-debug/ram/dds-once/native-service
umask 077
retain=0
case "$#:$1" in 0:) ;; 1:--retain-service) retain=1;; *) exit 64;; esac
$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90
$B grep -q '^none /tmp_bt tmpfs ' /proc/mounts || exit 90
[ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$D/boot-id")" ] || exit 91
[ ! -e /setting/a7c-display/enabled ] && [ ! -e "$U/display.active" ] || exit 92
[ ! -e "$D/lease.ready" ] || [ -e "$D/lease.done" ] || exit 97
read worker < "$U/worker.pid" || exit 94
case "$worker" in ''|1|*[!0-9]*) exit 94;; esac
kill -0 "$worker" 2>/dev/null || exit 94
p=$($B pidof im.elf)
case "$p" in ''|1|*[!0-9]*) exit 94;; esac
[ -d "$N" ] && [ -x "$D/probe" ] && [ -x "$D/lease" ] || exit 95
# Evidence is exclusive; do not overwrite a previous attempt or retry a load.
[ ! -e "$N/before.raw" ] && [ ! -e "$N/during.raw" ] && [ ! -e "$N/after.raw" ] || exit 95
$B mkdir "$D/trial.claim" || exit 93
lease_pid=
last_phase=lease
record() {
 echo "$*" > "$D/trial.state"
 echo "$*"
}
finish() {
 result=$?
 trap - EXIT
 if [ -n "$lease_pid" ]; then
  : > "$D/lease.done"
  lease_rc=0
  wait "$lease_pid" || lease_rc=$?
  echo "ABLATION_LEASE_END rc=$lease_rc"
  $B tail -c 1000 "$D/lease.log"
  if [ "$result" = 0 ] && [ "$lease_rc" != 0 ]; then result=96; fi
 fi
 record "ABLATION_END rc=$result phase=$last_phase"
 exit "$result"
}
trap finish EXIT
# A fresh, bounded lease belongs only to this trial. Its existing independent
# guardian releases it if this shell dies. No module cleanup is run by a trap.
$B rm -f "$D/lease.ready" "$D/lease.done"
"$D/lease" --upload-lease 180 > "$D/lease.log" 2>&1 &
lease_pid=$!
record "ABLATION_LEASE_BEGIN pid=$lease_pid"
n=0
while [ ! -e "$D/lease.ready" ] && [ "$n" -lt 5 ]; do
 kill -0 "$lease_pid" 2>/dev/null || exit 96
 $B sleep 1
 n=$((n+1))
done
[ -e "$D/lease.ready" ] && kill -0 "$lease_pid" 2>/dev/null || exit 96
record ABLATION_LEASE_READY
phase() {
 last_phase=$1
 record "ABLATION_PHASE_BEGIN $1"
 "$D/probe" "$1" "$p"
 rc=$?
 record "ABLATION_PHASE_END $1 rc=$rc"
 # Unknown load/preview/unload outcome: preserve evidence and stop. Do not
 # dispatch another native operation from an error trap or retry the request.
 [ "$rc" = 0 ] || exit "$rc"
}
phase --service-ready
phase --service-on
phase --inspect-service
phase --service-preview
if [ "$retain" = 1 ]; then
 # Explicit RAM lifecycle trial: leave the idle indicator registered, release
 # this script's lease, and let original IM deliver real power notifications.
 # No boot enable flag is written. A separate operator action retires it.
 record ABLATION_RETAINED_SERVICE
 exit 0
fi
phase --service-off
phase --finish-event
phase --inspect-marker
echo ABLATION_RESTORED
