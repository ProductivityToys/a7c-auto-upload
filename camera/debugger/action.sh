#!/bin/ash
B=/bin/busybox
D=/setting/a7c-debug/ram
R=/setting/a7c-uploader/ram
U=/setting/a7c-uploader
runtime_mounted() { $B grep -q "^a7c-upload-ram $R tmpfs " /proc/mounts; }
idle() {
 if ! runtime_mounted; then
  $B grep -q " $R " /proc/mounts && return 1
  [ -d "$R" ] && [ -z "$($B ls -A "$R")" ]
  return $?
 fi
 [ ! -d "$R/lock" ] && [ ! -d "$R/supervisor.lock" ] && [ ! -e "$R/source.fifo" ] || return 1
 if [ -e "$R/lease.ready" ]; then
  [ -e "$R/lease.done" ] && $B grep -qx 'PROBE_DONE set=0 clear=0 guardian_status=0' "$R/lease.log" || return 1
 fi
}
case "$1" in
 TRACE)
  # Fixed files only; readable even when copy state prevents START/UPDATE.
  echo A7C_DEBUG_V2
  echo "TRACE_UPTIME=$($B cat /proc/uptime)"
  if [ -f "$R/plain-worker.sh" ]; then
   trace_files='plain.worker.pid plain.stdout plain-ftp.log receipt.err receipt-copy.log receipt.root plain-stage.log copy.log relay.log relay.result copy.done guard.done relay.ready lease.log scan-lease.log events.log'
  else
   trace_files='worker.pid worker.exit copy.log relay.log relay.result copy.done guard.done relay.ready ftp.log result-ftp.log result.txt lease.log scan-lease.log events.log'
  fi
  for name in $trace_files; do
   if [ -f "$R/$name" ]; then
    bytes=$($B wc -c < "$R/$name"); echo "FILE=$name BYTES=$bytes"
    if [ "$bytes" -gt 1800 ]; then echo TRUNCATED=1; $B dd if="$R/$name" bs=1200 count=1 2>/dev/null; echo; echo TAIL; $B tail -c 600 "$R/$name";
    else echo TRUNCATED=0; $B cat "$R/$name"; fi
    echo
   fi
  done
  for path in "$R/lock" "$R/supervisor.lock" "$R/source.fifo" "$R/network.fifo"; do [ ! -e "$path" ] || echo "EXISTS=$path"; done
  echo A7C_DEBUG_END;;
 STATUS)
  echo A7C_DEBUG_V2
  echo "UPTIME=$($B cat /proc/uptime)"
  $B cat /proc/sys/kernel/random/boot_id
  echo WORKER_SHA256
  $B sha256sum "$U/worker.sh"
  for name in worker.pid worker.exit worker.stdout query.err drive rec dir info scan-diagnostic.txt ftp.log events.log lease.log scan-lease.log result.txt; do
   if [ -f "$R/$name" ]; then echo "FILE=$name"; $B tail -c 1000 "$R/$name"; echo; fi
  done
  for path in /proc/net/route /proc/ssboot/state "$D/lease.log" /setting/a7c-debug/last-session.txt /setting/a7c-debug/trial-starts; do
   if [ -f "$path" ]; then echo "FILE=$path"; $B tail -c 1000 "$path"; echo; fi
  done
  echo FILE=/sys/power/reboot_reason; $B cat /sys/power/reboot_reason
  echo DEBUG_RAM_MOUNT; $B grep " $D " /proc/mounts
  if [ -f "$D/listener.pid" ]; then
   pid=$($B cat "$D/listener.pid")
   case "$pid" in ''|*[!0-9]*) ;; *) echo LISTENER_STAT; $B cat "/proc/$pid/stat" "/proc/$pid/wchan" 2>/dev/null; echo;; esac
  fi
  for path in "$R/lock" "$R/supervisor.lock" "$R/source.fifo" "$R/stop" "$D/lease.done"; do [ ! -e "$path" ] || echo "EXISTS=$path"; done
  if [ -f "$R/worker.pid" ]; then
   pid=$($B cat "$R/worker.pid")
   case "$pid" in ''|*[!0-9]*) ;; *) echo WORKER_STAT; $B cat "/proc/$pid/stat" "/proc/$pid/wchan" 2>/dev/null; echo;; esac
  fi
  for name in probe.uptime probe.rc probe.err; do
   if [ -f "$D/$name" ]; then echo "FILE=$name"; $B tail -c 1000 "$D/$name"; echo; fi
  done
  if [ -f "$D/full-info.txt" ]; then
   bytes=$($B wc -c < "$D/full-info.txt")
   echo "FULL_INFO_BYTES=$bytes"
   if [ "$bytes" -gt 8000 ]; then echo FULL_INFO_TRUNCATED=1; else echo FULL_INFO_TRUNCATED=0; fi
   echo FILE=full-info.txt
   $B tail -c 8000 "$D/full-info.txt"; echo
  fi
  echo A7C_DEBUG_END;;
 PROBE)
  idle || exit 2
  $B cat /proc/uptime > "$D/probe.uptime"
  "$D/probe" full-info > "$D/full-info.txt" 2> "$D/probe.err"
  rc=$?; printf '%s\n' "$rc" > "$D/probe.rc"
  exit "$rc";;
 START)
  idle || exit 2
  [ -f "$U/enabled" ] || exit 3
  /bin/ash "$U/supervisor.sh" --start > "$D/uploader-supervisor.log" 2>&1 &
  echo "STARTED=$!";;
 PAUSE)
  if runtime_mounted; then : > "$R/stop"
  elif $B grep -q " $R " /proc/mounts; then exit 4
  fi;;
 UPDATE)
  # Fixed worker artifact only. SHA is validated before shell dispatch and again here.
  digest=$2
  case "$digest" in *[!0-9a-f]*|'') exit 64;; esac
  [ "${#digest}" = 64 ] || exit 64
  idle || exit 2
  "$D/net" get worker.sh "$D/worker.next" 8 || exit 5
  [ "$($B wc -c < "$D/worker.next")" -le 32768 ] || exit 6
  actual=$($B sha256sum "$D/worker.next"); actual=${actual%% *}
  [ "$actual" = "$digest" ] || exit 7
  /bin/ash -n "$D/worker.next" || exit 8
  $B cp "$U/worker.sh" "$U/worker.previous.sh" || exit 9
  $B cp "$D/worker.next" "$U/worker.next" || exit 10
  actual=$($B sha256sum "$U/worker.next"); actual=${actual%% *}
  [ "$actual" = "$digest" ] || exit 11
  $B chmod 644 "$U/worker.next" || exit 12
  $B mv "$U/worker.next" "$U/worker.sh" || exit 13
  $B rm -f "$D/worker.next"
  echo "INSTALLED=$digest";;
 *) exit 64;;
esac
