#!/bin/ash
# Wi-Fi diagnostics. Fixed files only: never prints FTP passwords, the pairing
# token, media contents or environment. PROBE makes one FTP control-connection
# check (login + NOOP). START relaunches the installed uploader supervisor,
# only when enabled and no supervisor/worker/transfer state exists.
B=/bin/busybox
P=/setting/a7c-diag
U=/setting/a7c-uploader
R=$U/ram
C=$U/plainftp
D=$R/diag
G=/setting/a7c-debug/ram/dds-once
umask 077
section() {
 # $1 label, $2 path, $3 byte limit (tail)
 if [ -f "$2" ]; then
  echo "== $1 ($($B wc -c < "$2") bytes)"
  $B tail -c "$3" "$2"; echo
 fi
}
proc_cpu() {
 # $1 label, $2 pid: utime stime cutime cstime in clock ticks (fields 14-17).
 local cpu_line cpu_rest
 case "$2" in ''|*[!0-9]*) return 0;; esac
 IFS= read -r cpu_line < "/proc/$2/stat" 2>/dev/null || return 0
 cpu_rest=${cpu_line##*) }
 set -- "$1" "$2" $cpu_rest
 [ "$#" -ge 17 ] || return 0
 local label=$1 pid=$2; shift 13
 echo "proc $label pid=$pid utime=$1 stime=$2 cutime=$3 cstime=$4"
}
load() {
 echo '== load'
 echo "uptime=$($B cat /proc/uptime)"
 echo "loadavg=$($B cat /proc/loadavg)"
 $B grep '^cpu' /proc/stat
 proc_cpu supervisor "$($B cat "$R/supervisor.pid" 2>/dev/null)"
 proc_cpu worker "$($B cat "$R/plain.worker.pid" 2>/dev/null)"
 proc_cpu diag "$($B cat "$D/listener.pid" 2>/dev/null)"
 proc_cpu im "$($B pidof im.elf 2>/dev/null)"
}
alive() {
 # $1 pid file, $2 required cmdline fragment
 local pid
 pid=$($B cat "$1" 2>/dev/null) || return 1
 case "$pid" in ''|*[!0-9]*) return 1;; esac
 [ -r "/proc/$pid/cmdline" ] && $B grep -q "$2" "/proc/$pid/cmdline" && echo "$pid"
}
status() {
 echo A7C_DIAG_V1
 echo "uptime=$($B cat /proc/uptime)"
 echo "boot_id=$($B cat /proc/sys/kernel/random/boot_id)"
 version=$($B sed -n 's/^  "version": "\(.*\)"$/\1/p' "$U/installed.json" 2>/dev/null)
 echo "installed=${version:-unknown}"
 echo "upload_enabled=$([ -f "$U/enabled" ] && echo 1 || echo 0) display_enabled=$([ -f /setting/a7c-display/enabled ] && echo 1 || echo 0)"
 photos=$($B sed -n 6p "$C/config" 2>/dev/null)
 echo "photos=${photos:-0}"
 echo "supervisor=$(alive "$R/supervisor.pid" "$U/supervisor.sh" || echo none) worker=$(alive "$R/plain.worker.pid" plain-worker.sh || echo none)"
 echo "worker_sha256=$($B sha256sum "$R/plain-worker.sh" 2>/dev/null | $B sed 's/ .*//')"
 for path in "$R/lock" "$R/supervisor.lock" "$R/source.fifo" "$R/network.fifo" "$R/stop" "$R/display.active" "$R/display.disabled"; do
  [ ! -e "$path" ] || echo "exists=${path#$R/}"
 done
 echo "ftp_health=$($B cat "$R/ftp-health" 2>/dev/null || echo unknown)"
 echo "worker_exit=$($B cat "$R/worker.exit" 2>/dev/null || echo none)"
 # 91 = display failed and the whole service stopped. A retained display
 # maintenance lock means the native indicator was not restored; only a full
 # power cycle (battery out) clears it, so START would fail again.
 echo "display_lock=$([ -d "$G/maintenance" ] && echo held || echo free) display_consumer_rc=$($B cat "$G/native-rect-v19/consumer.rc" 2>/dev/null || echo none)"
 echo "wlan0_ifindex=$($B cat /sys/class/net/wlan0/ifindex 2>/dev/null || echo absent)"
 echo "usb_speed=$($B cat /sys/class/udc/dwc3.0/current_speed 2>/dev/null)"
 section route /proc/net/route 2048
 section arp /proc/net/arp 2048
 section wireless /proc/net/wireless 1024
 if [ -f /proc/net/snmp ]; then echo '== tcp'; $B grep '^Tcp:' /proc/net/snmp; fi
 section last_probe "$D/probe.txt" 1024
 section discovery "$R/discovery.log" 512
 section events "$R/events.log" 4096
 load
 echo A7C_DIAG_END
}
case "$1" in
 STATUS) status;;
 TRACE)
  echo A7C_DIAG_TRACE_V1
  echo "uptime=$($B cat /proc/uptime)"
  section events.previous "$R/events.previous.log" 12288
  section events "$R/events.log" 16384
  section boot_timings "$R/plain-boot-timings.log" 1024
  section worker.stdout "$R/worker.stdout" 2048
  section ftp-health-check "$R/ftp-health-check.log" 1024
  section plain-ftp "$R/plain-ftp.log" 1024
  section receipt.err "$R/receipt.err" 1024
  section query.err "$R/query.err" 1024
  section lease "$R/lease.log" 1024
  section display "$R/display.log" 1024
  section display-bootstrap "$R/display-bootstrap.log" 1024
  section timings "$R/plain-timings.log" 4096
  section receipt-copy "$R/receipt-copy.log" 2048
  section receipt.root "$R/receipt.root" 2048
  section receipt.context "$R/receipt.context" 1024
  section copy "$R/copy.log" 1024
  section relay "$R/relay.log" 1024
  section relay.result "$R/relay.result" 256
  section relay.ready "$R/relay.ready" 64
  section copy.done "$R/copy.done" 64
  section guard.done "$R/guard.done" 64
  section scan-lease "$R/scan-lease.log" 512
  section pending-rows "$R/plain.pending" 2048
  section native-start "$G/native-start.log" 1024
  section native-service.start "$G/native-service/start.log" 1024
  section native-service.ready "$G/native-service/ready.log" 1024
  section ftp-health-display "$R/ftp-health-display.log" 512
  section listener "$D/listener.log" 512
  echo A7C_DIAG_END;;
 PROBE)
  {
   IFS= read -r config_version && IFS= read -r host && IFS= read -r port &&
   IFS= read -r user && IFS= read -r root
  } < "$C/config" || { echo 'probe=no_config' > "$D/probe.txt"; status; exit 3; }
  [ -x "$R/plainftp" ] || { echo 'probe=no_client' > "$D/probe.txt"; status; exit 3; }
  IFS=' ' read -r begin rest < /proc/uptime
  "$R/plainftp" check "$host" "$port" "$user" "$root" < "$C/password" > /dev/null 2>&1; rc=$?
  IFS=' ' read -r end rest < /proc/uptime
  {
   echo "probe_ftp target=$host:$port rc=$rc start=$begin end=$end wlan0_ifindex=$($B cat /sys/class/net/wlan0/ifindex 2>/dev/null || echo absent)"
   if $B ping -c 1 -W 2 "$host" > "$D/ping.out" 2>&1; then echo "probe_ping ok $($B grep -o 'time=[0-9.]* ms' "$D/ping.out")"
   else echo "probe_ping failed_or_unavailable $($B tail -c 120 "$D/ping.out" | $B sed -n '$p')"; fi
  } > "$D/probe.txt"
  status;;
 START)
  [ -f "$U/enabled" ] && [ -f "$U/supervisor.sh" ] || { echo 'start=disabled'; status; exit 3; }
  for path in "$R/supervisor.lock" "$R/lock" "$R/plain.bootstrap.lock" "$R/display-bootstrap.lock"; do
   [ ! -e "$path" ] || { echo "start=busy ${path#$R/}"; status; exit 2; }
  done
  if [ -e "$R/source.fifo" ] || [ -e "$R/network.fifo" ]; then
   # A failed pre-copy FTP connection could leave these pipes after both
   # worker and guardian completed. Only that completed transaction may be
   # retired here; an uncertain native writer keeps its readers untouched.
   if [ -p "$R/source.fifo" ] && [ -p "$R/network.fifo" ] &&
      [ -f "$R/copy.done" ] && [ -f "$R/guard.done" ] &&
      $B grep -qx 'normal\|recovered' "$R/guard.done"; then
    $B rm -f "$R/source.fifo" "$R/network.fifo" || exit 2
    echo 'start_cleanup=completed_transfer'
   else echo 'start=busy transfer_incomplete'; status; exit 2; fi
  fi
  [ ! -d "$G/maintenance" ] || echo 'start_warning=display_lock_held cold_restart_needed'
  ( trap '' HUP; exec /bin/ash "$U/supervisor.sh" --start </dev/null >/dev/null 2>&1 ) &
  $B sleep 4
  echo 'start=requested'
  status;;
 *) exit 64;;
esac
