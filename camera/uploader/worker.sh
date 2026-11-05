#!/bin/ash
# ILCE-7C 2.00 only. All runtime files live on checked tmpfs.
# NAS gives a plan, but source names/limits and native completion are checked here.
B=/bin/busybox
P=/setting/a7c-uploader
D=/setting/a7c-uploader/ram
trap '' HUP
STOP=0
trap 'STOP=1' TERM INT
log() {
 local log_clock
 LOG_COUNT=$((${LOG_COUNT:-0}+1))
 # At most 15 bounded messages beyond the previous limit, checked on first use.
 if [ "$((LOG_COUNT%16))" = 1 ] && [ -f "$D/events.log" ] && [ "$($B wc -c < "$D/events.log")" -gt 32768 ]; then $B mv "$D/events.log" "$D/events.previous.log"; fi
 IFS= read -r log_clock < /proc/uptime || log_clock=unknown
 printf '%s %s\n' "$1" "$log_clock" >> "$D/events.log"
}

put() { $D/net put "$2" "$3" "$1"; }
plan() { $D/net get plan.txt "$D/plan" 10; }
uptime_seconds() {
 local uptime_unused
 IFS=' ' read -r NOW uptime_unused < /proc/uptime || return 1
 NOW=${NOW%%.*}
 case "$NOW" in ''|*[!0-9]*) return 1;; esac
 [ "${#NOW}" -le 10 ]
}

quiet_unchanged() {
 # Compare fresh native directory/drive data, never a filename-only receipt.
 # Recording/unknown gates clear this state in run(). Clock rollback or an
 # unobserved active-time gap also ends it; no periodic metadata reread when idle.
 # Frontend echoes may include an extra MWF prompt. Ignore only that known
 # framing; retain complete file rows, errors and other diagnostic changes.
 SCAN_SIGNATURE=$(printf '%s\n' "$LETTER"; $B sed 's/\r//g; s/^MWF>//; /^IFSYS dir [A-Z]:\/PRIVATE\/M4ROOT\/CLIP$/d; /^$/d' "$D/dir")
 CLOCK_OK=0
 if uptime_seconds; then CLOCK_OK=1; fi
 [ "$CLOCK_OK" = 1 ] && [ "$QUIET_ARMED" = 1 ] &&
 [ "$NOW" -ge "$QUIET_LAST" ] && [ "$((NOW - QUIET_LAST))" -le 45 ] &&
 [ "$SCAN_SIGNATURE" = "$QUIET_SIGNATURE" ] || return 1
 QUIET_LAST=$NOW
}
arm_quiet() {
 read IDLE_TAG IDLE_DELAY IDLE_EXTRA < "$D/plan"
 [ "$IDLE_TAG" = IDLE ] && [ -z "$IDLE_EXTRA" ] && [ "$CLOCK_OK" = 1 ] || return 1
 case "$IDLE_DELAY" in ''|0*|*[!0-9]*) return 1;; esac
 [ "${#IDLE_DELAY}" -le 3 ] && [ "$IDLE_DELAY" -ge 1 ] && [ "$IDLE_DELAY" -le 240 ] || return 1
 QUIET_LAST=$NOW; QUIET_ARMED=1; QUIET_SIGNATURE=$SCAN_SIGNATURE
 log "NETWORK_QUIET until_source_change plan_hint=$IDLE_DELAY"
}
empty_rec() {
 EMPTY_REC=$($B sed 's/\r//g; /^$/d; /^MPR Debug RecInfo$/d' "$1") || return 1
 [ "$EMPTY_REC" = '[MprMcmd][RecInfo] =====
MON>' ]
}
full_state_idle() {
 # Exact validated suffix. Use only applets present in camera BusyBox (no awk).
 FULL_EXPECTED='MprIf Instance : active
+- Callback() : active
l + owner : active
+- RecParameter
l
+- Status : STATE
+-StillPlayer : none
+-MoviePlayer : none
+-IndexPlayer : none
+-AudioPlayer : none
+-StillRecorder : none
+-MovieRecorder : RECORDER
+-Finalizer : none
+-DubMgr : none
Command Status : Ready
+- Preload Param
+ m_preloadState : 0
+ mp_reservedCmdQueForPreload
+ Count : 0
+ m_execReservedCmdForPreload : 0x40000000
+ mb_existMMgrPreloadSuspendReq : 0
+ mb_prohibitPreload : 0
+ mb_existNewRequestOfPreload : 0
+ m_latestPreloadResult : 0x00000000
+ mb_needWaitAlmForPreloadRestart: 0
+ mb_waitingForAlarm : 0
+ mb_alarmAvailable : 1
+ m_waitTime : 500[ms]
MON>'
 FULL_NORMAL=$($B sed 's/\r//g; s/[[:blank:]][[:blank:]]*/ /g; s/^ //; s/ $//; /^$/d; s/active (at 0x[0-9A-Fa-f][0-9A-Fa-f]*)/active/g' "$1") || return 1
 if [ "${2:-}" = still ]; then
  # Only used between two exact still STANDBY/zero-count snapshots.
  printf '%s\n' "$FULL_NORMAL" | $B grep -q -x '+- Status : STAT_IDLE' || return 1
  printf '%s\n' "$FULL_NORMAL" | $B grep -q -x '+-StillRecorder : active' || return 1
  FULL_NORMAL=$(printf '%s\n' "$FULL_NORMAL" | $B sed 's/^+-StillRecorder : active$/+-StillRecorder : none/') || return 1
 fi
 [ "$(printf '%s\n' "$FULL_NORMAL" | $B grep -c -x '= = = = = MprIf Debug Information = = = = =')" = 1 ] || return 1
 [ "$(printf '%s\n' "$FULL_NORMAL" | $B grep -c -x 'l ProductName : ILCE-7C')" = 1 ] || return 1
 if printf '%s\n' "$FULL_NORMAL" | $B grep -E '(ILLEGAL|FAILURE|ERROR) : true|OVERFLOW|\[ERR\]|\[ERROR\]|Failed to|Illegal ' > /dev/null; then return 1; fi
 FULL_BODY=$(printf '%s\n' "$FULL_NORMAL" | $B sed -n '/^MprIf Instance :/,$p') || return 1
 if printf '%s\n' "$FULL_BODY" | $B grep -q -x '+- Status : STAT_IDLE'; then
  printf '%s\n' "$FULL_BODY" | $B grep -q -x '+-MovieRecorder : none' || return 1
 elif printf '%s\n' "$FULL_BODY" | $B grep -q -x '+- Status : STAT_MREC_STBY'; then
  printf '%s\n' "$FULL_BODY" | $B grep -q -x '+-MovieRecorder : active' || return 1
 else return 1; fi
 FULL_BODY=$(printf '%s\n' "$FULL_BODY" | $B sed 's/^+- Status : STAT_IDLE$/+- Status : STATE/; s/^+- Status : STAT_MREC_STBY$/+- Status : STATE/; s/^+-MovieRecorder : none$/+-MovieRecorder : RECORDER/; s/^+-MovieRecorder : active$/+-MovieRecorder : RECORDER/') || return 1
 [ "$FULL_BODY" = "$FULL_EXPECTED" ]
}
recording_idle() {
 FULL_STATE_USED=0
 $D/monitor recording > "$D/rec" 2> "$D/query.err" || return 1
 if [ "$($B grep -c 'contentType:Movie(XAVC), RecCnt1:0, RecCnt2:0, RecStatus:REC_STATE_STANDBY' "$D/rec")" = 2 ]; then return 0; fi
 empty_rec "$D/rec" || return 2
 [ -x "$D/monitor" ] || return 2
 $D/monitor full-info > "$D/full-state.txt" 2> "$D/query.err" || return 1
 full_state_idle "$D/full-state.txt" || return 2
 # Do not use a fallback across recorder initialization or state transitions.
 $D/monitor recording > "$D/rec-recheck" 2> "$D/query.err" || return 1
 empty_rec "$D/rec-recheck" || return 2
 FULL_STATE_USED=1
}
report() {
 REPORT_STAGE=drive
 $D/monitor drive > "$D/drive" 2> "$D/query.err" || return 1
 LETTER=$($B sed -n "s/\r//g; s/^driveLetter = '\([A-Z]\)'$/\1/p" "$D/drive" | $B tail -1)
 case "$LETTER" in [A-Z]) ;; *) return 1;; esac
 REPORT_STAGE=recording
 recording_idle || return $?
 REPORT_STAGE=directory
 $D/monitor dir "$LETTER" > "$D/dir" 2> "$D/query.err" || return 1
 REPORT_STAGE=file_status
 $D/monitor info > "$D/info" 2> "$D/query.err" || return 1
 { echo A7C_RESIDENT_V1; echo "BOOT=$BOOT"; $B cat "$D/drive" "$D/rec";
   if [ "$FULL_STATE_USED" = 1 ]; then
    echo A7C_FULL_STATE_BEGIN; $B cat "$D/full-state.txt"; echo A7C_FULL_STATE_END
    echo A7C_REC_RECHECK_BEGIN; $B cat "$D/rec-recheck"; echo A7C_REC_RECHECK_END
   fi
   $B cat "$D/dir" "$D/info"; echo A7C_STATUS_END; } > "$D/status"
 [ "$($B wc -c < "$D/status")" -le 262144 ]
}
read_plan() {
 read ACTION DRIVE VIDEO SIZE XML XSIZE ATTEMPT EXTRA < "$D/plan"
 [ "$ACTION" = META ] || return 2
 case "$DRIVE" in [A-Z]) ;; *) return 1;; esac
 case "$VIDEO" in C[0-9][0-9][0-9][0-9].MP4) ;; *) return 1;; esac
 [ "$XML" = "${VIDEO%.MP4}M01.XML" ] && [ -z "$EXTRA" ] && [ "$DRIVE" = "$LETTER" ] || return 1
 case "$SIZE:$XSIZE" in *[!0-9:]*|:*|*:) return 1;; esac
 case "$ATTEMPT" in *[!a-f0-9]*|'') return 1;; esac
 [ "${#ATTEMPT}" = 24 ] && [ "${#SIZE}" -le 12 ] && [ "${#XSIZE}" -le 5 ] || return 1
 [ "$((SIZE > 0 && SIZE <= 274877906944))" = 1 ] && [ "$XSIZE" -gt 0 ] && [ "$XSIZE" -le 16384 ]
}
metadata() {
 STAGE=metadata_copy; checkpoint
 $B rm -f "$D/metadata.xml"
 $D/monitor copy "$DRIVE" "$XML" 10 > "$D/xml-copy.log" 2>&1
 metadata_rc=$?; checkpoint
 [ "$metadata_rc" = 0 ] || return 1
 metadata_bytes=missing
 [ ! -f "$D/metadata.xml" ] || metadata_bytes=$($B wc -c < "$D/metadata.xml")
 [ "$metadata_bytes" = "$XSIZE" ] || return 1
 STAGE=metadata_send; checkpoint
 put 10 "metadata-$ATTEMPT.xml" "$D/metadata.xml" > "$D/ftp.log" 2>&1 || return 1
 plan >> "$D/ftp.log" 2>&1 || return 1
 read NEXT REST < "$D/plan"
 if [ "$NEXT" = SKIP ] && [ "$REST" = "$ATTEMPT" ]; then log "SKIP $VIDEO"; return 2; fi
 [ "$($B cat "$D/plan")" = "UPLOAD $DRIVE $VIDEO $SIZE $XML $XSIZE $ATTEMPT" ]
}
wait_child() {
 # A trapped TERM must not make wait look like successful native completion.
 wait "$1"; CHILD_RC=$?
 while kill -0 "$1" 2>/dev/null; do wait "$1"; CHILD_RC=$?; done
}
scan_hold_stop() {
 [ -n "$SCAN_HOLD" ] || return 0
 : > "$D/lease.done"
 CHILD_RC=1; wait_child "$SCAN_HOLD"; SCAN_HOLD=
 [ "$CHILD_RC" = 0 ] && $B grep -qx 'PROBE_DONE set=0 clear=0 guardian_status=0' "$D/scan-lease.log" || return 90
 $B rm -f "$D/lease.ready" "$D/lease.done"
 log 'SCAN_HOLD_RELEASED'
}
scan_hold_start() {
 # One bounded lease per worker startup, only for the first stability window.
 # Release and reap before an upload lease reuses these handshake files.
 $B rm -f "$D/lease.done" "$D/lease.ready"
 $D/lease --upload-lease 90 > "$D/scan-lease.log" 2>&1 & SCAN_HOLD=$!
 n=0
 while [ ! -f "$D/lease.ready" ] && [ "$n" -lt 8 ] && kill -0 "$SCAN_HOLD" 2>/dev/null; do $B sleep 1; n=$((n+1)); done
 if [ ! -f "$D/lease.ready" ]; then scan_hold_stop; return 90; fi
 log 'SCAN_HOLD_STARTED limit=90'
}
cleanup_completed_fifos() {
 # Called only after waiting for both relay and network children. Preserve
 # readers/FIFOs when native completion or guardian shutdown is uncertain.
 case "$copy_rc" in 0|73|76) ;; *) return 1;; esac
 [ -f "$D/copy.done" ] && [ -f "$D/guard.done" ] || return 1
 $B grep -qx 'normal\|recovered' "$D/guard.done" || return 1
 $B rm -f "$D/source.fifo" "$D/network.fifo"
}
checkpoint() {
 # Diagnostic mode only: retain one bounded record across loss of tmpfs.
 # Normal long-term operation never writes recurring logs to camera NAND.
 [ -f "$P/pause-after-failure" ] || return 0
 { echo "revision=v8w stage=$STAGE video=$VIDEO attempt=$ATTEMPT metadata_rc=$metadata_rc metadata_bytes=$metadata_bytes";
   $B cat /proc/uptime
   for f in xml-copy.log copy.log relay.result ftp.log lease.log; do
    if [ -f "$D/$f" ]; then echo "FILE=$f"; $B tail -c 1536 "$D/$f"; fi
   done; } > "$P/last-diagnostic.txt"
}
transfer() {
 STAGE=video_prepare; checkpoint
 transfer_rc=1; copy_rc=not_started; relay_rc=not_started; ftp_rc=not_started
 : > "$D/copy.log"; : > "$D/relay.log"
 if report && put 10 verify.txt "$D/status" > "$D/ftp.log" 2>&1; then
  if $B mkfifo "$D/source.fifo" "$D/network.fifo"; then
   $D/net put "video-$ATTEMPT.mp4" "$D/network.fifo" "$LIMIT" > "$D/ftp.log" 2>&1 & ftp=$!
   $D/relay "$D" "$SIZE" > "$D/relay.log" 2>&1 & relay=$!
   n=0
   while [ ! -f "$D/relay.ready" ] && [ "$n" -lt 12 ] && kill -0 "$relay" 2>/dev/null; do $B sleep 1; n=$((n+1)); done
   copy_rc=1
   if [ -f "$D/relay.ready" ] && kill -0 "$relay" 2>/dev/null; then
    STAGE=video_copy; checkpoint
    $D/monitor copy "$DRIVE" "$VIDEO" "$LIMIT" > "$D/copy.log" 2>&1
    copy_rc=$?
   fi
   if [ "$copy_rc" = 0 ] || [ "$copy_rc" = 73 ] || [ "$copy_rc" = 76 ] || [ ! -f "$D/relay.ready" ]; then : > "$D/copy.done"; fi
   # Code 76 means the monitor never wrote the native command; drain empty
   # readers normally and let network backoff retry. A later timeout is NOT proof that native IFSYS has stopped. The relay
   # and its guardian retain the reader; stop this worker rather than overlap.
   if [ "$copy_rc" != 0 ] && [ "$copy_rc" != 73 ] && [ "$copy_rc" != 76 ] && [ -f "$D/relay.ready" ]; then
    log 'NATIVE_COMPLETION_UNKNOWN: uploader halted, reader retained'
    return 90
   fi
   CHILD_RC=1; wait_child "$relay"; relay_rc=$CHILD_RC
   if [ "$relay_rc" != 0 ]; then kill -TERM "$ftp" 2>/dev/null; fi
   CHILD_RC=1; wait_child "$ftp"; ftp_rc=$CHILD_RC
   cleanup_completed_fifos
   if [ "$copy_rc" = 0 ] && [ "$relay_rc" = 0 ] && [ "$ftp_rc" = 0 ] && [ -f "$D/guard.done" ]; then
    read BAD COUNT HASH EXTRA < "$D/relay.result"
    case "$HASH" in *[!a-f0-9]*|'') BAD=1;; esac
    if [ "$BAD" = 0 ] && [ "$COUNT" = "$SIZE" ] && [ "${#HASH}" = 64 ] && [ -z "$EXTRA" ]; then
     printf '%s %s %s\n' "$ATTEMPT" "$HASH" "$COUNT" > "$D/commit.txt"
     if put 10 "commit-$ATTEMPT.txt" "$D/commit.txt" > "$D/commit.log" 2>&1 && plan >> "$D/commit.log" 2>&1 && [ "$($B cat "$D/plan")" = "DONE $ATTEMPT" ]; then
      transfer_rc=0; log "DONE $VIDEO $COUNT $HASH"
     fi
    fi
   fi
  fi
 fi
 return "$transfer_rc"
}
attempt() {
 $B rm -f "$D/lease.done" "$D/lease.ready" "$D/relay.ready" "$D/guard.done" "$D/copy.done" "$D/source.fifo" "$D/network.fifo"
 for f in xml-copy.log copy.log relay.log relay.result ftp.log commit.log lease.log; do : > "$D/$f"; done
 STAGE=lease_start; metadata_rc=not_started; metadata_bytes=unknown
 copy_rc=not_started; relay_rc=not_started; ftp_rc=not_started; transfer_rc=not_started
 LIMIT=$((150 + SIZE / 131072)); [ "$LIMIT" -le 86000 ] || LIMIT=86000
 checkpoint
 $D/lease --upload-lease "$LIMIT" > "$D/lease.log" 2>&1 & lease=$!
 n=0
 while [ ! -f "$D/lease.ready" ] && [ "$n" -lt 8 ] && kill -0 "$lease" 2>/dev/null; do $B sleep 1; n=$((n+1)); done
 attempt_rc=1
 if [ -f "$D/lease.ready" ]; then
  metadata; attempt_rc=$?
  if [ "$attempt_rc" = 0 ]; then transfer; attempt_rc=$?; fi
 fi
 STAGE=release; checkpoint
 : > "$D/lease.done"
 CHILD_RC=1; wait_child "$lease"; lease_rc=$CHILD_RC
 [ "$lease_rc" = 0 ] || attempt_rc=90
 STAGE=finished; checkpoint
 { echo "revision=v8w video=$VIDEO attempt_rc=$attempt_rc transfer_rc=$transfer_rc lease_rc=$lease_rc metadata_rc=$metadata_rc metadata_bytes=$metadata_bytes copy_rc=$copy_rc relay_rc=$relay_rc ftp_rc=$ftp_rc";
   for f in xml-copy.log lease.log relay.result copy.log relay.log ftp.log commit.log; do
    if [ -f "$D/$f" ]; then echo "FILE=$f"; $B tail -c 1536 "$D/$f"; fi
   done
   $B cat /proc/uptime /proc/meminfo; } > "$D/result.txt"
 if [ -f "$P/pause-after-failure" ]; then $B cp "$D/result.txt" "$P/last-diagnostic.txt"; fi
 put 10 result.txt "$D/result.txt" > "$D/result-ftp.log" 2>&1
 return "$attempt_rc"
}

scan_diagnostic() {
 # Keep one bounded RAM snapshot even in normal mode, available on demand.
 # This diagnostic never authorizes media access or adds idle network traffic.
 { echo "revision=v8w stage=$REPORT_STAGE report_rc=$report_rc worker_pid=$$";
   $B cat /proc/uptime
   for f in drive rec full-state.txt rec-recheck query.err ftp.log; do
    if [ -f "$D/$f" ]; then
     echo "FILE=$f"
     if [ "$f" = query.err ]; then $B sed -n '1,2p' "$D/$f"; fi
     $B tail -c 1536 "$D/$f"
    fi
   done; } > "$D/scan-diagnostic.txt"
 [ -f "$P/pause-after-failure" ] || return 0
 # Only changed gate results are persisted, bounded to eight writes per worker.
 signature=$(printf '%s\n' "$REPORT_STAGE:$report_rc:$LETTER"; $B cat "$D/rec" "$D/query.err" 2>/dev/null)
 if [ "$signature" != "$last_signature" ] && [ "$diag_writes" -lt 8 ]; then
  $B cp "$D/scan-diagnostic.txt" "$P/last-scan-diagnostic.txt"
  diag_writes=$((diag_writes+1)); last_signature=$signature
 fi
 put 4 result.txt "$D/scan-diagnostic.txt" > "$D/diagnostic-ftp.log" 2>&1
}

run() {
 [ "$((4294967296 + 1))" = 4294967297 ] || return 90
 BOOT=$($B cat /proc/sys/kernel/random/boot_id)
 [ "${#BOOT}" = 36 ] || return 90
 TOKEN=$($B cat "$P/token")
 [ "${#TOKEN}" = 64 ] || return 90
 backoff=10; diag_writes=0; last_signature=uninitialized
 QUIET_LAST=0; QUIET_ARMED=0; QUIET_SIGNATURE=uninitialized
 SCAN_HOLD=
 scan_hold_start || return 90
 if [ -f "$P/pause-after-failure" ]; then
  { echo "revision=v8w worker_pid=$$"; $B cat /proc/uptime /tmp_network/a7c-uploader.claim; } > "$P/last-start.txt"
 fi
 while [ "$STOP" = 0 ] && [ ! -f "$D/stop" ] && [ -f "$P/enabled" ]; do
  report; report_rc=$?
  if [ "$report_rc" = 0 ]; then
   if quiet_unchanged; then backoff=10
   else
    QUIET_ARMED=0
    if put 10 status.txt "$D/status" > "$D/ftp.log" 2>&1 && plan >> "$D/ftp.log" 2>&1; then
    if read_plan; then
     scan_hold_stop || return 90
     attempt; rc=$?
     if [ "$rc" = 90 ]; then return 90; fi
     if [ "$rc" = 1 ] && [ -f "$P/pause-after-failure" ]; then log "PAUSED_AFTER_FAILURE"; return 42; fi
     if [ "$rc" = 0 ] || [ "$rc" = 2 ]; then backoff=10; else backoff=$((backoff*2)); fi
    else
     if arm_quiet; then scan_hold_stop || return 90; fi
     backoff=10
    fi
    else scan_hold_stop || return 90; REPORT_STAGE=status_network; report_rc=3; scan_diagnostic; backoff=$((backoff*2)); fi
   fi
  else scan_hold_stop || return 90; QUIET_ARMED=0; scan_diagnostic; backoff=10; fi
  [ "$backoff" -le 600 ] || backoff=600
  # No power lease while idle or backing off; ordinary camera standby suspends us.
  $B sleep "$backoff"
 done
 scan_hold_stop || return 90
 return 42
}
$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs ' /proc/mounts || exit 90
$B mkdir -p "$D" || exit 90
$B mkdir "$D/lock" || exit 90
for n in monitor relay lease net; do $B cp "$P/$n" "$D/$n" && $B chmod 700 "$D/$n" || exit 90; done
# Bounded runtime event logs; no recurring writes to camera NAND.
run
RC=$?
$B rmdir "$D/lock"
exit "$RC"
