#!/bin/ash
# Persistent idle listener; no automatic network traffic or power lease.
B=/bin/busybox
P=/setting/a7c-debug
D=/setting/a7c-debug/ram
trap '' HUP
[ -f "$P/enabled" ] || exit 90
# The vendor unmounts /tmp_network when Wi-Fi stops; executing from it pins
# that mount and eventually crashes im.elf. Use an owned tmpfs instead.
# Installer creates the empty mountpoint; never write runtime files to NAND.
if ! $B grep -q "^a7c-debug-ram $D tmpfs " /proc/mounts; then
 $B grep -q " $D " /proc/mounts && exit 90
 [ -d "$D" ] && [ -z "$($B ls -A "$D")" ] || exit 90
 $B mount -n -t tmpfs -o size=1024k,mode=0700,nosuid,nodev a7c-debug-ram "$D" || exit 90
fi
$B grep -q "^a7c-debug-ram $D tmpfs " /proc/mounts || exit 90
cd / || exit 90
$B mkdir "$D/lock" || exit 90
# Optional, explicit installation trial only. Production has no trial file.
# Count attempts before launch so repeated firmware restarts cannot run forever.
if [ -f "$P/trial-starts" ]; then
 trial=$($B cat "$P/trial-starts")
 case "$trial" in
  1|2|3) printf '%s\n' "$((trial-1))" > "$P/trial-starts" || exit 91;;
  *) $B rm -f "$P/enabled"; printf 'revision=debug-v6 stage=trial-exhausted\n' > "$P/last-session.txt"; $B rmdir "$D/lock"; exit 91;;
 esac
fi
for f in listener lease net probe; do $B cp "$P/$f" "$D/$f" && $B chmod 700 "$D/$f" || { $B rmdir "$D/lock"; exit 90; }; done
$B rm -f "$D/stop"
printf 'revision=debug-v6 stage=start\n' > "$P/last-session.txt"
"$D/listener"
rc=$?
printf 'revision=debug-v6 stage=finished rc=%s\n' "$rc" > "$P/last-session.txt"
$B rmdir "$D/lock"
exit "$rc"
