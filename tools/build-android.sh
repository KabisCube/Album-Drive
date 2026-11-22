#!/usr/bin/env bash
# Builds the Android debug APK into dist/AlbumDrive-android-arm64-debug.apk.
script="$(realpath "$0")"
cd "$(dirname "$script")/.."
source tools/linux-env.sh "$script" "$@"

if ! ensure_android_setup || ! python3 scripts/build_android.py "$@"; then
	echo
	echo "Android build failed. See the error above and the prerequisites in README.md."
	pause
	exit 1
fi

echo
echo "Android APK ready in the dist folder."
pause
