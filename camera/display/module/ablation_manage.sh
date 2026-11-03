#!/bin/ash
# Temporary package only. Update trial/probe before its one-shot claim;
# never replace a mapped module, production uploader or persistent startup.
B=/bin/busybox
D=/setting/a7c-debug/ram/maint
case "$1" in
 XREADLOCK) $B mkdir "$D/transfer.lock";;
 XLOCK) [ ! -e "$D/trial.claim" ] && $B mkdir "$D/transfer.lock";;
 XUNLOCK) $B rmdir "$D/transfer.lock";;
 XIDLE) [ ! -e "$D/trial.claim" ];;
 XCOMMIT)
  [ ! -e "$D/trial.claim" ] && [ -d "$D/transfer.lock" ] || exit 92
  case "$2" in
   action:*) target=trial.sh; /bin/ash -n "$D/incoming" || exit 96;;
   capture:*) target=probe;;
   *) exit 64;;
  esac
  [ ! -L "$D/$target" ] || exit 92
  $B chmod 500 "$D/incoming" && $B mv "$D/incoming" "$D/$target";;
 *) exit 64;;
esac
