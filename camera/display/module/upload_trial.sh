#!/bin/ash
# One-request RAM trial. Restore the original consumer before starting, so the
# next upload uses the established display. Never installed persistently.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
U=/setting/a7c-uploader/ram
N=$D/native-rect-v18
umask 077
trap '' HUP
[ "$#" = 1 ] && [ "$($B cat "$U/display.active")" = "$1" ] || exit 86
[ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$N/boot-id")" ] || exit 91
[ "$($B sha256sum "$N/consumer.original" | $B cut -d ' ' -f1)" = d9a38c12201c36b11f07492184fb3ebea7aa926b889b1cc049c2245bb025a2bc ] || exit 94
$B cp "$N/consumer.original" "$U/upload-display.next" &&
$B chmod 700 "$U/upload-display.next" &&
$B mv "$U/upload-display.next" "$U/upload-display.sh" || exit 95
$B mkdir "$D/maintenance" || exit 92
safe=0
finish() {
 result=$?
 echo "$result" > "$N/consumer.rc"
 [ "$safe" != 1 ] || $B rmdir "$D/maintenance"
 echo "NATIVE_CONSUMER_DONE rc=$result native_restored=$safe original_consumer_restored=1"
}
trap finish EXIT
p=$($B pidof im.elf)
[ "$p" = "$($B cat "$N/im.pid")" ] || { safe=1; exit 91; }
echo $$ > "$N/consumer.pid"
"$N/sampler" "$p" 06015000 > "$N/sampler.log" 2>&1 &
echo $! > "$N/sampler.pid"
rc=0
"$N/probe" --once "$p" > "$N/result.log" 2>&1 || rc=$?
echo "$rc" > "$N/trial.rc"
if $B grep -qx 'MODULE_DONE install=0 load=0 restore=0 unload=0 marker=0 guardian=0 remaining=0' "$N/result.log"; then
 safe=1
 for frame in before during after; do
  [ ! -f "$N/$frame.raw" ] || $B mv "$N/$frame.raw" "$D/dds-$frame.raw" || exit 98
 done
fi
$B tail -c 12000 "$N/result.log"
exit "$rc"
