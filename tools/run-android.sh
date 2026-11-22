#!/usr/bin/env bash
# Builds the Android APK, installs it on the phone connected by USB, and opens it.
# Use "tools/run-android.sh --skip-build" to reinstall the last build.
# run-android-release.sh calls this with --release for a signed release build.
script="$(realpath "$0")"
cd "$(dirname "$script")/.."
source tools/linux-env.sh "$script" "$@"

PACKAGE="org.albumdrive.albumdrive"
# Drawing size in percent: 100, or 30 to 90 in steps of 5. Lower scrolls smoother but looks softer.
RENDER_SCALE=60
RELEASE=""
SKIP_BUILD=""
for argument in "$@"; do
	case "$argument" in
		--release) RELEASE=1 ;;
		--skip-build) SKIP_BUILD=1 ;;
	esac
done
if [ -n "$RELEASE" ]; then
	APK="dist/AlbumDrive-android-arm64.apk"
else
	APK="dist/AlbumDrive-android-arm64-debug.apk"
fi

fail() {
	echo
	echo "$1"
	pause
	exit 1
}

find_adb
[ -n "$ADB" ] || download_adb
[ -n "$ADB" ] || fail "Could not find or download adb. Install your distribution's android-tools package, then try again."

# Check the phone first so a long build does not end with nowhere to install.
find_phone
if [ -z "$ANDROID_SERIAL" ]; then
	[ -n "$UNAUTHORIZED" ] && fail "The phone has not allowed this PC yet. Unlock it, accept the USB debugging prompt, and try again."
	fail "No phone found. Connect it by USB, turn on USB debugging, and set USB mode to file transfer.
If it still is not found, your system may need the android-udev package so it can reach USB phones."
fi
echo "Using phone $ANDROID_SERIAL"

if [ -z "$SKIP_BUILD" ]; then
	ensure_android_setup || fail "Android setup failed. See the error above and the prerequisites in README.md."
	python3 scripts/build_android.py ${RELEASE:+--release} \
		|| fail "Android build failed. See the error above and the prerequisites in README.md."
fi

[ -f "$APK" ] || fail "$APK does not exist yet. Run this script without --skip-build first."
echo
echo "Installing on the phone..."
install_log="$("$ADB" install -r "$APK" 2>&1)"
install_result=$?
echo "$install_log"
if [[ "$install_log" == *INSTALL_FAILED_UPDATE_INCOMPATIBLE* ]]; then
	fail "The phone has a version of Album Drive signed with a different key, such as a debug or release build.
Android cannot update it in place. Uninstall Album Drive from the phone and run this again.
Uninstalling also removes the app's settings on the phone."
fi
[ "$install_result" = 0 ] || fail "Install failed. See the error above."

if [ -z "$RELEASE" ]; then
	# Android only allows this per-app override on debug builds, set from a computer.
	"$ADB" shell am compat reset-all "$PACKAGE" >/dev/null 2>&1
	if [ "$RENDER_SCALE" != 100 ]; then
		"$ADB" shell am compat enable DOWNSCALED "$PACKAGE" >/dev/null 2>&1
		"$ADB" shell am compat enable "DOWNSCALE_$RENDER_SCALE" "$PACKAGE" >/dev/null 2>&1
	fi
fi
"$ADB" shell monkey -p "$PACKAGE" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 \
	|| fail "Album Drive was installed but did not open. Start it from the phone."

echo
echo "Album Drive is running on the phone."
pause
