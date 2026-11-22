#!/usr/bin/env bash
# Builds a signed release APK, installs it on the phone connected by USB, and opens it.
# Use "tools/run-android-release.sh --skip-build" to reinstall the last release build.
exec bash "$(dirname "$(realpath "$0")")/run-android.sh" --release "$@"
