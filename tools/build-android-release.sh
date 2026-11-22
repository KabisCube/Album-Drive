#!/usr/bin/env bash
# Builds a signed release APK. The first run creates a signing key in ~/.config/album-drive.
script="$(realpath "$0")"
cd "$(dirname "$script")/.."
source tools/linux-env.sh "$script" "$@"

if ! ensure_android_setup || ! python3 scripts/build_android.py --release; then
	echo
	echo "Android build failed. See the error above and the prerequisites in README.md."
	pause
	exit 1
fi

echo
echo "Android release APK ready in dist/AlbumDrive-android-arm64.apk"
echo "Back up ~/.config/album-drive. Updates must be signed with the same key."
pause
