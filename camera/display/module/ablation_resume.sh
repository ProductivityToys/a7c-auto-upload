#!/bin/ash
# Explicit operator action after read-only diagnosis. Restart unchanged uploader
# only when no old worker, supervisor, copy FIFO or native-transfer lock remains.
B=/bin/busybox
D=/setting/a7c-debug/ram/maint
U=/setting/a7c-uploader/ram
[ ! -e /setting/a7c-display/enabled ] || exit 92
alive() {
 [ -f "$U/worker.pid" ] || return 1
 read worker < "$U/worker.pid" || return 1
 case "$worker" in ''|1|*[!0-9]*) return 1;; esac
 kill -0 "$worker" 2>/dev/null
}
if alive; then echo "ABLATION_UPLOADER_ALIVE pid=$worker"; exit 0; fi
for n in lock supervisor.lock plain.arm source.fifo network.fifo display.active; do
 [ ! -e "$U/$n" ] || { echo "ABLATION_UPLOADER_BUSY file=$n"; exit 94; }
done
echo ABLATION_UPLOADER_RESUME
/bin/ash /setting/a7c-uploader/supervisor.sh --start </dev/null > "$D/uploader-resume.log" 2>&1 &
supervisor=$!
n=0
while [ "$n" -lt 5 ]; do
 if alive; then echo "ABLATION_UPLOADER_ALIVE pid=$worker"; exit 0; fi
 kill -0 "$supervisor" 2>/dev/null || exit 94
 $B sleep 1
 n=$((n+1))
done
exit 94
