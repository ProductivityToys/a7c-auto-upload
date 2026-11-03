#!/bin/ash
# Optional RAM consumer, installed as uploader/ram/upload-display.sh.
# Invoked by the uploader only for an actual video transfer, never at idle.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
U=/setting/a7c-uploader/ram
umask 077
cd / || exit 90
display_mark() {
 # Optional bounded diagnostics: seven fixed markers per actual upload.
 [ -f "$U/trace-timing" ] || return 0
 local display_clock display_unused
 IFS=' ' read -r display_clock display_unused < /proc/uptime || return 0
 printf 'op=%s uptime=%s\n' "$1" "$display_clock" >> "$D/upload-timings.log" || :
}
[ ! -f "$U/trace-timing" ] || : > "$D/upload-timings.log"
display_mark consumer_begin
[ "$#" = 1 ] || exit 64
token=$1
read owner start serial limit extra <<OWNER
$token
OWNER
case "$owner:$start:$serial:$limit" in *[!0-9:]*|:*|*::*) exit 64;; esac
[ -z "$extra" ] && [ "$owner" -gt 1 ] && [ "$start" -gt 0 ] &&
[ "$serial" -gt 0 ] && [ "$limit" -ge 240 ] && [ "$limit" -le 86000 ] || exit 64
$B grep -q "^a7c-display-ram $D tmpfs " /proc/mounts &&
$B grep -q "^a7c-upload-ram $U tmpfs " /proc/mounts || exit 90
owner_active() {
 [ ! -e "$U/stop" ] && [ ! -e "$D/cancel" ] || return 1
 [ "$($B cat "$U/display.active" 2>/dev/null)" = "$token" ] || return 1
 kill -0 "$owner" 2>/dev/null || return 1
 IFS= read -r owner_stat < "/proc/$owner/stat" || return 1
 owner_stat=${owner_stat##*) }
 set -- $owner_stat
 [ "$#" -ge 20 ] || return 1
 shift 19
 [ "$1" = "$start" ]
}
now_seconds() {
 read now unused < /proc/uptime || return 1
 now=${now%%.*}
 case "$now" in ''|*[!0-9]*) return 1;; esac
}
# A pending wireless PAUSE is not implicitly cleared by an upload.
owner_active || exit 0
if [ -x "$D/prepare.sh" ]; then
 # Early boot can precede native UI readiness. Skip optional OSD this time;
 # the next actual upload retries binding, without idle polling/extra power.
 /bin/ash "$D/prepare.sh" > "$D/prepare.log" 2>&1 || { echo UPLOAD_DISPLAY_NOT_READY; exit 0; }
fi
display_mark native_binding_ready
# Do not reclaim or wait on another operation. Upload continues without OSD.
$B mkdir "$D/maintenance" || exit 92
claimed=0; running=0; cycles=0
finish() {
 result=$?
 if [ "$claimed" = 1 ]; then
  printf 'exit=%s\n' "$result" > "$D/done"
  if [ "$result" = 0 ]; then echo stage=restored > "$D/status";
  else printf 'stage=upload-display-failed rc=%s\n' "$result" > "$D/status"; fi
 fi
 [ "$running" != 1 ] || $B rmdir "$D/blink-worker.running"
 $B rmdir "$D/maintenance"
 display_mark consumer_end
 echo "UPLOAD_DISPLAY_DONE rc=$result cycles=$cycles"
}
trap finish EXIT
# Pause/request removal is observed by the renderer, which owns final cleanup.
stop=0
trap '' HUP
trap 'stop=1' TERM INT
# This checks boot/PID/timer, original font/coordinates and the previous
# successful timer-cancel proof before discarding old frame files.
display_mark rearm_begin
/bin/ash "$D/manage.sh" XREARM || exit 95
display_mark rearm_end
owner_active || exit 0
p=$($B cat "$D/native.pid"); a=$($B cat "$D/native.base")
timer=$($B cat "$D/native.timer"); boot=$($B cat "$D/boot-id")
mode=$($B cat "$D/native.mode")
case "$mode" in
 --once-shooting) mode=--upload-shooting;;
 --once-shooting-idle) mode=--upload-shooting-idle;;
 *) exit 95;;
esac
[ "$($B cat "$D/shooting-overlay")" = 1 ] || exit 95
now_seconds || exit 95
begin=$now
if [ "$stop" = 0 ] && owner_active; then
 now_seconds && [ "$now" -ge "$begin" ] || exit 95
 if [ "$((now-begin))" -ge "$limit" ]; then echo UPLOAD_DISPLAY_DEADLINE; exit 0; fi
 [ "$($B cat /proc/sys/kernel/random/boot_id)" = "$boot" ] &&
 [ "$($B pidof im.elf)" = "$p" ] || exit 95
 if [ "$claimed" = 0 ]; then
  $B mkdir "$D/claimed" || exit 92
  claimed=1
  $B mkdir "$D/blink-worker.running" || exit 92
  running=1
 fi
 # Four fixed-size snapshots plus bounded logs stay in the 4 MiB display RAM.
 $B rm -f "$D/dds-before.raw" "$D/dds-during.raw" "$D/dds-late.raw" "$D/dds-after.raw" || exit 98
 printf 'stage=uploading cycle=%s\n' "$((cycles+1))" > "$D/status"
 display_mark renderer_exec
 capture_rc=0
 "$D/capture" "$mode" "$p" "$a" > "$D/overlay.log" 2>&1 || capture_rc=$?
 display_mark renderer_exit
 if [ "$capture_rc" != 0 ]; then
  # A changed native OSD (e.g. histogram) is not failed font/timer cleanup.
  # Accept only the renderer's exact post-capture occupancy result; all other
  # failures remain blocked. The fresh inspection below is still mandatory.
  [ "$capture_rc" = 91 ] &&
  $B grep -qx 'DDS_DONE display=0 cleanup=0 guardian=0 captures=0,0,98' "$D/overlay.log" &&
  $B grep -qx 'DDS_LATE capture=0' "$D/overlay.log" &&
  $B grep -qx "DDS_CANCEL timer=$timer transport=0 response=0" "$D/overlay.log" || exit 97
  echo UPLOAD_DISPLAY_POST_FRAME_CHANGED
 fi
 $B grep -qx "DDS_CANCEL timer=$timer transport=0 response=0" "$D/overlay.log" &&
 $B grep -Eq '^DDS_DONE display=0 cleanup=0 guardian=0 captures=0,0,(0|98)$' "$D/overlay.log" || exit 98
 "$D/capture" --inspect "$p" "$a" > "$D/inspect-after.log" 2>&1 || exit 98
 $B grep -qx "DDS_STATE attached timer=$timer first=0 override=0 visible=0 others_idle=1" "$D/inspect-after.log" &&
 $B grep -qx 'DDS_FONT original_matches=1 bytes=128' "$D/inspect-after.log" &&
 $B grep -qx 'DDS_POSITION original_matches=1 x=30 y=250' "$D/inspect-after.log" || exit 98
 cycles=$((cycles+1))
 printf 'cycle=%s restored=1\n' "$cycles" > "$D/blink-history"
fi
# No timer, socket polling or power lease remains owned by this consumer.
exit 0
