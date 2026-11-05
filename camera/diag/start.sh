#!/bin/ash
# Opt-in Wi-Fi diagnostics. Started once per boot by the uploader supervisor
# (or by the installer after pairing). Runs from the uploader's private tmpfs,
# never from /tmp_network or NAND; exits if the pairing is removed.
B=/bin/busybox
P=/setting/a7c-diag
D=/setting/a7c-uploader/ram/diag
umask 077
trap '' HUP
[ -f "$P/enabled" ] && [ -f "$P/token" ] || exit 0
$B grep -q '^a7c-upload-ram /setting/a7c-uploader/ram tmpfs ' /proc/mounts || exit 90
[ -d "$D" ] || $B mkdir "$D" || exit 90
$B mkdir "$D/lock" 2>/dev/null || exit 0
release() { $B rmdir "$D/lock"; }
expected=$($B cat "$P/listener.sha256" 2>/dev/null)
actual=$($B sha256sum "$P/listener"); actual=${actual%% *}
[ "${#actual}" = 64 ] && [ "$expected" = "$actual" ] || { release; exit 91; }
$B rm -f "$D/stop" "$D/listener.next"
$B cp "$P/listener" "$D/listener.next" && $B chmod 700 "$D/listener.next" &&
$B mv "$D/listener.next" "$D/listener" || { release; exit 90; }
cd / || { release; exit 90; }
exec 0</dev/null
"$D/listener" > "$D/listener.log" 2>&1
rc=$?
echo "DIAG_LISTENER_EXIT rc=$rc" >> "$D/listener.log"
release
exit "$rc"
