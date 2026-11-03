#!/bin/ash
# Stable RAM-only management plane; not replaceable by PUSH.
B=/bin/busybox
D=/setting/a7c-debug/ram/dds-once
umask 077
$B grep -q "^a7c-display-ram $D tmpfs " /proc/mounts || exit 90
cd "$D" || exit 90
inactive_helpers() {
    [ ! -d blink-worker.running ] || return 92
    # Resolve procfs links in one BusyBox process instead of one per PID.
    # Transient/kernel exe read failures were ignored by the previous scan.
    # Require our own stable link so an empty/failed listing cannot pass.
    local helper_links helper_line
    helper_links=$($B ls -ln /proc/[0-9]*/exe 2>/dev/null)
    case "$helper_links" in *" /proc/$$/exe -> "*) ;; *) return 95;; esac
    while IFS= read -r helper_line; do
        case "$helper_line" in
            *" -> $D/capture"*|*" -> $D/incoming"*|*" -> $D/redraw"*|*" -> $D/blink-launch"*) return 92;;
        esac
    done <<LINKS
$helper_links
LINKS
}
clean_abort() {
    # Explicit shell proof from a completed preflight; no renderer was called.
    # The absence of output alone is never enough to release a failed claim.
    if [ -f prewrite-abort ] && [ ! -e overlay.log ] &&
       $B grep -qx 'no_display_started=1' prewrite-abort &&
       $B grep -Eq '^exit=(94|95|96)$' done; then return 0; fi
    # capture exits here BEFORE installing font/coordinates or sending DDS.
    # Keep all unknown/post-write failures blocked, even if a partial log exists.
    [ -f done ] && $B grep -qx 'exit=97' done &&
    $B grep -qx 'DDS_GUARD ready=1' overlay.log &&
    [ "$($B grep -Ec '^DDS_ABORT baseline_capture=(8[0-9]|98) guardian=0$' overlay.log)" = 1 ] &&
    ! $B grep -Eq '^DDS_FONT install=|^DDS_POSITION install=|^DDS_SEND |^DDS_ARM |^DDS_DONE ' overlay.log
}
inactive() {
    inactive_helpers || return $?
    if [ -d claimed ]; then
        { [ -f done ] && $B grep -qx 'exit=0' done && $B grep -qx 'stage=restored' status; } ||
        clean_abort || return 92
    fi
}
identity() {
    [ "$($B cat /proc/sys/kernel/random/boot_id)" = "$($B cat boot-id)" ] || return 95
    p=$($B cat native.pid);a=$($B cat native.base);timer=$($B cat native.timer)
    case "$p:$a:$timer" in *[!0-9a-f:]*|:*|*::*) return 95;; esac
    [ "$($B pidof im.elf)" = "$p" ] || return 95
}
idle() {
    inactive && identity || return $?
    ./capture --inspect "$p" "$a" > manage-inspect.log 2>&1 || return 95
    read state attached timer_field first_field rest < manage-inspect.log || return 95
    observed=${timer_field#timer=}
    case "$observed" in ''|*[!0-9]*) return 95;; esac
    $B grep -Eq "^DDS_STATE attached timer=$observed first=[01] override=0 visible=0 others_idle=1$" manage-inspect.log || return 95
    $B grep -qx 'DDS_FONT original_matches=1 bytes=128' manage-inspect.log &&
    $B grep -qx 'DDS_POSITION original_matches=1 x=30 y=250' manage-inspect.log || return 95
    if [ "$observed" != "$timer" ]; then
        # DDS can recreate its timer without changing boot/PID. Accept only
        # untouched lazy-init state, never an unknown first=0 lifecycle.
        # inactive() requires the previous claimed transaction to be clean.
        [ "$first_field" = first=1 ] || return 95
        printf '%s\n' "$observed" > native.timer.next &&
        $B mv native.timer.next native.timer || return 95
        $B rm -f restore-proof || return 95
        timer=$observed
    fi
    if $B grep -q 'first=0 ' manage-inspect.log; then
        # Reuse only this same session's successful final transaction.
        if [ -f done ] && ! clean_abort; then
            $B grep -qx 'exit=0' done && $B grep -qx 'stage=restored' status || return 95
            $B grep -q "DDS_CANCEL timer=$timer transport=0 response=0" overlay.log &&
            $B grep -Eq '^DDS_DONE display=0 cleanup=0 guardian=0 captures=0,0,(0|98)$' overlay.log || return 95
            printf '%s %s %s\n' "$($B cat boot-id)" "$p" "$timer" > restore-proof || return 95
        else
            [ "$($B cat restore-proof)" = "$($B cat boot-id) $p $timer" ] || return 95
        fi
    fi
}
role_path() {
    case "$1" in capture) target=capture;; action) target=action.sh;; *) return 64;; esac
}
validate() {
    case "$target" in
      capture)
        # The transport checks ELF32 ARM identity before this commit.
        # Rollback uses only a previously accepted role file.
        "$B" chmod 700 "$1" || return 96
        "./$1" --inspect "$p" "$a" > candidate-inspect.log 2>&1 || return 96
        $B grep -qx 'DDS_FONT original_matches=1 bytes=128' candidate-inspect.log &&
        $B grep -qx 'DDS_POSITION original_matches=1 x=30 y=250' candidate-inspect.log || return 96;;
      action.sh) /bin/ash -n "$1" || return 96;;
    esac
}
case "$1" in
 XREADLOCK)
    # Existing frames are evidence, even after an unknown display failure.
    # They can be read only once both renderer and independent guardian exit.
    # This does not authorize capture, update, rearm, or native memory writes.
    inactive_helpers || exit $?
    # A claimed async launch can precede its running marker/process. Only a
    # completed attempt (including failure) has immutable diagnostic frames.
    [ ! -d claimed ] || [ -f done ] || exit 92
    $B mkdir maintenance || exit 92;;
 XLOCK)
    inactive || exit $?
    # Also shared with the upload-driven consumer. Never steal an existing
    # lock: it may be between validation and claiming its native transaction.
    # Normal transport failure runs XUNLOCK; ambiguous orphan locks require
    # explicit diagnosis, not a second writer.
    $B mkdir maintenance || exit 92;;
 XUNLOCK) $B rmdir maintenance || exit 92;;
 XENABLE)
    [ -d maintenance ] && idle || exit 95
    # Explicit operator action after correcting the optional consumer/renderer.
    # Does not start upload/display or steal an in-flight upload's request.
    U=/setting/a7c-uploader/ram
    $B grep -q "^a7c-upload-ram $U tmpfs " /proc/mounts &&
    [ ! -e "$U/display.active" ] || exit 92
    $B rm -f "$U/display.disabled" || exit 98
    echo upload_display=enabled > update-result;;
 XIDLE) [ -d maintenance ] && idle || exit 95;;
 XCOMMIT)
    [ -d maintenance ] && idle || exit 95
    spec=$2;role=${spec%%:*};rest=${spec#*:};size=${rest%%:*};hash=${rest#*:}
    role_path "$role" || exit 64
    [ "$($B wc -c < incoming)" -eq "$size" ] || exit 96
    actual=$($B sha256sum incoming);[ "${actual%% *}" = "$hash" ] || exit 96
    validate incoming || exit $?
    $B cp "$target" "$target.previous.next" && $B chmod 700 "$target.previous.next" &&
    $B mv "$target.previous.next" "$target.previous" && $B chmod 700 incoming &&
    $B mv incoming "$target" || exit 98
    printf '%s %s\n' "$target" "$hash" > update-result;;
 XROLLBACK)
    [ -d maintenance ] && idle || exit 95
    role_path "$2" || exit 64
    [ -f "$target.previous" ] || exit 96
    validate "$target.previous" || exit $?
    $B cp "$target.previous" incoming && $B chmod 700 incoming && $B mv incoming "$target" || exit 98
    echo "rollback=$target" > update-result;;
 XREARM)
    [ -d maintenance ] && idle || exit 95
    # Drop evidence only after the operator explicitly requests another run.
    # No native writes, no timer creation and no automatic display.
    if $B grep -q 'first=0 ' manage-inspect.log; then mode=--once-shooting-idle; else mode=--once-shooting; fi
    for n in claimed blink-worker.started; do [ ! -d "$n" ] || $B rmdir "$n" || exit 98; done
    $B rm -f cancel done prewrite-abort blink-stop blink-history overlay.log inspect-before.log inspect-after.log dds-first.raw dds-before.raw dds-during.raw dds-late.raw dds-after.raw shooting.raw shooting.rle || exit 98
    printf '%s\n' "$mode" > native.mode
    echo stage=waiting > status;;
 XSCREEN)
    [ -d maintenance ] && idle || exit 95
    $B rm -f shooting.raw shooting.rle || exit 98
    ./capture --capture-physical "$p" "$a" > screen.log 2>&1 || exit 96
    [ "$($B wc -c < shooting.raw)" -eq 614400 ] || exit 96;;
 *) exit 64;;
esac
