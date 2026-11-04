#!/usr/bin/env sh
set -eu
cd -- "$(dirname -- "$0")"
if [ -x .venv-linux/bin/python ]; then
    exec .venv-linux/bin/python src/main.py
fi
if [ ! -x .venv/bin/python ]; then
    echo 'First run: follow the setup instructions in README.md.' >&2
    exit 1
fi
exec .venv/bin/python src/main.py
