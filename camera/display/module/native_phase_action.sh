#!/bin/ash
# RAM-only native phase observation. No uploader control, module load or lease.
B=/bin/busybox
D=/setting/a7c-debug/ram/maint
sample() {
 p=$($B pidof im.elf); case "$p" in ''|*[!0-9]*) return 94;; esac
 base=
 while read range perms offset device inode name; do
  if [ "$offset" = 00000000 ] && [ "$name" = /usr/lib/libObj.so ]; then
   [ -z "$base" ] || return 95
   base=${range%%-*}
  fi
 done < /proc/$p/maps
 case "$base" in ''|*[!0-9a-f]*) return 95;; esac
 echo SAMPLE_BEGIN
 $B cat /proc/uptime
 "$D/probe" "$p" "$base" "${1:---native-phase}"
 rc=$?
 echo SAMPLE_END_rc=$rc
 return "$rc"
}
case "$1" in
 STATUS|TRACE)
  echo A7C_DEBUG_V2
  $B cat /proc/uptime /proc/sys/kernel/random/boot_id
  for n in probe.log phase.log lease.log; do
   if [ -f "$D/$n" ]; then echo FILE=$n; if [ "$n" = probe.log ]; then limit=12000; elif [ "$n" = lease.log ]; then limit=2000; else limit=6000; fi; $B tail -c "$limit" "$D/$n"; echo; fi
  done
  [ ! -f "$D/lease.ready" ] || echo LEASE_READY=1
  [ ! -f "$D/lease.done" ] || echo LEASE_DONE=1
  echo A7C_DEBUG_END; exit 0;;
esac
$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90
[ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$D/boot-id")" ] || exit 91
case "$1" in
 PROBE) sample --native-phase-burst > "$D/probe.log" 2>&1;;
 START)
  $B mkdir "$D/sample.lock" || exit 93
  trap '$B rmdir "$D/sample.lock"' EXIT
  : > "$D/phase.log"
  n=0
  while [ "$n" -lt 10 ]; do
   sample > "$D/sample.tmp" 2>&1; rc=$?
   $B cat "$D/sample.tmp" >> "$D/phase.log"
   $B grep -E '^(SAMPLE_|NATIVE_PHASE pending|NATIVE_PHASE_TRACE)' "$D/sample.tmp"
   [ "$rc" = 0 ] || exit "$rc"
   n=$((n+1)); $B sleep 1
  done;;
 PAUSE) echo NATIVE_PHASE_NO_BACKGROUND_WORK;;
 *) exit 64;;
esac
