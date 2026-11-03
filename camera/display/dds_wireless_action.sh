#!/bin/ash
# Installed only after USB hash/idle checks and same-boot timer cancel proof.
# PROBE still requires host-observed USB absence and a user-ready shooting UI.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
$B grep -q '^a7c-debug-ram /setting/a7c-debug/ram tmpfs ' /proc/mounts || exit 90
cd / || exit 90
umask 077
case "$1" in
 PAUSE)
    # The current guarded transaction completes restoration before stopping.
    # Never kill a native setter or its independent cleanup guardian here.
    printf 'cancel\n' > "$D/cancel" || exit 94;;
 STATUS)
    echo A7C_DEBUG_V2
    for n in update-result status done prewrite-abort blink-stop blink-history capture-attempts inspect-before.log overlay.log inspect-after.log screen.log manage-inspect.log query-uptime layout.rc layout.log shooting.rc shooting.log; do
        if [ -f "$D/$n" ]; then echo FILE=$n; $B cat "$D/$n"; fi
    done
    # Fixed RAM diagnostics for the upload consumer; no credentials or native
    # queries. Keep STATUS useful even if the consumer exits before claiming DDS.
    U=/setting/a7c-uploader/ram
    for n in display.active display.log display.disabled; do
        if [ -f "$U/$n" ]; then
            echo UPLOAD_FILE=$n
            $B tail -c 2000 "$U/$n"; echo
        fi
    done
    for phase in before after; do
        if [ -f "$D/layout-$phase.bin" ]; then
            echo LAYOUT_TEXT=$phase
            $B grep -E 'Display LayoutList|Physical:|groupID:' "$D/layout-$phase.bin"
        fi
    done
    # Metadata only; do not open devices or read pixels for STATUS. Include the
    # real backing path so a failed capture never implies an unverified device.
    p=$($B cat "$D/native.pid")
    case "$p" in ''|*[!0-9]*) p=invalid;; esac
    if [ "$p" != invalid ] && [ "$($B pidof im.elf)" = "$p" ] &&
       [ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$D/boot-id")" ]; then
        echo CURRENT_SHARED_MAPS_LIMIT_BYTES=12000
        # This camera's BusyBox has no head applet. bs=1 also handles short
        # pipe reads without ending the bounded copy before 12000 bytes.
        $B grep ' rw-s ' "/proc/$p/maps" | $B dd bs=1 count=12000 2>/dev/null
        echo
    else echo CURRENT_SHARED_MAPS_UNAVAILABLE; fi
    echo A7C_DEBUG_END;;
 PROBE|RUN)
    [ ! -d "$D/maintenance" ] || exit 92
    [ ! -e "$D/cancel" ] || exit 94
    continuous=0
    if [ -e "$D/continuous-blink" ]; then
        [ "$($B cat "$D/continuous-blink")" = 300 ] || exit 95
        [ ! -e "$D/blink" ] || exit 95
        [ "$($B cat "$D/shooting-overlay")" = 1 ] || exit 95
        continuous=1
    fi
    if [ "$1" = PROBE ]; then
        # Claim is never reset, including ambiguous worker startup failures.
        # Serialize the check/claim with updates and upload-driven display.
        $B mkdir "$D/maintenance" || exit 92
        $B mkdir "$D/claimed" || { $B rmdir "$D/maintenance"; exit 92; }
        $B rmdir "$D/maintenance" || exit 92
        if [ "$continuous" = 1 ]; then
            echo stage=launching > "$D/status"
            "$D/blink-launch" || exit 97
            exit 0
        fi
    else
        [ "$continuous" = 1 ] && [ -d "$D/claimed" ] || exit 95
        $B mkdir "$D/blink-worker.started" || exit 92
        $B mkdir "$D/blink-worker.running" || exit 92
    fi
    display_started=0
    finish() {
        rc=$?
        # Publish a positive prewrite proof only on a normal shell exit. A
        # killed/ambiguous launch gets no proof and keeps its claim blocked.
        if [ "$display_started" = 0 ] && [ ! -e "$D/overlay.log" ]; then
            case "$rc" in 94|95|96) echo no_display_started=1 > "$D/prewrite-abort";; esac
        fi
        printf 'exit=%s\n' "$rc" > "$D/done"
        if [ "$continuous" = 1 ]; then $B rmdir "$D/blink-worker.running"; fi
    }
    trap finish EXIT
    echo stage=checking > "$D/status"
    [ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$D/boot-id")" ] || exit 95
    p=$($B cat "$D/native.pid")
    a=$($B cat "$D/native.base")
    mode=$($B cat "$D/native.mode")
    timer=$($B cat "$D/native.timer")
    case "$p" in ''|*[!0-9]*) exit 95;; esac
    case "$a" in ''|*[!0-9a-f]*) exit 95;; esac
    case "$timer" in ''|*[!0-9]*) exit 95;; esac
    case "$mode" in
        --once) first=1;; --once-idle) first=0;;
        --once-shooting) first=1;; --once-shooting-idle) first=0;;
        *) exit 95;;
    esac
    case "$mode" in
        --once-shooting*)
            [ "$($B cat "$D/shooting-overlay")" = 1 ] || exit 95
            for flag in diagnose-only capture-only physical-only retry-readonly; do
                [ ! -e "$D/$flag" ] || exit 95
            done;;
        *) [ ! -e "$D/shooting-overlay" ] || exit 95;;
    esac
    cycles=1
    if [ "$continuous" = 1 ]; then
        case "$mode" in --once-shooting|--once-shooting-idle) cycles=120;; *) exit 95;; esac
    fi
    if [ -e "$D/blink" ]; then
        [ "$($B cat "$D/blink")" = 4 ] || exit 95
        case "$mode" in --once-shooting|--once-shooting-idle) cycles=4;; *) exit 95;; esac
    fi
    [ "$($B pidof im.elf)" = "$p" ] || exit 95
    attempt=0
    if [ -f "$D/retry-readonly" ]; then
        # Explicit install-only mode; at most three host-triggered attempts.
        # A crash keeps the claim. Successful/partial output is never replaced.
        for flag in retry-readonly diagnose-only capture-only physical-only; do
            [ "$($B cat "$D/$flag")" = 1 ] || exit 95
        done
        for n in overlay.log shooting.raw shooting.rle; do
            [ ! -e "$D/$n" ] || exit 95
        done
        previous=0
        if [ -e "$D/capture-attempts" ]; then previous=$($B cat "$D/capture-attempts"); fi
        case "$previous" in 0) attempt=1;; 1) attempt=2;; 2) attempt=3;; *) exit 92;; esac
        printf '%s\n' "$attempt" > "$D/capture-attempts" || exit 95
    fi
    if [ -f "$D/diagnose-only" ] || [ -f "$D/shooting-overlay" ]; then
        # Fixed read-only native query, hash-verified at USB installation.
        # Default diagnosis does not invoke the DDS binary. Optional screenshot
        # uses only its separately gated read-only command, never a display mode.
        echo stage=layout-diagnosis > "$D/status"
        $B timeout -t 3 -s 9 /usr/bin/ulogio dk 0x034fd000 0x8000 "$D/layout-before.bin" || exit 96
        [ "$($B wc -c < "$D/layout-before.bin")" -eq 32768 ] || exit 96
        "$D/ui-layout" > "$D/layout.log" 2>&1
        rc=$?; printf '%s\n' "$rc" > "$D/layout.rc"
        [ "$rc" = 0 ] || exit 96
        $B sleep 1
        $B timeout -t 3 -s 9 /usr/bin/ulogio dk 0x034fd000 0x8000 "$D/layout-after.bin" || exit 96
        [ "$($B wc -c < "$D/layout-after.bin")" -eq 32768 ] || exit 96
        if [ -f "$D/capture-only" ]; then
            echo stage=shooting-capture > "$D/status"
            capture_mode=--capture-shooting
            [ ! -f "$D/physical-only" ] || capture_mode=--capture-physical
            "$D/capture" "$capture_mode" "$p" "$a" > "$D/shooting.log" 2>&1
            rc=$?; printf '%s\n' "$rc" > "$D/shooting.rc"
            if [ "$rc" = 84 ] && [ "$attempt" -gt 0 ] && [ "$attempt" -lt 3 ] &&
               $B grep -qx 'DDS_CAPTURE_REJECT physical_required matches=0 pixel_read_started=0' "$D/shooting.log" &&
               ! $B grep -Eq '^DDS_PHYSICAL|^DDS_CAPTURE name=' "$D/shooting.log" &&
               [ ! -e "$D/shooting.raw" ] && [ ! -e "$D/shooting.rle" ]; then
                echo stage=awaiting-shooting > "$D/status"
                $B rmdir "$D/claimed" || exit 95
                exit 96
            fi
            [ "$rc" = 0 ] || exit 96
            echo stage=captured > "$D/status"
            exit 0
        fi
        if [ ! -f "$D/shooting-overlay" ]; then
            echo stage=diagnosed > "$D/status"
            exit 0
        fi
    fi
    "$D/capture" --inspect "$p" "$a" > "$D/inspect-before.log" 2>&1 || exit 96
    if ! $B grep -qx "DDS_STATE attached timer=$timer first=$first override=0 visible=0 others_idle=1" "$D/inspect-before.log"; then
        # Native sleep/resume may recreate DDS after host REARM. Rebind only
        # an untouched shooting lifecycle, checked immediately before drawing.
        [ -f "$D/shooting-overlay" ] || exit 95
        read state attached timer_field first_field rest < "$D/inspect-before.log" || exit 95
        observed=${timer_field#timer=}
        case "$observed" in ''|*[!0-9]*) exit 95;; esac
        [ "$observed" -gt 0 ] && [ "$observed" -lt 512 ] || exit 95
        $B grep -qx "DDS_STATE attached timer=$observed first=1 override=0 visible=0 others_idle=1" "$D/inspect-before.log" &&
        $B grep -qx 'DDS_FONT original_matches=1 bytes=128' "$D/inspect-before.log" &&
        $B grep -qx 'DDS_POSITION original_matches=1 x=30 y=250' "$D/inspect-before.log" || exit 95
        printf '%s\n' "$observed" > "$D/native.timer.next" &&
        $B mv "$D/native.timer.next" "$D/native.timer" &&
        $B rm -f "$D/restore-proof" || exit 95
        timer=$observed;first=1;mode=--once-shooting
        printf '%s\n' "$mode" > "$D/native.mode" || exit 95
    fi
    [ ! -e "$D/cancel" ] || exit 94
    $B cat /proc/uptime > "$D/query-uptime"
    echo stage=display > "$D/status"
    [ ! -e "$D/overlay.log" ] || exit 95
    # A single claim permits a fixed blink sequence, never failure retries.
    # Each binary invocation has its own guardian and restores font/position,
    # cancels the timer and redraws before the next cycle can begin.
    cycle=1
    read begin unused < /proc/uptime || exit 95
    begin=${begin%%.*}
    case "$begin" in ''|*[!0-9]*) exit 95;; esac
    while [ "$cycle" -le "$cycles" ]; do
        if [ -e "$D/cancel" ]; then
            if [ "$continuous" = 1 ]; then echo reason=cancel > "$D/blink-stop"; break; fi
            exit 94
        fi
        if [ "$continuous" = 1 ]; then
            read now unused < /proc/uptime || exit 95
            now=${now%%.*}
            case "$now" in ''|*[!0-9]*) exit 95;; esac
            [ "$now" -ge "$begin" ] || exit 95
            if [ "$((now-begin))" -ge 300 ]; then echo reason=deadline > "$D/blink-stop"; break; fi
        fi
        [ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat "$D/boot-id")" ] || exit 95
        [ "$($B pidof im.elf)" = "$p" ] || exit 95
        if [ "$cycle" -gt 1 ]; then
            # Retain the completed frames until another cycle actually starts.
            $B rm -f "$D/dds-before.raw" "$D/dds-during.raw" "$D/dds-late.raw" "$D/dds-after.raw" || exit 98
            if [ "$continuous" = 1 ]; then : > "$D/overlay.log"; fi
        fi
        display_started=1
        if [ "$cycles" -gt 1 ]; then
            printf 'DDS_BLINK cycle=%s total=%s\n' "$cycle" "$cycles" >> "$D/overlay.log"
        fi
        "$D/capture" "$mode" "$p" "$a" >> "$D/overlay.log" 2>&1
        rc=$?
        [ "$rc" = 0 ] || exit 97
        "$D/capture" --inspect "$p" "$a" > "$D/inspect-after.log" 2>&1 || exit 98
        if [ "$cycles" -gt 1 ]; then
            $B grep -qx "DDS_STATE attached timer=$timer first=0 override=0 visible=0 others_idle=1" "$D/inspect-after.log" || exit 98
            $B grep -qx 'DDS_FONT original_matches=1 bytes=128' "$D/inspect-after.log" || exit 98
            $B grep -qx 'DDS_POSITION original_matches=1 x=30 y=250' "$D/inspect-after.log" || exit 98
            # Success also means the native client's post-cleanup empty-region
            # check passed. Keep the first visible snapshot and final four.
            for frame in before during late after; do
                [ "$($B wc -c < "$D/dds-$frame.raw")" -eq 614400 ] || exit 98
            done
            if [ "$cycle" = 1 ]; then
                [ ! -e "$D/dds-first.raw" ] || exit 98
                $B cp "$D/dds-during.raw" "$D/dds-first.raw" || exit 98
            fi
            if [ "$cycle" -lt "$cycles" ]; then
                # Only this successful same-process sequence establishes that
                # the previous timer was cancelled; do not infer from first=0.
                mode=--once-shooting-idle
            fi
        fi
        if [ "$continuous" = 1 ]; then
            printf 'cycle=%s restored=1\n' "$cycle" >> "$D/blink-history"
            printf 'stage=blinking cycle=%s\n' "$cycle" > "$D/status"
        fi
        cycle=$((cycle+1))
    done
    echo stage=restored > "$D/status";;
 *) exit 64;;
esac
