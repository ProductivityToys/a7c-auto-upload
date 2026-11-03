#!/bin/ash
# Existing upload request -> native progress mailbox. No screenshots or NAND I/O.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
U=/setting/a7c-uploader/ram
N=$D/native-service
umask 077
trap '' HUP
[ "$#" = 1 ] && [ "$($B cat "$U/display.active")" = "$1" ] || exit 86
[ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$N/boot-id")" ] || exit 91
[ "$($B pidof im.elf)" = "$($B cat "$N/im.pid")" ] || exit 91
$B mkdir "$D/maintenance" || exit 92
safe=0
finish() {
 result=$?
 [ "$safe" != 1 ] || $B rmdir "$D/maintenance"
 echo "NATIVE_SERVICE_CONSUMER rc=$result indicator_restored=$safe"
}
trap finish EXIT
rc=0
"$N/probe" --service-upload "$($B cat "$N/im.pid")" > "$N/upload.log" 2>&1 || rc=$?
if $B grep -qx 'SERVICE_UPLOAD_DONE progress=0 guardian=0 capture=0 idle=1' "$N/upload.log"; then safe=1; fi
$B tail -c 2500 "$N/upload.log"
exit "$rc"
