#!/bin/ash
# Bind only untouched native DDS; no display messages, power lease or NAND log.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
umask 077
cd / || exit 75
$B grep -q "^a7c-display-ram $D tmpfs " /proc/mounts || exit 75
[ "$($B cat "$D/boot-id")" = "$($B cat /proc/sys/kernel/random/boot_id)" ] || exit 75
p=$($B pidof im.elf)
case "$p" in ''|*[!0-9]*) exit 75;; esac
[ "$p" -gt 1 ] && [ "$($B readlink /proc/$p/exe)" = /usr/bin/im.elf ] || exit 75
IFS= read -r stat < "/proc/$p/stat" || exit 75
stat=${stat##*) };set -- $stat
[ "$#" -ge 20 ] || exit 75
shift 19;start=$1
case "$start" in ''|*[!0-9]*) exit 75;; esac
if [ -f "$D/native.ready" ]; then
 [ "$p" = "$($B cat "$D/native.pid")" ] &&
 [ "$start" = "$($B cat "$D/native.start")" ] || exit 75
 exit 0
fi
# Do not reset a diagnostic/manual claim or overlap an initializing consumer.
[ ! -d "$D/claimed" ] && [ ! -d "$D/maintenance" ] || exit 75
$B mkdir "$D/init.lock" || exit 75
trap '$B rmdir "$D/init.lock"' EXIT
base=;matches=0
while read -r range permissions offset device inode path; do
 if [ "$path" = /usr/lib/libObj.so ] && [ "$offset" = 00000000 ]; then
  case "$permissions" in r-xp|r--p) ;; *) continue;; esac
  base=${range%-*};matches=$((matches+1))
 fi
done < "/proc/$p/maps"
[ "$matches" = 1 ] || exit 75
case "$base" in ''|*[!0-9a-f]*) exit 75;; esac
"$D/capture" --inspect "$p" "$base" > "$D/initial-inspect.log" 2>&1 || exit 75
read state attached timer_field first_field rest < "$D/initial-inspect.log" || exit 75
timer=${timer_field#timer=}
case "$timer" in ''|*[!0-9]*) exit 75;; esac
[ "$timer" -gt 0 ] && [ "$timer" -lt 512 ] || exit 75
$B grep -qx "DDS_STATE attached timer=$timer first=1 override=0 visible=0 others_idle=1" "$D/initial-inspect.log" &&
$B grep -qx 'DDS_FONT original_matches=1 bytes=128' "$D/initial-inspect.log" &&
$B grep -qx 'DDS_POSITION original_matches=1 x=30 y=250' "$D/initial-inspect.log" || exit 75
printf '%s\n' "$start" > "$D/native.start"
printf '%s\n' "$p" > "$D/native.pid"; printf '%s\n' "$base" > "$D/native.base"
printf '%s\n' "$timer" > "$D/native.timer"; printf '%s\n' --once-shooting > "$D/native.mode"
[ -f "$D/enabled" ] && [ ! -e "$D/stop" ] || exit 75
/bin/ash "$D/collector.sh" --check || exit 75
# Launch at most once per staged session. If startup was slow, the next
# real upload may observe readiness, but never starts a duplicate listener.
if [ ! -e "$D/listener.started" ]; then
 [ ! -d "$D/running" ] || exit 75
 : > "$D/listener.started" || exit 75
 "$D/launch" || exit 75
fi
# Bounded readiness check. The listener subsequently blocks without idle polls.
n=0
while [ "$n" -lt 3 ]; do
 if [ -f "$D/listener.pid" ]; then
  listener=$($B cat "$D/listener.pid")
  case "$listener" in ''|*[!0-9]*) exit 75;; esac
  if [ "$($B readlink /proc/$listener/exe)" = "$D/listener" ] && $B kill -0 "$listener"; then
   echo native_ready=1 > "$D/native.ready"; echo DISPLAY_NATIVE_READY; exit 0
  fi
 fi
 $B sleep 1;n=$((n+1))
done
exit 75
