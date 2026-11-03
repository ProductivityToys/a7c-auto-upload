#!/bin/sh
a7c_entry_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$a7c_entry_dir/start.sh" "$@"
a7c_status=$?
if [ "$a7c_status" -ne 0 ]; then
    printf '\n启动未完成，请查看上方提示。按回车关闭。\n'
    read -r a7c_reply
fi
exit "$a7c_status"
