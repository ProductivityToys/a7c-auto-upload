#!/bin/ash
# Bind the native indicator once at uploader startup; no idle daemon or lease.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
U=/setting/a7c-uploader/ram
N=$D/native-service
M=/tmp_bt/a70.so
umask 077
$B grep -q "^a7c-display-ram $D tmpfs " /proc/mounts || exit 90
$B grep -q '^none /tmp_bt tmpfs ' /proc/mounts || exit 90
[ ! -e "$U/display.active" ] || exit 92
$B mkdir "$D/native-start.lock" || exit 92
trap '$B rmdir "$D/native-start.lock"' EXIT
[ -d "$N" ] || $B mkdir "$N" || exit 95
expected=$($B sha256sum "$D/native-module.so");expected=${expected%% *}
if [ -e "$M" ]; then
 actual=$($B sha256sum "$M");[ "${actual%% *}" = "$expected" ] || exit 94
else
 # Never recreate an unlinked mapping at the same pathname in this boot.
 p=$($B pidof im.elf)
 [ -z "$p" ] || ! $B grep -q "$M" /proc/$p/maps || exit 94
 $B cp "$D/native-module.so" "$M.next" && $B chmod 500 "$M.next" && $B mv "$M.next" "$M" || exit 96
fi
$B cp "$D/native-probe" "$N/probe.next" && $B chmod 500 "$N/probe.next" && $B mv "$N/probe.next" "$N/probe" || exit 96
$B cat /proc/sys/kernel/random/boot_id > "$N/boot-id"
n=0
while [ "$n" -lt 15 ]; do
 p=$($B pidof im.elf)
 case "$p" in ''|*[!0-9]*) ;; *)
  if "$N/probe" --service-ready "$p" > "$N/ready.log" 2>&1; then break; fi;;
 esac
 n=$((n+1));$B sleep 1
done
[ "$n" -lt 15 ] || exit 75
# A retired module stays mapped until reboot. Its init/handoff are one-shot;
# do not invoke init again after an uninstall in this same camera session.
if "$N/probe" --inspect-marker "$p" > "$N/retired.log" 2>&1; then
 echo NATIVE_SERVICE_RETIRED
 exit 78
fi
printf '%s\n' "$p" > "$N/im.pid"
"$N/probe" --service-on "$p" > "$N/start.log" 2>&1 || exit 77
$B cat "$U/worker.pid" > "$N/owner"
if [ "$($B cat "$U/ftp-health" 2>/dev/null)" = error ]; then
 "$N/probe" --service-error "$p" > "$N/health.log" 2>&1 || :
fi
echo NATIVE_SERVICE_READY
