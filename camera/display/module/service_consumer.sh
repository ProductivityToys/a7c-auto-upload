#!/bin/ash
# RAM native service consumer. Module stays loaded between upload requests.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
U=/setting/a7c-uploader/ram
N=$D/native-rect-v19
umask 077
trap '' HUP
[ "$#" = 1 ] && [ "$($B cat "$U/display.active")" = "$1" ] || exit 86
[ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$N/boot-id")" ] || exit 91
$B mkdir "$D/maintenance" || exit 92
safe=0
finish() {
 result=$?
 echo "$result" > "$N/consumer.rc"
 [ "$safe" != 1 ] || $B rmdir "$D/maintenance"
 echo "NATIVE_SERVICE_CONSUMER rc=$result indicator_restored=$safe"
}
trap finish EXIT
p=$($B pidof im.elf)
[ "$p" = "$($B cat "$N/im.pid")" ] || { safe=1; exit 91; }
for frame in before during after; do $B rm -f "$N/$frame.raw"; done
rc=0
"$N/probe" --service-upload "$p" > "$N/upload.log" 2>&1 || rc=$?
if $B grep -qx 'SERVICE_UPLOAD_DONE progress=0 guardian=0 capture=0 idle=1' "$N/upload.log"; then
 safe=1
 for frame in before during after; do
  [ ! -f "$N/$frame.raw" ] || $B mv "$N/$frame.raw" "$D/dds-$frame.raw" || exit 98
 done
fi
$B tail -c 12000 "$N/upload.log"
exit "$rc"
