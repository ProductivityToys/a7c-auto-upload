#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then
    command -v python3 >/dev/null || { echo 'Please install Python 3.11+ first.' >&2; exit 1; }
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || { echo 'Python 3.11+ is required.' >&2; exit 1; }
    python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import usb, Cryptodome, libusb_package' >/dev/null 2>&1; then
    .venv/bin/python -m pip install -r requirements.txt
fi
if [ "$#" -eq 0 ]; then
    set -- menu
fi
case "$(uname -s):${1}:$(id -u)" in
    Darwin:detect:*|Darwin:test-ftp:*|Darwin:--help:*|Darwin:*:0) ;;
    Darwin:*)
        if [ "$1" = menu ]; then
            exec sudo .venv/bin/python -m a7c_installer.interactive
        fi
        exec sudo .venv/bin/python install.py "$@"
        ;;
esac
if [ "$1" = menu ]; then
    exec .venv/bin/python -m a7c_installer.interactive
fi
exec .venv/bin/python install.py "$@"
