#!/bin/ash
# 0.4.0-home.1 -> exact 0.3.8-home.1. Requires cooperative uploader pause.
# Invoke as authenticated display action PROBE; STATUS is read-only.
B=/bin/busybox
P=/setting/a7c-display
K=$P/native-backup-038
D=/setting/a7c-debug/ram/dds-once
U=/setting/a7c-uploader/ram
N=$D/native-service
umask 077
echo A7C_DEBUG_V2
(
if [ "$1" = STATUS ]; then
 if [ -f "$U/native-rollback.log" ]; then $B cat "$U/native-rollback.log"; else echo ROLLBACK_READY_REQUIRES_UPLOADER_PAUSED; fi
 exit 0
fi
[ "$1" = PROBE ] || exit 64
[ -e "$U/stop" ] && [ -e "$U/worker.exit" ] && [ ! -e "$U/source.fifo" ] && [ ! -e "$U/display.active" ] || exit 92
actual=$($B sha256sum "$K/action.sh"); [ "${actual%% *}" = bedb4f2016768ccedbad2484cac296809e77ba1c8491d85c6e98bda2415f92c6 ] || exit 94
actual=$($B sha256sum "$K/blink-launch"); [ "${actual%% *}" = 36d83cd4ab2afa6000c192e5f364d75c135999d20e96ba04447ff8f98e01bf5f ] || exit 94
actual=$($B sha256sum "$K/blink-worker.sh"); [ "${actual%% *}" = 8ee58f169b050c713d0479659f2411975f8766b9f3637fd319a037eb2e68652f ] || exit 94
actual=$($B sha256sum "$K/capture"); [ "${actual%% *}" = 3e6fce722d16e1d06148b154435b4214b8232a64be8a4d094e8b7c917664c9d5 ] || exit 94
actual=$($B sha256sum "$K/collector.sh"); [ "${actual%% *}" = 82ddf4d1671edb18c453b8c19c494ead1a0b89ac817835db31ade4e92b8fd390 ] || exit 94
actual=$($B sha256sum "$K/consumer.sh"); [ "${actual%% *}" = d9a38c12201c36b11f07492184fb3ebea7aa926b889b1cc049c2245bb025a2bc ] || exit 94
actual=$($B sha256sum "$K/enabled"); [ "${actual%% *}" = 50f510abdf531e2aba932b5aebd618141d005b718cd2ce7394909ef4910cd022 ] || exit 94
actual=$($B sha256sum "$K/launch"); [ "${actual%% *}" = 0059929b02bdf4e42e7bde6e8341c76f55effddc877f7259f66d3092134ce263 ] || exit 94
actual=$($B sha256sum "$K/listener"); [ "${actual%% *}" = 9253b36b7bea4a532eda672f539b868fa28978dcc8052510685b418f299d48b7 ] || exit 94
actual=$($B sha256sum "$K/manage.sh"); [ "${actual%% *}" = 5d42840b74833c568b8d17cfededc2321547ff576fad9df31412d7bf42c48e76 ] || exit 94
actual=$($B sha256sum "$K/manifest"); [ "${actual%% *}" = 9d25da51e34359d26d462f256cfd0b9bf885093d5698a514a3ca13f42dcc33ba ] || exit 94
actual=$($B sha256sum "$K/native.sha256"); [ "${actual%% *}" = 5524dd3a9810eba08b120b2ecf5e4a60c9ff19508d617067d009026fc7eb17aa ] || exit 94
actual=$($B sha256sum "$K/prepare.sh"); [ "${actual%% *}" = 75cc84616379ee2a8b2d65ded1bdae784b44564b607fb06002289369f32393d3 ] || exit 94
actual=$($B sha256sum "$K/redraw"); [ "${actual%% *}" = 8de0e767d30c727bf6b915f1e7a5babe3325fd55f2abad07d23476801f30928e ] || exit 94
actual=$($B sha256sum "$K/stage.sh"); [ "${actual%% *}" = 36e9747f8bf8ce921c725068d1414fa8e677de03f71cd88602ef8b4b90896146 ] || exit 94
actual=$($B sha256sum "$K/stage.sha256"); [ "${actual%% *}" = 7221e6aa8f5c9a7456476a3f04d329fd81750b05bbd90b214847c009b6b9d630 ] || exit 94
actual=$($B sha256sum "$K/ui-layout"); [ "${actual%% *}" = a7fb993531e785c0e48039f4452860828a2c00e09920c0ae72c5445cd5b83b99 ] || exit 94
actual=$($B sha256sum "$P/action.sh"); [ "${actual%% *}" = 2d5753ea0f867b412fda3c8e71e3b5c271c7610bd6aca0fcf1c8be077e9b7776 ] || exit 94
actual=$($B sha256sum "$P/blink-launch"); [ "${actual%% *}" = 36d83cd4ab2afa6000c192e5f364d75c135999d20e96ba04447ff8f98e01bf5f ] || exit 94
actual=$($B sha256sum "$P/blink-worker.sh"); [ "${actual%% *}" = 8ee58f169b050c713d0479659f2411975f8766b9f3637fd319a037eb2e68652f ] || exit 94
actual=$($B sha256sum "$P/capture"); [ "${actual%% *}" = 3e6fce722d16e1d06148b154435b4214b8232a64be8a4d094e8b7c917664c9d5 ] || exit 94
actual=$($B sha256sum "$P/collector.sh"); [ "${actual%% *}" = 82ddf4d1671edb18c453b8c19c494ead1a0b89ac817835db31ade4e92b8fd390 ] || exit 94
actual=$($B sha256sum "$P/consumer.sh"); [ "${actual%% *}" = e7e205accd1b01de0a903b3f0c511c82d247533f09adece96aeb663e96d6d136 ] || exit 94
actual=$($B sha256sum "$P/enabled"); [ "${actual%% *}" = 50f510abdf531e2aba932b5aebd618141d005b718cd2ce7394909ef4910cd022 ] || exit 94
actual=$($B sha256sum "$P/launch"); [ "${actual%% *}" = 0059929b02bdf4e42e7bde6e8341c76f55effddc877f7259f66d3092134ce263 ] || exit 94
actual=$($B sha256sum "$P/listener"); [ "${actual%% *}" = 9253b36b7bea4a532eda672f539b868fa28978dcc8052510685b418f299d48b7 ] || exit 94
actual=$($B sha256sum "$P/manage.sh"); [ "${actual%% *}" = 5d42840b74833c568b8d17cfededc2321547ff576fad9df31412d7bf42c48e76 ] || exit 94
actual=$($B sha256sum "$P/manifest"); [ "${actual%% *}" = 7fce6446202118b9dab69092293149c1d039cae219bb31ce305c88110897cfc8 ] || exit 94
actual=$($B sha256sum "$P/native.sha256"); [ "${actual%% *}" = 92323a368e95629d176810a3b3da203b0d8fad3c8fcd2a30e2b5c6387e6e659c ] || exit 94
actual=$($B sha256sum "$P/prepare.sh"); [ "${actual%% *}" = 75cc84616379ee2a8b2d65ded1bdae784b44564b607fb06002289369f32393d3 ] || exit 94
actual=$($B sha256sum "$P/redraw"); [ "${actual%% *}" = 8de0e767d30c727bf6b915f1e7a5babe3325fd55f2abad07d23476801f30928e ] || exit 94
actual=$($B sha256sum "$P/stage.sh"); [ "${actual%% *}" = 9597c21e399d15fdc395bb3adeef7e41618eed7217e38b3ba74be7e8cdc93fa1 ] || exit 94
actual=$($B sha256sum "$P/stage.sha256"); [ "${actual%% *}" = 4eb0f20df238c2a25be57ab1c085291ff9db9c43302885c155f46e45f27d60fc ] || exit 94
actual=$($B sha256sum "$P/ui-layout"); [ "${actual%% *}" = a7fb993531e785c0e48039f4452860828a2c00e09920c0ae72c5445cd5b83b99 ] || exit 94
actual=$($B sha256sum "$P/native-start.sh"); [ "${actual%% *}" = d05b8c26221b2b8968e2b08a914f1a7636df4a667886897e8bea3a76850884c0 ] || exit 94
actual=$($B sha256sum "$P/native-probe"); [ "${actual%% *}" = 7896ee8be04d7b46ed7c8a49c5873dd13c8e9c92878158f2dc472c5383f77391 ] || exit 94
actual=$($B sha256sum "$P/native-module.so"); [ "${actual%% *}" = ab7e9e81fedab0310f400e5d8781fb6c45760630b4aec85a62aefd901d697939 ] || exit 94
p=$($B pidof im.elf)
[ "$p" = "$($B cat "$N/im.pid")" ] || exit 91
"$N/probe" --service-off "$p" > "$N/rollback-off.log" 2>&1 &&
"$N/probe" --finish-event "$p" > "$N/rollback-exit.log" 2>&1 || exit 99
$B cp "$K/action.sh" "$P/action.sh.next" && $B chmod 600 "$P/action.sh.next" && $B mv "$P/action.sh.next" "$P/action.sh" || exit 96
$B cp "$K/blink-launch" "$P/blink-launch.next" && $B chmod 600 "$P/blink-launch.next" && $B mv "$P/blink-launch.next" "$P/blink-launch" || exit 96
$B cp "$K/blink-worker.sh" "$P/blink-worker.sh.next" && $B chmod 600 "$P/blink-worker.sh.next" && $B mv "$P/blink-worker.sh.next" "$P/blink-worker.sh" || exit 96
$B cp "$K/capture" "$P/capture.next" && $B chmod 600 "$P/capture.next" && $B mv "$P/capture.next" "$P/capture" || exit 96
$B cp "$K/collector.sh" "$P/collector.sh.next" && $B chmod 600 "$P/collector.sh.next" && $B mv "$P/collector.sh.next" "$P/collector.sh" || exit 96
$B cp "$K/consumer.sh" "$P/consumer.sh.next" && $B chmod 600 "$P/consumer.sh.next" && $B mv "$P/consumer.sh.next" "$P/consumer.sh" || exit 96
$B cp "$K/enabled" "$P/enabled.next" && $B chmod 600 "$P/enabled.next" && $B mv "$P/enabled.next" "$P/enabled" || exit 96
$B cp "$K/launch" "$P/launch.next" && $B chmod 600 "$P/launch.next" && $B mv "$P/launch.next" "$P/launch" || exit 96
$B cp "$K/listener" "$P/listener.next" && $B chmod 600 "$P/listener.next" && $B mv "$P/listener.next" "$P/listener" || exit 96
$B cp "$K/manage.sh" "$P/manage.sh.next" && $B chmod 600 "$P/manage.sh.next" && $B mv "$P/manage.sh.next" "$P/manage.sh" || exit 96
$B cp "$K/native.sha256" "$P/native.sha256.next" && $B chmod 600 "$P/native.sha256.next" && $B mv "$P/native.sha256.next" "$P/native.sha256" || exit 96
$B cp "$K/prepare.sh" "$P/prepare.sh.next" && $B chmod 600 "$P/prepare.sh.next" && $B mv "$P/prepare.sh.next" "$P/prepare.sh" || exit 96
$B cp "$K/redraw" "$P/redraw.next" && $B chmod 600 "$P/redraw.next" && $B mv "$P/redraw.next" "$P/redraw" || exit 96
$B cp "$K/stage.sh" "$P/stage.sh.next" && $B chmod 600 "$P/stage.sh.next" && $B mv "$P/stage.sh.next" "$P/stage.sh" || exit 96
$B cp "$K/ui-layout" "$P/ui-layout.next" && $B chmod 600 "$P/ui-layout.next" && $B mv "$P/ui-layout.next" "$P/ui-layout" || exit 96
$B cp "$K/manifest" "$P/manifest.next" && $B chmod 600 "$P/manifest.next" && $B mv "$P/manifest.next" "$P/manifest" || exit 96
$B cp "$K/stage.sha256" "$P/stage.sha256.next" && $B chmod 600 "$P/stage.sha256.next" && $B mv "$P/stage.sha256.next" "$P/stage.sha256" || exit 96
$B rm "$P/native-start.sh" "$P/native-probe" "$P/native-module.so" || exit 96
while read h name; do
 [ "$name" != action.sh ] || continue
 $B cp "$P/$name" "$D/$name.next" && $B chmod 700 "$D/$name.next" && $B mv "$D/$name.next" "$D/$name" || exit 96
done < "$P/manifest"
actual=$($B sha256sum "$P/manifest"); printf '%s
' "${actual%% *}" > "$D/bundle.digest"
[ ! -d "$D/maintenance" ] || $B rmdir "$D/maintenance" || exit 92
echo NATIVE_ROLLBACK_038_OK > "$U/native-rollback.log"
)
echo ROLLBACK_RC=$?
echo A7C_DEBUG_END
