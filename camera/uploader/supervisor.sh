#!/bin/ash
# Bounded restart count, no repeated restart on an unknown native-copy state.
B=/bin/busybox
P=/setting/a7c-uploader
D=/setting/a7c-uploader/ram
trap '' HUP
# A private tmpfs avoids pinning the vendor's unmounted-on-idle network RAM.
# The empty underlying directory is installed once. Never fall back to NAND.
[ -f "$P/enabled" ] || exit 90
if ! $B grep -q "^a7c-upload-ram $D tmpfs " /proc/mounts; then
 $B grep -q " $D " /proc/mounts && exit 90
 [ -d "$D" ] && [ -z "$($B ls -A "$D")" ] || exit 90
 $B mount -n -t tmpfs -o size=2048k,mode=0700,nosuid,nodev a7c-upload-ram "$D" || exit 90
fi
$B grep -q "^a7c-upload-ram $D tmpfs " /proc/mounts || exit 90
cd / || exit 90
$B mkdir "$D/supervisor.lock" || exit 90
[ "$1" != --start ] || $B rm -f "$D/stop" "$D/worker.exit"
echo "$$" > "$D/supervisor.pid"
attempt=0
while [ "$attempt" -lt 3 ] && [ -f "$P/enabled" ] && [ ! -f "$D/stop" ]; do
 attempt=$((attempt+1))
 /bin/ash "$P/worker.sh" > "$D/worker.stdout" 2>&1 & worker=$!
 echo "$worker" > "$D/worker.pid"
 wait "$worker"; rc=$?
 echo "$rc" > "$D/worker.exit"
 case "$rc" in 42|90) break;; esac
 # Never overlap a crashed worker's source reader or native operation.
 [ ! -e "$D/source.fifo" ] && [ ! -e "$D/lock" ] || break
 $B sleep 60
done
$B rmdir "$D/supervisor.lock"
