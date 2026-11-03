#!/bin/ash
# Update only external maintenance code, even after a completed trial.
# Loaded DSO, claim, evidence, uploader and persistent startup are untouched.
B=/bin/busybox
D=/setting/a7c-debug/ram/maint
idle() {
 [ ! -e "$D/trial.claim" ] ||
 $B grep -Eq '^(ABLATION_END rc=[0-9]+ phase=--[a-z-]+|LIFECYCLE_REVOKED)$' "$D/trial.state"
}
case "$1" in
 XREADLOCK) $B mkdir "$D/transfer.lock";;
 XLOCK) idle && $B mkdir "$D/transfer.lock";;
 XUNLOCK) $B rmdir "$D/transfer.lock";;
 XIDLE) idle;;
 XCOMMIT)
  idle && [ -d "$D/transfer.lock" ] || exit 92
  case "$2" in
   action:*) target=action.sh; /bin/ash -n "$D/incoming" || exit 96;;
   capture:*) target=probe;;
   *) exit 64;;
  esac
  [ ! -L "$D/$target" ] || exit 92
  $B chmod 500 "$D/incoming" && $B mv "$D/incoming" "$D/$target";;
 *) exit 64;;
esac
