#!/usr/bin/env sh
set -eu
cd -- "$(dirname -- "$0")"
# Check that Python really runs: a venv copied from Windows can hold an empty 0-byte "python"
# file, which the shell would run as an empty script that silently "succeeds".
for venv in .venv-linux .venv; do
	if [ "$("$venv/bin/python" -c 'print("ok")' 2>/dev/null || true)" = "ok" ]; then
		exec "$venv/bin/python" src/main.py
	fi
done
echo 'First run: run tools/build-linux.sh once, or follow the setup instructions in BUILDING.md.' >&2
exit 1
