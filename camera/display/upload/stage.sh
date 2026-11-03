#!/bin/ash
# Optional boot staging under the existing uploader supervisor. No native writes.
B=/bin/busybox
P=/setting/a7c-display
U=/setting/a7c-uploader/ram
G=/setting/a7c-debug/ram
D=/setting/a7c-debug/ram/dds-once
umask 077
cd / || exit 90
private() {
 [ ! -L "$1" ] || return 1
 details=$($B ls -ldn "$1") || return 1
 read mode links uid gid rest <<META
$details
META
 [ "$mode" = "$2" ] && [ "$uid" = 0 ] && [ "$gid" = 0 ]
}
fail() { echo "DISPLAY_STAGE_REJECTED $1"; exit 90; }
[ "$#" = 0 ] || fail arguments
$B grep -q "^a7c-upload-ram $U tmpfs " /proc/mounts || fail uploader_mount
[ ! -e "$U/display.active" ] || fail active
private "$P" drwx------ && private "$P/enabled" -rw------- &&
private "$P/manifest" -rw------- || fail permissions
[ "$($B cat "$P/enabled")" = a7c-upload-display-v1 ] || fail enabled
# Verify every persistent payload before mounting/publishing anything.
count=0; seen=' '
while read -r hash name extra; do
 [ -z "$extra" ] && [ "${#hash}" = 64 ] || fail manifest
 case "$hash" in *[!a-f0-9]*) fail digest;; esac
 case "$name" in capture|redraw|listener|launch|blink-launch|ui-layout|collector.sh|action.sh|manage.sh|blink-worker.sh|prepare.sh|consumer.sh|native-start.sh|native-probe|native-module.so|native.sha256) ;; *) fail payload;; esac
 case "$seen" in *" $name "*) fail duplicate;; esac
 seen="$seen$name ";count=$((count+1))
 private "$P/$name" -rw------- || fail payload_permissions
 actual=$($B sha256sum "$P/$name");[ "${actual%% *}" = "$hash" ] || fail source_hash
done < "$P/manifest"
[ "$count" = 16 ] || fail count
count=0;seen=' '
while read -r hash path extra; do
 [ -z "$extra" ] && [ "${#hash}" = 64 ] || fail native_manifest
 case "$hash" in *[!a-f0-9]*) fail native_digest;; esac
 case "$path" in /usr/lib/libObj.so|/usr/lib/libosal_uipc.so|/usr/kmod/utimer.ko|/lib/libc-2.11.2.so|/lib/librt-2.11.2.so|/usr/bin/testcmd.elf|/usr/lib/libtestcmd.so|/usr/bin/im.elf|/usr/lib/libIMDB.so) ;; *) fail native_path;; esac
 case "$seen" in *" $path "*) fail native_duplicate;; esac
 seen="$seen$path ";count=$((count+1))
 actual=$($B sha256sum "$path");[ "${actual%% *}" = "$hash" ] || fail native_hash
done < "$P/native.sha256"
[ "$count" = 9 ] || fail native_count
bundle=$($B sha256sum "$P/manifest");bundle=${bundle%% *}
# The debugger supervisor is the only owner allowed to create its parent
# mount. A concurrent second mount would hide its live listener and logs.
n=0
while ! $B grep -q "^a7c-debug-ram $G tmpfs " /proc/mounts; do
 $B grep -q " $G " /proc/mounts && fail foreign_parent
 [ "$n" -lt 3 ] || fail parent_not_ready
 $B sleep 1;n=$((n+1))
done
$B mkdir "$G/display-stage.lock" || fail stage_busy
trap '$B rmdir "$G/display-stage.lock"' EXIT
if ! $B grep -q "^a7c-display-ram $D tmpfs " /proc/mounts; then
 $B grep -q " $D " /proc/mounts && fail foreign_runtime
 [ ! -L "$D" ] || fail runtime_link
 [ -d "$D" ] || $B mkdir "$D" || fail runtime_directory
 [ -z "$($B ls -A "$D")" ] || fail runtime_not_empty
 $B mount -n -t tmpfs -o size=4096k,mode=0700,nosuid,nodev a7c-display-ram "$D" || fail runtime_mount
fi
$B grep -q "^a7c-display-ram $D tmpfs " /proc/mounts || fail runtime_verify
if [ -f "$D/bundle.digest" ]; then
 # Reuse the same session, including accepted wireless updates and proofs.
 [ "$($B cat "$D/bundle.digest")" = "$bundle" ] || fail different_bundle
 [ "$($B cat "$D/boot-id")" = "$($B cat /proc/sys/kernel/random/boot_id)" ] || fail old_boot
else
 [ -z "$($B ls -A "$D")" ] || fail partial_runtime
 while read -r hash name extra; do
  $B cp "$P/$name" "$D/$name.next" || fail copy
  actual=$($B sha256sum "$D/$name.next");[ "${actual%% *}" = "$hash" ] || fail ram_hash
  $B chmod 700 "$D/$name.next" && $B mv "$D/$name.next" "$D/$name" || fail publish
 done < "$P/manifest"
 $B cat /proc/sys/kernel/random/boot_id > "$D/boot-id" || fail boot_id
 printf '1\n' > "$D/enabled" || fail listener_enable
 printf '1\n' > "$D/shooting-overlay"; printf '300\n' > "$D/continuous-blink"
 printf '%s\n' "$bundle" > "$D/bundle.digest" || fail bundle
fi
# Publish the optional consumer last. It retries read-only native binding on
# an actual transfer if im.elf was not ready during this boot-stage attempt.
$B cp "$D/consumer.sh" "$U/upload-display.next" &&
$B chmod 700 "$U/upload-display.next" &&
$B mv "$U/upload-display.next" "$U/upload-display.sh" || fail consumer
echo DISPLAY_STAGE_READY
/bin/ash "$D/prepare.sh" > "$D/prepare.log" 2>&1
r=$?; echo "DISPLAY_PREPARE rc=$r"
/bin/ash "$D/native-start.sh" > "$D/native-start.log" 2>&1
echo "DISPLAY_NATIVE_START rc=$?"
# Native readiness is optional; staging failure never blocks ordinary FTP.
exit 0
