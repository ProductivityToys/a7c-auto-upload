#!/bin/ash
# Wireless native display diagnostics; ordinary transfers use no image capture.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
U=/setting/a7c-uploader/ram
N=$D/native-service
umask 077
echo A7C_DEBUG_V2
(
[ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$N/boot-id")" ] || exit 91
p=$($B pidof im.elf);[ "$p" = "$($B cat "$N/im.pid")" ] || exit 91
case "$1" in
STATUS)
 echo NATIVE_SERVICE; "$N/probe" --inspect-service "$p" | $B tail -n 7
 echo OWNER; $B cat "$N/owner"
 for f in start.log preview.log upload.log; do [ ! -f "$N/$f" ] || { echo "$f"; $B tail -c 2200 "$N/$f"; }; done
 exit 0;;
PROBE)
 [ ! -e "$U/display.active" ] || exit 92
 $B mkdir "$D/maintenance" || exit 92
 for f in before during after; do $B rm -f "$N/$f.raw"; done
 "$N/probe" --service-on "$p" > "$N/bind.log" 2>&1 &&
 "$N/probe" --service-preview "$p" > "$N/preview.log" 2>&1
 rc=$?
 for f in before during after; do [ ! -f "$N/$f.raw" ] || $B mv "$N/$f.raw" "$D/dds-$f.raw" || exit 98; done
 [ "$rc" != 0 ] || $B rmdir "$D/maintenance"
 exit "$rc";;
PAUSE)
 [ ! -e "$U/display.active" ] || exit 92
 "$N/probe" --service-off "$p" > "$N/off.log" 2>&1;;
*) exit 64;;
esac
)
echo NATIVE_ACTION_RC=$?
echo A7C_DEBUG_END
