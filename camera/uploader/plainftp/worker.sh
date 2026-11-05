#!/bin/ash
# Experimental standard-FTP worker; only password input is stdin (RAM).
# Runtime library contains the exact validated native/power functions extracted
# at build time from the baseline worker. No NAS planner calls are used.
B=/bin/busybox
P=/setting/a7c-uploader
D=/setting/a7c-uploader/ram
umask 077
. "$D/plain-runtime.sh" || exit 90
HOST=$1; PORT=$2; USER=$3; ROOT=$4
PHOTOS=${5:-0}
[ "$#" = 4 ] || [ "$#" = 5 ] || exit 64
case "$PHOTOS" in 0|1) ;; *) exit 64;; esac
$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs ' /proc/mounts || exit 90
$B mkdir "$D/lock" || exit 90
echo "$$" > "$D/plain.worker.pid"
IFS= read -r FTP_PASSWORD || { $B rmdir "$D/lock"; exit 64; }
[ -n "$FTP_PASSWORD" ] || { $B rmdir "$D/lock"; exit 64; }
exec 0</dev/null
ftp() { printf '%s\n' "$FTP_PASSWORD" | "$D/plainftp" "$1" "$HOST" "$PORT" "$USER" "$ROOT" "$IDENTITY" "$SIZE" "$2" "$LIMIT" ${MEDIA_EXT:+$MEDIA_EXT}; }
plain_display_begin() {
 # Optional consumer, installed separately in RAM. No helper means no display
 # process, marker, or extra polling. No media identity or credentials exposed.
 DISPLAY_PID=; DISPLAY_TOKEN=
 [ ! -d "$D/display-bootstrap.lock" ] || { log 'DISPLAY_SKIPPED stage_pending'; return 0; }
 [ -x "$D/upload-display.sh" ] && [ ! -e "$D/display.disabled" ] || return 0
 [ ! -e "$D/display.active" ] || { log 'DISPLAY_SKIPPED stale_active'; return 0; }
 IFS= read -r display_stat < "/proc/$$/stat" || return 0
 display_stat=${display_stat##*) }
 set -- $display_stat
 [ "$#" -ge 20 ] || return 0
 shift 19
 case "$1" in ''|*[!0-9]*) return 0;; esac
 DISPLAY_SERIAL=$((${DISPLAY_SERIAL:-0}+1))
 DISPLAY_TOKEN="$$ $1 $DISPLAY_SERIAL $LIMIT"
 $B rm -f "$D/display.progress" "$D/display.progress.next"
 printf '%s\n' "$DISPLAY_TOKEN" > "$D/display.active.next" &&
 $B mv "$D/display.active.next" "$D/display.active" || { DISPLAY_TOKEN=; return 0; }
 /bin/ash "$D/upload-display.sh" "$DISPLAY_TOKEN" > "$D/display.log" 2>&1 & DISPLAY_PID=$!
}
plain_display_end() {
 [ -n "$DISPLAY_TOKEN" ] || return 0
 if [ "$($B cat "$D/display.active" 2>/dev/null)" = "$DISPLAY_TOKEN" ]; then
  $B rm -f "$D/display.active" "$D/display.progress" "$D/display.progress.next"
 fi
 # Cooperate with the native transaction's independent 15-second guardian.
 # Never signal/kill its setter. Retain the upload lease until this bounded
 # cleanup wait ends; display failure never changes FTP or receipt results.
 display_wait=0
 while [ -n "$DISPLAY_PID" ] && kill -0 "$DISPLAY_PID" 2>/dev/null && [ "$display_wait" -lt 22 ]; do
  $B sleep 1; display_wait=$((display_wait+1))
 done
 if [ -n "$DISPLAY_PID" ]; then
  if kill -0 "$DISPLAY_PID" 2>/dev/null; then
   : > "$D/display.disabled"; log 'DISPLAY_CLEANUP_TIMEOUT disabled=1'
  else
   wait "$DISPLAY_PID"; display_rc=$?
   log "DISPLAY_EXIT rc=$display_rc"
   [ "$display_rc" = 0 ] || : > "$D/display.disabled"
  fi
 fi
 DISPLAY_PID=; DISPLAY_TOKEN=
 return 0
}
# Detailed per-query timings are an explicit RAM-only maintenance option.
TIMING_ENABLED=0
[ ! -f "$D/trace-timing" ] || TIMING_ENABLED=1
timed() {
 # Bounded RAM-only timings. Arguments/output (including credentials) are never logged.
 local timing_op=$1 timing_before timing_after timing_rest timing_rc
 shift
 if [ "$TIMING_ENABLED" != 1 ]; then "$@"; return $?; fi
 IFS=' ' read -r timing_before timing_rest < /proc/uptime || timing_before=unknown
 "$@"; timing_rc=$?
 IFS=' ' read -r timing_after timing_rest < /proc/uptime || timing_after=unknown
 printf 'op=%s start=%s end=%s rc=%s\n' "$timing_op" "$timing_before" "$timing_after" "$timing_rc" >> "$D/plain-timings.log"
 if [ "$($B wc -c < "$D/plain-timings.log")" -gt 16384 ]; then
  $B tail -c 8192 "$D/plain-timings.log" > "$D/plain-timings.next" && $B mv "$D/plain-timings.next" "$D/plain-timings.log"
 fi
 return "$timing_rc"
}
cache_invalidate() {
 SNAPSHOT_AT=; GATE_AT=; ROOT_AT=; ROOT_CARD=
}
usb_media_ready() {
 # The driver leaves state="configured" after physical unplug. Negotiated
 # speed resets to UNKNOWN and reflects the actual absence of a data link.
 local usb_speed
 IFS= read -r usb_speed < /sys/class/udc/dwc3.0/current_speed || { cache_invalidate; return 1; }
 [ "$usb_speed" = UNKNOWN ] || { cache_invalidate; return 1; }
}
snapshot_fresh() {
 [ -n "$SNAPSHOT_AT" ] && uptime_seconds &&
 [ "$NOW" -ge "$SNAPSHOT_AT" ] && [ "$((NOW-SNAPSHOT_AT))" -le 30 ]
}
directory_publish() {
 $D/local-media newest "$LETTER" "$D/dir" > "$D/plain.entries.next" || { cache_invalidate; return 1; }
 if [ "${PHOTOS:-0}" = 1 ]; then
  $D/local-media photos "$LETTER" "$D/dir" >> "$D/plain.entries.next" || { cache_invalidate; return 1; }
  $D/local-media order "$D/plain.entries.next" > "$D/plain.entries.sorted" &&
  $B mv "$D/plain.entries.sorted" "$D/plain.entries.next" || { cache_invalidate; return 1; }
 fi
 if [ "$CARD" != "$SNAPSHOT_CARD" ] || ! $B cmp "$D/plain.entries.next" "$D/plain.entries" > /dev/null 2>&1; then ROOT_AT=; fi
 $B mv "$D/plain.entries.next" "$D/plain.entries" || { cache_invalidate; return 1; }
 uptime_seconds || { cache_invalidate; return 1; }
 SNAPSHOT_AT=$NOW; SNAPSHOT_CARD=$CARD; SNAPSHOT_LETTER=$LETTER
}
still_rec_standby() {
 local still_rec
 still_rec=$($B sed 's/\r//g; /^$/d; /^MPR Debug RecInfo$/d' "$1") || return 1
 [ "$still_rec" = '[MprMcmd][RecInfo] =====
 + line[0], contentType:Still(JPG), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY
MON>' ]
}
recording_idle() {
 FULL_STATE_USED=0
 # Unlink before a new redirect: a leftover native process cannot append to
 # the next transaction's inode. Only a fully completed bundle is published.
 $B rm -f "$D/recording.bundle"
 "$D/monitor" recording-bundle > "$D/recording.bundle" 2> "$D/query.err" || return 1
 $B sed -n '/^A7C_REC_PART_0_BEGIN$/,/^A7C_REC_PART_0_END$/p' "$D/recording.bundle" | $B sed '1d; $d' > "$D/rec" || return 1
 if [ "$($B grep -c 'contentType:Movie(XAVC), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY' "$D/rec")" = 2 ]; then return 0; fi
 local still_idle=0
 if still_rec_standby "$D/rec"; then still_idle=1; else empty_rec "$D/rec" || return 2; fi
 $B sed -n '/^A7C_REC_PART_1_BEGIN$/,/^A7C_REC_PART_1_END$/p' "$D/recording.bundle" | $B sed '1d; $d' > "$D/full-state.txt" || return 1
 if [ "$still_idle" = 1 ]; then full_state_idle "$D/full-state.txt" still || return 2
 else full_state_idle "$D/full-state.txt" || return 2; fi
 $B sed -n '/^A7C_REC_PART_2_BEGIN$/,/^A7C_REC_PART_2_END$/p' "$D/recording.bundle" | $B sed '1d; $d' > "$D/rec-recheck" || return 1
 if [ "$still_idle" = 1 ]; then still_rec_standby "$D/rec-recheck" || return 2
 else empty_rec "$D/rec-recheck" || return 2; fi
 FULL_STATE_USED=1
}
media_gate() {
 # Video transfer needs a full recorder/source snapshot. SD receipt writes
 # use their separate current recorder/card/open-handle gate below.
 timed recording recording_idle || { cache_invalidate; return 1; }
 filesystem_bind
}
filesystem_idle() {
 local info_mode=info
 [ "${PHOTOS:-0}" != 1 ] || info_mode=info-photos
 CARD=$(timed fs_idle "$D/local-media" "$info_mode" "$LETTER" "$D/info") || { cache_invalidate; return 1; }
 # This is a read-only gate. Actual transfer and SD writes use media_gate.
 if $B grep -Fq ':\PRIVATE\M4ROOT\CLIP\' "$D/info"; then cache_invalidate; return 1; fi
}
filesystem_bind() {
 # One native frontend, three sequential replies: drive -> directory -> info.
 # Both parsers select their own completed reply from the bounded transcript.
 local filesystem_mode=filesystem
 [ "${PHOTOS:-0}" != 1 ] || filesystem_mode=filesystem-photos
 timed filesystem "$D/monitor" "$filesystem_mode" > "$D/filesystem.snapshot" 2> "$D/query.err" || { cache_invalidate; return 1; }
 LETTER=$($B sed -n "s/\r//g; s/^driveLetter = '\([A-Z]\)'$/\1/p" "$D/filesystem.snapshot" | $B tail -1)
 case "$LETTER" in [A-Z]) ;; *) cache_invalidate; return 1;; esac
 $B cp "$D/filesystem.snapshot" "$D/info" && $B cp "$D/filesystem.snapshot" "$D/dir" || { cache_invalidate; return 1; }
 filesystem_idle || return 1
 directory_publish || return 1
 GATE_AT=$NOW
}
media_poll() {
 usb_media_ready || return 1
 # A short read-only backlog window reuses the whole card/directory snapshot,
 # not one new IFSYS info per old clip. Refresh after 8s or on idle.
 # Actual video reads and SD writes keep current gates.
 if snapshot_fresh && [ "${QUEUE_PENDING:-1}" = 1 ] &&
    [ "$((NOW-SNAPSHOT_AT))" -le 8 ]; then
  LETTER=$SNAPSHOT_LETTER; CARD=$SNAPSHOT_CARD
  return 0
 fi
 filesystem_bind
}

source_same() {
 usb_media_ready || return 1
 # Keep the complete recorder check immediately before copying. Reuse only
 # the <=8s drive/directory listing, then refresh card/open handles in place.
 timed recording recording_idle || { cache_invalidate; return 1; }
 if snapshot_fresh && [ "$((NOW-SNAPSHOT_AT))" -le 8 ] &&
    [ "$SNAPSHOT_LETTER" = "$DRIVE" ] && [ "$SNAPSHOT_CARD" = "$SOURCE_CARD" ]; then
  LETTER=$DRIVE
  timed transfer_info "$D/monitor" info > "$D/transfer.info" 2> "$D/query.err" || { cache_invalidate; return 1; }
  $B cp "$D/transfer.info" "$D/info" || { cache_invalidate; return 1; }
  filesystem_idle || return 1
 else
  filesystem_bind || return 1
 fi
 if [ "$LETTER" != "$DRIVE" ] || [ "$CARD" != "$SOURCE_CARD" ]; then
  cache_invalidate; return 1
 fi
 $B grep -Fqx "$SOURCE_ROW" "$D/plain.entries"
}
receipt_sample_idle() {
 # The existing read-only probe binds the current im.elf mapping/code/pointer.
 # Accept only the exact two XAVC standby rows used by the native fast path.
 local sample_header sample_ms sample_row sample_index sample_expected sample_extra
 {
  IFS= read -r sample_header || return 1
  case "$sample_header" in
   "A7C_RECORDER_SAMPLE_V1 pid=$1 ms="*) sample_ms=${sample_header#* ms=};;
   *) return 1;;
  esac
  case "$sample_ms" in ''|*[!0-9]*) return 1;; esac
  for sample_index in 0 1 2 3; do
   IFS= read -r sample_row || return 1
   case "$sample_index" in
    0|1) sample_expected="line=$sample_index active=1 index=$sample_index type=256 state=1 count1=0 count2=0";;
    *) sample_expected="line=$sample_index active=0 index=0 type=0 state=0 count1=0 count2=0";;
   esac
   [ "$sample_row" = "$sample_expected" ] || return 1
  done
  ! IFS= read -r sample_extra && [ -z "$sample_extra" ]
 } < "$D/receipt-recorder.sample"
}
receipt_recording_idle() {
 local receipt_pid=${discovery_pid:-}
 if [ "${DISCOVERY_OFF:-0}" = 0 ] && [ -x "$D/discovery" ]; then
  [ -n "$receipt_pid" ] || receipt_pid=$($B pidof im.elf)
  if "$D/discovery" "$receipt_pid" > "$D/receipt-recorder.sample" 2> "$D/query.err" &&
     receipt_sample_idle "$receipt_pid"; then return 0; fi
 fi
 # Unknown/other modes retain the original complete recorder query. Video
 # transfer always uses that query; this fast path only precedes a receipt.
 recording_idle
}
receipt_card_ready() {
 usb_media_ready || return 1
 # The video is already published. A receipt describes that completed upload,
 # even if the user removed the source afterwards. Before this small SD write
 # check current recording/card/open handles, without re-listing all videos.
 timed receipt_recording receipt_recording_idle || { cache_invalidate; return 1; }
 local receipt_root_reused=0
 # This sole worker owns the receipt namespace. Reuse its existing <=30s root
 # snapshot, never its old card/open-handle state. Every write invalidates it.
 if receipt_root_fresh; then
  timed receipt_info "$D/monitor" info > "$D/info" 2> "$D/query.err" || { cache_invalidate; return 1; }
  receipt_root_reused=1
 else
  # Long transfers need a new root; obtain it with current card info in one
  # sequential frontend session. Publish neither cache on failure.
  ROOT_AT=
  timed receipt_context "$D/sd-monitor" context "$DRIVE" > "$D/receipt.context" 2> "$D/query.err" || { cache_invalidate; return 1; }
  $B cp "$D/receipt.context" "$D/info" && $B cp "$D/receipt.context" "$D/receipt.root" || { cache_invalidate; return 1; }
 fi
 LETTER=$DRIVE
 filesystem_idle && [ "$CARD" = "$SOURCE_CARD" ] || { cache_invalidate; return 1; }
 if [ "$receipt_root_reused" != 1 ]; then
  uptime_seconds || { cache_invalidate; return 1; }
  ROOT_AT=$NOW; ROOT_CARD=$CARD
 fi
}
source_checked() {
 # The scheduler just checked the filesystem card/open-writer state. Reuse it
 # only for read-only receipt lookup in this bounded directory generation;
 # video transfer uses source_same; receipt writes recheck recorder/card/handles.
 if snapshot_fresh && [ -n "$GATE_AT" ] && [ "$NOW" -ge "$GATE_AT" ] &&
    [ "$((NOW-GATE_AT))" -le 8 ] && [ "$LETTER" = "$DRIVE" ] && [ "$CARD" = "$SOURCE_CARD" ]; then
  $B grep -Fqx "$SOURCE_ROW" "$D/plain.entries"
 else
  media_poll && [ "$LETTER" = "$DRIVE" ] && [ "$CARD" = "$SOURCE_CARD" ] &&
  $B grep -Fqx "$SOURCE_ROW" "$D/plain.entries"
 fi
}
receipt_root_fresh() {
 uptime_seconds && [ -n "$ROOT_AT" ] && [ "$ROOT_CARD" = "$CARD" ] &&
    [ "$NOW" -ge "$ROOT_AT" ] && [ "$((NOW-ROOT_AT))" -le 30 ] && [ -f "$D/receipt.root" ]
}
receipt_root() {
 if [ "$1" != fresh ] && receipt_root_fresh; then return 0; fi
 ROOT_AT=
 timed receipt_root "$D/sd-monitor" root "$DRIVE" > "$D/receipt.root" 2> "$D/receipt.err" || return 90
 uptime_seconds || return 90
 ROOT_AT=$NOW; ROOT_CARD=$CARD
}
receipt_load() {
 SLOT_A=-; SLOT_B=-; EMPTY_SLOT=
 receipt_root "${1:-cached}" || return 90
 PREFIX=$($D/plainftp slot "$HOST" "$PORT" "$USER" "$ROOT" "$IDENTITY") || return 90
 [ "${#PREFIX}" = 6 ] || return 90
 case "$PREFIX" in *[!0-9A-F]*) return 90;; esac
 for slot in A B; do
  filename="U${PREFIX}${slot}.RCP"
  $D/local-media exists "$DRIVE" "$filename" "$D/receipt.root"; present=$?
  case "$present" in
   0) $B rm -f "$D/receipt.read"
      timed receipt_read "$D/sd-monitor" read "$DRIVE" "$filename" > "$D/receipt-copy.log" 2>&1 || return 90
      [ -f "$D/receipt.read" ] || return 90
      $B mv "$D/receipt.read" "$D/receipt.$slot" || return 90
      if [ "$slot" = A ]; then SLOT_A="$D/receipt.A"; else SLOT_B="$D/receipt.B"; fi;;
   10) [ -n "$EMPTY_SLOT" ] || EMPTY_SLOT=$filename;;
   *) return 90;;
  esac
 done
 $D/plainftp match-row "$HOST" "$PORT" "$USER" "$ROOT" "$IDENTITY" "$SIZE" "$SLOT_A" "$SLOT_B" ${MEDIA_EXT:+$MEDIA_EXT}
}
receipt_store() {
 # Never overwrite an occupied/colliding slot, including a damaged one.
 receipt_card_ready || return 1
 # Card/handles were just rechecked; root is refreshed or within its old TTL.
 receipt_load cached; receipt_rc=$?
 [ "$receipt_rc" != 0 ] || return 0
 [ "$receipt_rc" = 10 ] && [ -n "$EMPTY_SLOT" ] || return 90
 [ "$($B wc -c < "$D/receipt.write")" = 512 ] || return 90
 ROOT_AT=
 $B rm -f "$D/receipt.read"
 timed receipt_write_verify "$D/sd-monitor" write-verify "$DRIVE" "$EMPTY_SLOT" > "$D/receipt-copy.log" 2>&1 || { log "SD_WRITE_VERIFY_FAILED rc=$?"; return 90; }
 $B cmp "$D/receipt.write" "$D/receipt.read" > /dev/null 2>&1 || { log 'SD_READBACK_MISMATCH'; return 90; }
 # commit emitted this encoded 512-byte receipt after FTP length confirmation;
 # exact readback equality already proves it is the same record, no re-decode.
 log "SD_RECEIPT $VIDEO $EMPTY_SLOT"
}
plain_transfer() {
 plain_transfer_body; transfer_result=$?
 plain_display_end
 return "$transfer_result"
}
plain_transfer_body() {
 source_same || return 75
 copy_rc=not_started; relay_rc=not_started; ftp_rc=not_started
 $B rm -f "$D/relay.ready" "$D/relay.result" "$D/guard.done" "$D/copy.done" "$D/receipt.write"
 $B mkfifo "$D/source.fifo" "$D/network.fifo" || return 90
 plain_display_begin
 ftp put "$D/network.fifo" > "$D/plain-ftp.log" 2>&1 & ftp_pid=$!
 $D/relay "$D" "$SIZE" > "$D/relay.log" 2>&1 & relay_pid=$!
 # Native bounded readiness wait avoids a full-second shell polling penalty.
 "$D/monitor" wait-ready relay "$relay_pid" || :
 copy_rc=76
 if [ -f "$D/relay.ready" ] && kill -0 "$relay_pid" 2>/dev/null; then
  log "FTP_COPY_BEGIN $VIDEO"
  $D/monitor copy "$DRIVE" "$VIDEO" "$LIMIT" > "$D/copy.log" 2>&1; copy_rc=$?
 fi
 case "$copy_rc" in
  0|73|76) : > "$D/copy.done";;
  *) log 'NATIVE_COMPLETION_UNKNOWN'; return 90;;
 esac
 wait_child "$relay_pid"; relay_rc=$CHILD_RC
 if [ "$relay_rc" != 0 ]; then kill -TERM "$ftp_pid" 2>/dev/null; fi
 wait_child "$ftp_pid"; ftp_rc=$CHILD_RC
 [ "$ftp_rc" = 0 ] || FTP_TRANSPORT_FAILED=1
 cleanup_completed_fifos || return 90
 [ "$copy_rc" = 0 ] && [ "$relay_rc" = 0 ] && [ "$ftp_rc" = 0 ] || { [ "$ftp_rc" != 90 ] || return 90; return 1; }
 read BAD COUNT EXTRA < "$D/relay.result"
 [ "$BAD" = 0 ] && [ "$COUNT" = "$SIZE" ] && [ -z "$EXTRA" ] || return 90
 # Commit only after native copy, relay drain, byte count and FTP child succeed.
 ftp commit - > "$D/receipt.write" 2> "$D/plain-ftp.log"; committed=$?
 [ "$committed" = 0 ] || FTP_TRANSPORT_FAILED=1
 [ "$committed" != 90 ] || return 90
 [ "$committed" = 0 ] || return 1
 receipt_store || return $?
 log "FTP_DONE $VIDEO $SIZE proof=ftp_size"
}
plain_attempt() {
 # Directory-key/receipt checks need no per-file upload power lease.
 # The full source gate still runs after acquiring the actual upload lease.
 ATTEMPT_SKIPPED=0; lease_pid=; FTP_TRANSPORT_FAILED=0; MEDIA_EXT=
 case "$VIDEO" in DCIM/*.JPG) MEDIA_EXT=JPG;; DCIM/*.ARW) MEDIA_EXT=ARW;; esac
 # 75 is pre-transfer source unavailability, not a failed FTP connection.
 result=75
 if source_checked; then
  IDENTITY=$($D/local-media row-identity "$SOURCE_ROW"); identity_rc=$?
  if [ "$identity_rc" = 0 ]; then
   receipt_load; found=$?
   case "$found" in
    0) result=0; ATTEMPT_SKIPPED=1;;
    10) if [ -n "$EMPTY_SLOT" ]; then
         LIMIT=$((240 + SIZE / 32768)); [ "$LIMIT" -le 86000 ] || LIMIT=86000
         $B rm -f "$D/lease.ready" "$D/lease.done"
         $D/lease --upload-lease "$LIMIT" > "$D/lease.log" 2>&1 & lease_pid=$!
         "$D/monitor" wait-ready lease "$lease_pid" || :
         if [ -f "$D/lease.ready" ]; then plain_transfer; result=$?; fi
        else result=90; fi;;
    *) result=90;;
   esac
  else result=90; fi
 fi
 if [ -n "$lease_pid" ]; then
  : > "$D/lease.done"; wait_child "$lease_pid"
  [ "$CHILD_RC" = 0 ] && $B grep -qx 'PROBE_DONE set=0 clear=0 guardian_status=0' "$D/lease.log" || result=90
 fi
 [ "$ATTEMPT_SKIPPED" = 1 ] || log "FTP_ATTEMPT $VIDEO result=$result"
 return "$result"
}
prune_rows() {
 # Keep only exact current rows (both sizes and timestamps), never names alone.
 # One fixed-string intersection avoids a new process for every card entry.
 # This camera's BusyBox treats an empty pattern file as match-all. Handle
 # empty sets ourselves; a nonempty grep returning 1 is an empty intersection.
 if [ ! -s "$D/plain.entries" ] || [ ! -s "$1" ]; then
  : > "$1" || return 90
  return 0
 fi
 $B grep -Fxf "$D/plain.entries" "$1" > "$1.next"; prune_rc=$?
 case "$prune_rc" in 0|1) ;; *) $B rm -f "$1.next"; return 90;; esac
 $B mv "$1.next" "$1"
}
scan_update() {
 # "known" orders work; "checked" records prior successful facts for this
 # worker/target/card. Revalidate the card and exact rows in a fresh snapshot
 # after activity/unknown time, rather than forgetting every old success.
 if [ "$CARD" != "$known_card" ]; then
  # Baseline the first directory only for ordering. Old files still have no
  # checked receipt: they take the fallback path and are all verified/uploaded.
  # A newly recorded row must not wait behind this entire initial backlog.
  $B cp "$D/plain.entries" "$D/plain.known" || return 90
  : > "$D/plain.checked" || return 90
  known_card=$CARD
 fi
 discontinuity=0; changed=0
 if [ "$CARD" != "$previous_card" ] || [ "$NOW" -lt "$last_scan" ] || [ "$((NOW-last_scan))" -gt 45 ]; then
  discontinuity=1
 fi
 if [ ! -f "$D/plain.previous" ] || ! $B cmp "$D/plain.entries" "$D/plain.previous" > /dev/null 2>&1; then changed=1; fi
 if [ "$discontinuity" = 1 ] || [ "$changed" = 1 ]; then
  log "SCAN_REFRESH discontinuity=$discontinuity directory_changed=$changed"
  QUEUE_PENDING=1
  prune_rows "$D/plain.checked" && prune_rows "$D/plain.known" || return 90
  $B cp "$D/plain.entries" "$D/plain.previous" || return 90
 fi
 previous_card=$CARD; last_scan=$NOW
}
rows_missing_from() {
 # Exact line difference, with an explicit empty-pattern branch for this
 # camera's BusyBox. Errors must stop selection, never authorize a transfer.
 if [ ! -s "$1" ]; then : > "$3"; return $?; fi
 if [ ! -s "$2" ]; then $B cp "$1" "$3"; return $?; fi
 $B grep -Fvxf "$2" "$1" > "$3"; difference_rc=$?
 case "$difference_rc" in 0|1) return 0;; *) $B rm -f "$3"; return 90;; esac
}
choose_row() {
 chosen=; fallback=; priority=recheck
 rows_missing_from "$D/plain.entries" "$D/plain.checked" "$D/plain.pending" &&
 rows_missing_from "$D/plain.pending" "$D/plain.known" "$D/plain.new" || return 90
 if [ -s "$D/plain.new" ]; then
  IFS= read -r chosen < "$D/plain.new" || return 90
  priority=new_or_changed
 elif [ -s "$D/plain.pending" ]; then
  IFS= read -r chosen < "$D/plain.pending" || return 90
 fi
 return 0
}
ftp_health_mark() {
 if [ "${FTP_HEALTH:-unknown}" != "$1" ]; then
  FTP_HEALTH=$1
  printf '%s\n' "$1" > "$D/ftp-health.next" && $B mv "$D/ftp-health.next" "$D/ftp-health" || :
  log "FTP_HEALTH $1"
 fi
 [ "${FTP_HEALTH_SHOWN:-unknown}" != "$1" ] || return 0
 # One aligned status word in the existing renderer, only on state changes.
 # No display daemon, timer, power lease or NAND writes.
 local health_native=/setting/a7c-debug/ram/dds-once/native-service health_pid
 if [ -x "$health_native/probe" ] && [ "$($B cat "$health_native/owner" 2>/dev/null)" = "$$" ]; then
  health_pid=$($B pidof im.elf)
  if [ "$health_pid" = "$($B cat "$health_native/im.pid" 2>/dev/null)" ]; then
   if [ "$1" = error ]; then
    "$health_native/probe" --service-error "$health_pid" > "$D/ftp-health-display.log" 2>&1 && FTP_HEALTH_SHOWN=$1
   else
    "$health_native/probe" --service-healthy "$health_pid" > "$D/ftp-health-display.log" 2>&1 && FTP_HEALTH_SHOWN=$1
   fi
  fi
 fi
 return 0
}
ftp_health_ready() {
 local link_generation=0 health_now health_rest health_begin health_end health_rc health_action
 IFS= read -r link_generation < /sys/class/net/wlan0/ifindex 2>/dev/null || link_generation=0
 case "$link_generation" in ''|*[!0-9]*) link_generation=0;; esac
 if [ "${FTP_LINK:-unset}" != "$link_generation" ]; then
  [ -z "${FTP_LINK:-}" ] || log "FTP_LINK_CHANGED $FTP_LINK->$link_generation"
  FTP_LINK=$link_generation; FTP_CHECK_DUE=1; FTP_CHECK_BACKOFF=10
  FTP_LINK_FAST_UNTIL=0
  if [ "$link_generation" != 0 ] && IFS=' ' read -r health_now health_rest < /proc/uptime; then
   FTP_LINK_FAST_UNTIL=$((${health_now%%.*}+10))
  fi
 fi
 if [ "${FTP_CHECK_DUE:-1}" != 1 ] && [ "${FTP_HEALTH:-unknown}" = healthy ]; then
  ftp_health_mark healthy; return 0
 fi
 FTP_CHECK_DUE=0
 IFS=' ' read -r health_begin health_rest < /proc/uptime || health_begin=unknown
 health_action=check
 if [ "$health_begin" != unknown ] && [ "${health_begin%%.*}" -lt "${FTP_LINK_FAST_UNTIL:-0}" ]; then
  health_action=check-fast
 fi
 health_rc=0
 printf '%s\n' "$FTP_PASSWORD" | "$D/plainftp" "$health_action" "$HOST" "$PORT" "$USER" "$ROOT" > "$D/ftp-health-check.log" 2>&1 || health_rc=$?
 IFS=' ' read -r health_end health_rest < /proc/uptime || health_end=unknown
 log "FTP_CHECK rc=$health_rc start=$health_begin end=$health_end mode=$health_action"
 if [ "$health_rc" = 0 ]; then
  FTP_CHECK_BACKOFF=10; FTP_LINK_FAST_UNTIL=0; ftp_health_mark healthy; return 0
 fi
 ftp_health_mark error
 # Wi-Fi creation precedes DHCP/association by more than two cheap failures.
 # Use an elapsed-time window, including failed connection time, not a count.
 if IFS=' ' read -r health_now health_rest < /proc/uptime &&
    [ "${health_now%%.*}" -lt "${FTP_LINK_FAST_UNTIL:-0}" ]; then
  FTP_HEALTH_DELAY=1; return 1
 fi
 FTP_LINK_FAST_UNTIL=0
 FTP_CHECK_BACKOFF=$((${FTP_CHECK_BACKOFF:-10}*2))
 [ "$FTP_CHECK_BACKOFF" -le 600 ] || FTP_CHECK_BACKOFF=600
 FTP_HEALTH_DELAY=$FTP_CHECK_BACKOFF
 return 1
}
discovery_wait() {
 [ "$delay" != 0 ] || return 0
 # Only replaces the ordinary 2s idle/busy delay.
 # Backlog draining and exponential network backoff keep their own timings.
 # A 30s timeout plus normal query overhead fits the existing 45s continuity
 # bound; slow/unknown periods still invalidate the receipt-check cache.
 if [ "$delay" = 1 ] || [ "${DISCOVERY_OFF:-0}" = 1 ] || [ ! -x "$D/discovery" ]; then
  $B sleep "$delay"; return 0
 fi
 discovery_pid=$($B pidof im.elf)
 local wait_left=$delay wait_slice wait_before wait_after wait_rest wait_elapsed
 [ "$delay" != 2 ] || wait_left=30
 while [ "$wait_left" -gt 0 ]; do
 wait_slice=$wait_left; [ "$wait_slice" -le 30 ] || wait_slice=30
 IFS=' ' read -r wait_before wait_rest < /proc/uptime || wait_before=0
 "$D/discovery" "$discovery_pid" wait "$wait_slice" "${FTP_LINK:-0}" > "$D/discovery.log" 2>&1; discovery_rc=$?
 case "$discovery_rc" in
  0) [ "$delay" != 2 ] || log 'DISCOVERY_WAKE quiet_timeout';;
  10|11) log "DISCOVERY_WAKE activity=$discovery_rc"
     cache_invalidate; previous_card=none; QUEUE_PENDING=1;;
  12) log 'DISCOVERY_WAKE network'
      FTP_CHECK_DUE=1; FTP_CHECK_BACKOFF=10
      cache_invalidate; previous_card=none; QUEUE_PENDING=1; return 0;;
  20) return 0;;
  *) # Still capture can temporarily change the recorder layout. Retry this
     # read-only hint next cycle so idle photos do not force permanent polling.
     if [ "${PHOTOS:-0}" = 1 ] && [ "$discovery_rc" = 95 ]; then
      log 'DISCOVERY_RETRY photo_state'
     else
      DISCOVERY_OFF=1; log "DISCOVERY_FALLBACK rc=$discovery_rc"
     fi
     cache_invalidate; previous_card=none; QUEUE_PENDING=1
     if [ "$delay" = 2 ]; then $B sleep 2; else $B sleep "$wait_left"; fi
     return 0;;
 esac
 [ "$delay" != 2 ] || return 0
 IFS=' ' read -r wait_after wait_rest < /proc/uptime || wait_after=$wait_before
 wait_elapsed=$((${wait_after%%.*}-${wait_before%%.*}))
 [ "$wait_elapsed" -ge 1 ] || wait_elapsed=1
 wait_left=$((wait_left-wait_elapsed))
 done
 return 0
}
plain_run() {
 BOOT=$($B cat /proc/sys/kernel/random/boot_id); DISCOVERY_OFF=0; SCAN_HOLD=
 FTP_HEALTH=unknown; FTP_CHECK_DUE=1; FTP_CHECK_BACKOFF=10
 $D/plainftp namespace "$HOST" "$PORT" "$USER" "$ROOT" > "$D/plain.namespace" || return 90
 $B rm -f "$D/plain.previous"; : > "$D/plain.checked"; : > "$D/plain.known"
 cache_invalidate
 backoff=10; previous_card=none; known_card=none; last_scan=0; QUEUE_PENDING=1
 scan_hold_start || return 90
 while [ "$STOP" = 0 ] && [ ! -f "$D/stop" ]; do
  if ! usb_media_ready; then
   cache_invalidate; scan_hold_stop || return 90; delay=1
  elif ! ftp_health_ready; then
   scan_hold_stop || return 90; delay=$FTP_HEALTH_DELAY
  elif media_poll && uptime_seconds; then
   scan_update || return 90
   # Receipt lookup is read-only. Actual transfers still run source_same,
   # which freshly checks recorder/card/open handles and the selected row.
    choose_row || return 90
    if [ -n "$chosen" ]; then
     QUEUE_PENDING=1
     SOURCE_ROW=$chosen; SOURCE_CARD=$CARD; DRIVE=$LETTER
     read VIDEO SIZE XML XSIZE REST <<ROW
$chosen
ROW
     [ -s "$D/plain.checked" ] || log "SCAN_FIRST $VIDEO"
     scan_hold_stop || return 90
     ATTEMPT_SKIPPED=0; plain_attempt; rc=$?
     [ "${FTP_TRANSPORT_FAILED:-0}" != 1 ] || ftp_health_mark error
     if uptime_seconds; then last_scan=$NOW; fi
     case "$rc" in
      0) printf '%s\n' "$chosen" >> "$D/plain.checked" || return 90
         if [ "$priority" = new_or_changed ]; then printf '%s\n' "$chosen" >> "$D/plain.known" || return 90; fi
         backoff=10; delay=0;;
      75) delay=1;;
      90) return 90;;
      *) backoff=$((backoff*2)); delay=$backoff;;
     esac
    else scan_hold_stop || return 90; backoff=10; delay=2
     [ "$QUEUE_PENDING" != 1 ] || log SCAN_DONE
     QUEUE_PENDING=0
    fi
  else
   cache_invalidate
   scan_hold_stop || return 90; previous_card=none; backoff=10; delay=2; QUEUE_PENDING=1
  fi
  [ "$backoff" -le 600 ] || backoff=600
  [ "$delay" -le 600 ] || delay=600
  # No network traffic or power hold during quiet scans/backoff.
  # Success drains the queue promptly; idle/retry intervals remain bounded.
  discovery_wait || return 90
 done
 scan_hold_stop || return 90
 return 42
}
# Optional installation-only handshake on the ordinary FTP server. The host
# creates this one-byte trigger only after confirming physical USB disconnect.
# It is not a planner/receiver and is not polled after starting normal work.
if [ -f "$D/plain.arm" ]; then
 log 'FTP_ARM_WAIT'
 ARM_TOKEN=$($B cat "$D/plain.arm"); armed=0; tries=0
 while [ "$STOP" = 0 ] && [ ! -f "$D/stop" ] && [ "$tries" -lt 120 ]; do
  if printf '%s\n' "$FTP_PASSWORD" | $D/plainftp armed "$HOST" "$PORT" "$USER" "$ROOT" "$ARM_TOKEN"; then armed=1; break; fi
  tries=$((tries+1)); $B sleep 5
 done
 if [ "$armed" != 1 ]; then log 'FTP_ARM_EXPIRED_OR_STOPPED'; FTP_PASSWORD=; $B rmdir "$D/lock"; exit 42; fi
 $B rm -f "$D/plain.arm"
 log 'FTP_ARM_ACCEPTED'
fi
trap 'plain_display_end' EXIT
plain_run; rc=$?
 log "FTP_WORKER_EXIT rc=$rc"
FTP_PASSWORD=
$B rmdir "$D/lock"
exit "$rc"
