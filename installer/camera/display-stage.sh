#!/bin/ash
# Native renderer staging; no DDS test tools, screenshots or network listener.
B=/bin/busybox
P=/setting/a7c-display
U=/setting/a7c-uploader/ram
G=/setting/a7c-debug/ram
D=$G/dds-once
umask 077
cd / || exit 90
fail() { echo "DISPLAY_STAGE_REJECTED $1"; exit 90; }
private() {
 [ ! -L "$1" ] || return 1
 details=$($B ls -ldn "$1") || return 1
 read mode links uid gid rest <<META
$details
META
 [ "$mode" = "$2" ] && [ "$uid" = 0 ] && [ "$gid" = 0 ]
}
$B grep -q "^a7c-upload-ram $U tmpfs " /proc/mounts || fail uploader_mount
$B grep -q "^a7c-debug-ram $G tmpfs " /proc/mounts || fail display_parent
private "$P" drwx------ && private "$P/enabled" -rw------- || fail permissions
[ "$($B cat "$P/enabled")" = a7c-upload-display-v1 ] || fail enabled
count=0; seen=' '
while read -r hash name extra; do
 [ -z "$extra" ] && [ "${#hash}" = 64 ] || fail manifest
 case "$hash" in *[!a-f0-9]*) fail digest;; esac
 case "$name" in native-probe|native-module.so|native-start.sh|consumer.sh|native.sha256|redraw) ;; *) fail member;; esac
 case "$seen" in *" $name "*) fail duplicate;; esac
 seen="$seen$name "; count=$((count+1))
 private "$P/$name" -rw------- || fail payload_permissions
 actual=$($B sha256sum "$P/$name"); [ "${actual%% *}" = "$hash" ] || fail source_hash
done < "$P/manifest"
[ "$count" = 6 ] || fail member_count
count=0
while read -r hash path extra; do
 [ -z "$extra" ] && [ "${#hash}" = 64 ] || fail firmware_manifest
 case "$path" in /usr/lib/libObj.so|/usr/lib/libosal_uipc.so|/usr/kmod/utimer.ko|/lib/libc-2.11.2.so|/lib/librt-2.11.2.so|/usr/bin/testcmd.elf|/usr/lib/libtestcmd.so|/usr/bin/im.elf|/usr/lib/libIMDB.so) ;; *) fail firmware_path;; esac
 actual=$($B sha256sum "$path"); [ "${actual%% *}" = "$hash" ] || fail firmware_hash
 count=$((count+1))
done < "$P/native.sha256"
[ "$count" = 9 ] || fail firmware_count
if ! $B grep -q "^a7c-display-ram $D tmpfs " /proc/mounts; then
 $B grep -q " $D " /proc/mounts && fail foreign_runtime
 [ ! -L "$D" ] || fail link
 [ -d "$D" ] || $B mkdir "$D" || fail mkdir
 [ -z "$($B ls -A "$D")" ] || fail runtime_not_empty
 $B mount -n -t tmpfs -o size=4096k,mode=0700,nosuid,nodev a7c-display-ram "$D" || fail mount
fi
bundle=$($B sha256sum "$P/manifest"); bundle=${bundle%% *}
if [ -e "$D/bundle.digest" ]; then
 [ "$($B cat "$D/bundle.digest")" = "$bundle" ] || fail different_session
else
 [ -z "$($B ls -A "$D")" ] || fail partial_runtime
 while read -r hash name extra; do
  $B cp "$P/$name" "$D/$name.next" || fail copy
  actual=$($B sha256sum "$D/$name.next"); [ "${actual%% *}" = "$hash" ] || fail ram_hash
  $B chmod 700 "$D/$name.next" && $B mv "$D/$name.next" "$D/$name" || fail publish
 done < "$P/manifest"
 $B cat /proc/sys/kernel/random/boot_id > "$D/boot-id"
 printf '%s\n' "$bundle" > "$D/bundle.digest"
fi
$B cp "$D/consumer.sh" "$U/upload-display.next" && $B chmod 700 "$U/upload-display.next" &&
 $B mv "$U/upload-display.next" "$U/upload-display.sh" || fail consumer
/bin/ash "$D/native-start.sh" > "$D/native-start.log" 2>&1
echo "DISPLAY_NATIVE_START rc=$?"
exit 0
