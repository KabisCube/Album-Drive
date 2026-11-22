#!/usr/bin/env bash
# Removes Album Drive from the app menu again. The app folder, your themes and settings are not touched.
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

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"

# The same names the app uses in install_desktop_entry (src/app_identity.py)
rm -f "$data_home/applications/album-drive.desktop" "$data_home/icons/hicolor/scalable/apps/album-drive.svg"
update-desktop-database "$data_home/applications" >/dev/null 2>&1 || true

echo "Album Drive was removed from the app menu."
