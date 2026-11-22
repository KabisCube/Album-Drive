# Shared setup for the Linux launcher scripts. Source it at the top of a script with:
#   source tools/linux-env.sh "<absolute path of the script>" "$@"

# When started from a file manager there is no terminal, so reopen the script in one.
if [ ! -t 1 ] && [ -z "${ALBUM_DRIVE_IN_TERMINAL:-}" ]; then
	export ALBUM_DRIVE_IN_TERMINAL=1
	script="$1"; shift
	for terminal in konsole gnome-terminal kgx ptyxis xfce4-terminal kitty alacritty foot xterm x-terminal-emulator; do
		command -v "$terminal" >/dev/null || continue
		case "$terminal" in
			gnome-terminal|kgx|ptyxis) exec "$terminal" -- bash "$script" "$@" ;;
			*) exec "$terminal" -e bash "$script" "$@" ;;
		esac
	done
	notify-send "Album Drive" "No terminal found to run $(basename "$script")" 2>/dev/null
	exit 1
fi
# The marker only stops the reopened script from reopening again. Clear it so programs
# started from here (like the app itself) don't inherit it.
unset ALBUM_DRIVE_IN_TERMINAL

# Waits for Enter when someone is at the keyboard. Always "succeeds", so a script that
# ends with pause keeps the exit code of what it did before.
pause() {
	[ -t 0 ] && read -rp "Press Enter to close..."
	return 0
}

# True if the Python at $1 really runs. A venv copied from Windows can hold an empty
# 0-byte "python" file, which the shell runs as an empty script that "succeeds".
python_works() {
	[ "$("$1" -c 'print("ok")' 2>/dev/null)" = "ok" ]
}

# Finds adb: on PATH, in the Android SDK, or in the tools the Android build downloads.
find_adb() {
	ADB="$(command -v adb || true)"
	for candidate in "${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb" \
			"$HOME/.cache/album-drive-android/sdk/platform-tools/adb" \
			"$HOME/.cache/album-drive/platform-tools/adb"; do
		[ -z "$ADB" ] && [ -x "$candidate" ] && ADB="$candidate"
	done
	return 0
}

download_adb() {
	echo "Downloading Android platform tools from Google. This only happens once."
	local tools="$HOME/.cache/album-drive"
	mkdir -p "$tools"
	curl -fsSL -o "$tools/platform-tools.zip" \
		https://dl.google.com/android/repository/platform-tools-latest-linux.zip || return 0
	unzip -qo "$tools/platform-tools.zip" -d "$tools" || return 0
	rm -f "$tools/platform-tools.zip"
	find_adb
}

# Sets ANDROID_SERIAL to the first ready phone, and UNAUTHORIZED if one is waiting for approval.
find_phone() {
	ANDROID_SERIAL=""
	UNAUTHORIZED=""
	"$ADB" start-server >/dev/null 2>&1
	while read -r serial state; do
		[ "$state" = "device" ] && [ -z "$ANDROID_SERIAL" ] && ANDROID_SERIAL="$serial"
		[ "$state" = "unauthorized" ] && UNAUTHORIZED=1
	done < <("$ADB" devices | tail -n +2)
	export ANDROID_SERIAL
}

# The Android build needs its SDK, NDK and Python set up once in ~/.cache/album-drive-android.
ensure_android_setup() {
	if [ ! -x "$HOME/.cache/album-drive-android/venv/bin/python" ]; then
		echo "First Android build: setting up the SDK and tools. This takes a while."
		bash scripts/setup_android.sh
	fi
}
