#!/usr/bin/env bash
# Adds Album Drive to the app menu with its icon, for the folder this script is in.
# Run it again after moving the folder. uninstall.sh removes it again.
set -euo pipefail

# Started from a file manager there is no terminal, so reopen in one to show what happens.
# Without any terminal program it still runs, just without a window.
if [ ! -t 1 ] && [ -z "${ALBUM_DRIVE_IN_TERMINAL:-}" ]; then
	export ALBUM_DRIVE_IN_TERMINAL=1
	for terminal in konsole gnome-terminal kgx ptyxis xfce4-terminal kitty alacritty foot xterm x-terminal-emulator; do
		command -v "$terminal" >/dev/null || continue
		case "$terminal" in
			gnome-terminal|kgx|ptyxis) exec "$terminal" -- bash "$(realpath "$0")" ;;
			*) exec "$terminal" -e bash "$(realpath "$0")" ;;
		esac
	done
fi
# The marker only stops the reopened script from reopening again. Clear it so programs
# started from here don't inherit it.
opened_terminal="${ALBUM_DRIVE_IN_TERMINAL:-}"
unset ALBUM_DRIVE_IN_TERMINAL
# In a terminal opened just for this, wait before it closes, also after an error
if [ -n "$opened_terminal" ] && [ -t 0 ]; then
	trap 'echo; read -rp "Press Enter to close..."' EXIT
fi

folder="$(dirname "$(realpath "$0")")"
program="$folder/AlbumDrive"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"

if [ ! -x "$program" ]; then
	echo "AlbumDrive was not found next to this script, in $folder"
	exit 1
fi

# The app writes its own menu entry and icon, so they always match the version in this folder.
# "offscreen" lets it do that without opening a window.
QT_QPA_PLATFORM=offscreen "$program" --install-desktop-entry

# Ask the desktop to notice the new entry now. Most desktops also do this on their own.
update-desktop-database "$data_home/applications" >/dev/null 2>&1 || true
touch "$data_home/icons/hicolor" 2>/dev/null || true

echo "Album Drive is now in the app menu."
echo "It runs $program"
