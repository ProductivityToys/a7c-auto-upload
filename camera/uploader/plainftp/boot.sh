#!/bin/ash
# Installed as /setting/a7c-uploader/worker.sh, under the existing supervisor.
# Read persistent configuration once; runtime, logs and retries stay in tmpfs.
B=/bin/busybox
P=/setting/a7c-uploader
D=/setting/a7c-uploader/ram
C=/setting/a7c-uploader/plainftp
umask 077
fail() { echo "PLAIN_BOOT_REJECTED $1"; exit 90; }
private() {
 [ ! -L "$1" ] || return 1
 details=$($B ls -ldn "$1") || return 1
 read mode links uid gid rest <<META
$details
META
 [ "$mode" = "$2" ] && [ "$uid" = 0 ] && [ "$gid" = 0 ]
}
$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs ' /proc/mounts || fail runtime
[ ! -e "$D/lock" ] && [ ! -e "$D/source.fifo" ] && [ ! -e "$D/network.fifo" ] &&
[ ! -e "$D/display-bootstrap.lock" ] || fail busy
boot_mark() {
 IFS=' ' read -r boot_time boot_unused < /proc/uptime || boot_time=unknown
 printf 'op=%s uptime=%s\n' "$1" "$boot_time" >> "$D/plain-boot-timings.log"
}
private "$C" drwx------ && private "$C/config" -rw------- && private "$C/password" -rw------- && private "$C/manifest" -rw------- || fail permissions
[ "$($B wc -c < "$C/config")" -le 1024 ] && [ "$($B wc -c < "$C/password")" -le 257 ] || fail length
photos=0; pause_native_ftp=0
{
 IFS= read -r version && IFS= read -r host && IFS= read -r port && IFS= read -r user && IFS= read -r root || fail config
 case "$version" in
  a7c-plainftp-v1) ;;
  a7c-plainftp-v2|a7c-plainftp-v3)
   IFS= read -r photos || fail config
   case "$photos" in 0|1) ;; *) fail photos;; esac
   if [ "$version" = a7c-plainftp-v3 ]; then
    IFS= read -r pause_native_ftp || fail config
    case "$pause_native_ftp" in 0|1) ;; *) fail photos;; esac
   fi;;
  *) fail version;;
 esac
 ! IFS= read -r extra
} < "$C/config" || fail config
[ -z "$extra" ] || fail config
$B mkdir "$D/plain.bootstrap.lock" || fail claimed
trap '$B rmdir "$D/plain.bootstrap.lock"' EXIT
: > "$D/plain-boot-timings.log"
boot_mark begin
count=0; seen=' '
while read -r hash name extra; do
 [ -z "$extra" ] && [ "${#hash}" = 64 ] || fail manifest
 case "$hash" in *[!a-f0-9]*) fail digest;; esac
 case "$name" in monitor|relay|lease|plainftp|local-media|sd-monitor|discovery|plain-runtime.sh|plain-worker.sh) ;; *) fail payload;; esac
 case "$seen" in *" $name "*) fail duplicate;; esac
 seen="$seen$name "; count=$((count+1))
 private "$C/$name" -rw------- || fail payload_permissions
 actual=$($B sha256sum "$C/$name"); actual=${actual%% *}
 [ "$actual" = "$hash" ] || fail source_hash
 $B cp "$C/$name" "$D/$name.next" || fail copy
 actual=$($B sha256sum "$D/$name.next"); actual=${actual%% *}
 [ "$actual" = "$hash" ] || fail ram_hash
 $B chmod 700 "$D/$name.next" && $B mv "$D/$name.next" "$D/$name" || fail publish
done < "$C/manifest"
[ "$count" = 9 ] || fail payload_count
boot_mark payloads_ready
"$D/plainftp" namespace "$host" "$port" "$user" "$root" > "$D/plain.namespace" || fail target
# Display is an independently versioned optional package. Its failure cannot
# prevent ordinary FTP. Verify its entry before executing; never read secrets.
S=/setting/a7c-display
if [ -d "$S" ]; then
 $B rm -f "$D/upload-display.sh"
 if private "$S" drwx------ && private "$S/enabled" -rw------- &&
    private "$S/stage.sh" -rw------- && private "$S/stage.sha256" -rw-------; then
  display_hash=$($B cat "$S/stage.sha256")
  display_actual=$($B sha256sum "$S/stage.sh")
  if [ "${#display_hash}" = 64 ] && [ "$display_hash" = "${display_actual%% *}" ]; then
   # Stage the optional display while read-only media discovery/stability runs.
   # This lock also guards upgrades/restarts until its independent child exits.
   $B mkdir "$D/display-bootstrap.lock" || fail display_busy
   (
    exec 0</dev/null
    trap '$B rmdir "$D/display-bootstrap.lock"' EXIT
    boot_mark display_begin
    /bin/ash "$S/stage.sh" > "$D/display-bootstrap.log" 2>&1
    display_rc=$?
    boot_mark display_end
    [ "$display_rc" = 0 ] || echo DISPLAY_OPTIONAL_STAGE_FAILED
   ) &
  fi
 fi
fi
# Credentials are never arguments, environment, or diagnostic output.
$B rmdir "$D/plain.bootstrap.lock" || fail release
trap - EXIT
boot_mark worker_exec
exec /bin/ash "$D/plain-worker.sh" "$host" "$port" "$user" "$root" "$photos" "$pause_native_ftp" < "$C/password"
