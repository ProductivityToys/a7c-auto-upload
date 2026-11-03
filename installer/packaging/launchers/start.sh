#!/bin/sh
set -eu
a7c_entry_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec sh "$a7c_entry_dir/app/install.sh" "$@"
