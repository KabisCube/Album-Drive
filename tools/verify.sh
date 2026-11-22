#!/usr/bin/env bash
# Checks the Linux build the way GitHub does. Add --android to also test on a USB phone.
script="$(realpath "$0")"
cd "$(dirname "$script")/.."
source tools/linux-env.sh "$script" "$@"

python3 scripts/verify.py "$@"
result=$?
pause
exit $result
