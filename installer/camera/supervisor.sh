#!/bin/ash
# Installer-owned startup. Upload and native indicator only; no Wi-Fi debugger.
B=/bin/busybox
P=/setting/a7c-uploader
D=$P/ram
G=/setting/a7c-debug/ram
umask 077
trap '' HUP
[ -f "$P/enabled" ] || exit 90
ram_mount() {
 source=$1; target=$2; size=$3
 $B grep -q "^$source $target tmpfs " /proc/mounts && return 0
 $B grep -q " $target " /proc/mounts && return 1
 [ ! -L "$target" ] && [ -d "$target" ] && [ -z "$($B ls -A "$target")" ] || return 1
 $B mount -n -t tmpfs -o "size=$size,mode=0700,nosuid,nodev" "$source" "$target"
}
ram_mount a7c-upload-ram "$D" 2048k || exit 90
# The display binaries retain this internal RAM pathname. No debug launcher,
# token, listener or NAS service is installed or started.
if [ -f /setting/a7c-display/enabled ]; then
 ram_mount a7c-debug-ram "$G" 1024k || exit 90
fi
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
 [ ! -e "$D/source.fifo" ] && [ ! -e "$D/lock" ] || break
 $B sleep 60
done
$B rmdir "$D/supervisor.lock"
