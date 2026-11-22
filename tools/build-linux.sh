#!/usr/bin/env bash
# Builds the standalone Linux app into dist/AlbumDrive-linux-x86_64, plus a .tar.gz of it.
script="$(realpath "$0")"
cd "$(dirname "$script")/.."
source tools/linux-env.sh "$script" "$@"

VENV=".venv-linux"
PYTHON="$VENV/bin/python"

if ! python_works "$PYTHON"; then
	if [ -e "$VENV" ]; then
		echo "$VENV does not work on this computer (it may have been copied from Windows). Recreating it."
		rm -rf -- "$VENV"
	fi
	if ! python3 -m venv "$VENV"; then
		echo
		echo "Could not create $VENV. Install Python 3 with its venv module, then try again."
		pause
		exit 1
	fi
fi

if ! "$PYTHON" -m pip install -r requirements/build.txt || ! "$PYTHON" scripts/build.py; then
	echo
	echo "Linux build failed. See the error above."
	pause
	exit 1
fi

echo
echo "Linux build ready in dist/AlbumDrive-linux-x86_64"
echo "Run install.sh in that folder to add Album Drive to the app menu with its icon."
command -v xdg-open >/dev/null && xdg-open dist/AlbumDrive-linux-x86_64 >/dev/null 2>&1 &
pause
