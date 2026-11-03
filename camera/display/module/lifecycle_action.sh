#!/bin/ash
# Temporary lifecycle trial maintenance; never modifies persistent startup.
B=/bin/busybox
D=/setting/a7c-debug/ram/maint
U=/setting/a7c-uploader/ram
case "$1" in
 STATUS|TRACE)
  echo A7C_DEBUG_V2
  $B cat /proc/uptime /proc/sys/kernel/random/boot_id
  if [ -e /setting/a7c-display/enabled ]; then echo DISPLAY_ENABLED; else echo DISPLAY_DISABLED; fi
  if [ -f "$U/worker.pid" ]; then
   read worker < "$U/worker.pid"
   case "$worker" in ''|*[!0-9]*) echo WORKER_PID_INVALID;; *) if kill -0 "$worker" 2>/dev/null; then echo WORKER_ALIVE=$worker; else echo WORKER_STOPPED=$worker; fi;; esac
  fi
  for n in worker.exit events.log worker.stdout receipt.err receipt-copy.log receipt.root scan-lease.log; do
   if [ -f "$U/$n" ]; then echo FILE=$n; $B tail -c 1000 "$U/$n"; echo; fi
  done
  for n in trial.state lease.log probe.log revoke.log; do
   if [ -f "$D/$n" ]; then echo FILE=$n; case "$n" in probe.log|revoke.log) limit=6000;; *) limit=1500;; esac; $B tail -c "$limit" "$D/$n"; echo; fi
  done
  echo A7C_DEBUG_END; exit 0;;
esac
$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90
[ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$D/boot-id")" ] || exit 91
[ ! -e /setting/a7c-display/enabled ] || exit 92
case "$1" in
 START) [ ! -e "$D/trial.claim" ] || exit 93; /bin/ash "$D/resume.sh" || exit $?; exec /bin/ash "$D/trial.sh" --retain-service;;
 PROBE)
  p=$($B pidof im.elf); case "$p" in ''|*[!0-9]*) exit 94;; esac
  # Listener runs STATUS after PROBE and truncates action.out. Keep the query
  # separately, including failure output and the boot/uptime of this sample.
  {
   echo PROBE_BEGIN; $B cat /proc/uptime /proc/sys/kernel/random/boot_id
   "$D/probe" --inspect-service "$p"; service_rc=$?
   "$D/probe" --inspect-frame "$p"; frame_rc=$?
   echo "PROBE_DONE service_rc=$service_rc frame_rc=$frame_rc"
  } > "$D/probe.log" 2>&1
  exit "$service_rc";;
 PAUSE)
  # 87 at the first preview snapshot is a known return before any preview
  # publication. Module load itself completed. Permit explicit retirement.
  $B grep -Eq '^ABLATION_END rc=(0|87) phase=--service-preview$' "$D/trial.state" || exit 92
  $B mkdir "$D/revoke.claim" || exit 93
  p=$($B pidof im.elf); case "$p" in ''|*[!0-9]*) exit 94;; esac
  {
   "$D/probe" --inspect-service "$p" && "$D/probe" --service-off "$p" &&
   "$D/probe" --finish-event "$p" && "$D/probe" --inspect-marker "$p"
  } > "$D/revoke.log" 2>&1 || exit $?
  echo LIFECYCLE_REVOKED > "$D/trial.state";;
 *) exit 64;;
esac
