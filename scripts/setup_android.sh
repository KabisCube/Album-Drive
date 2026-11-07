set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
cache="$HOME/.cache/album-drive-android"
qt_version=6.11.3
p4a_revision=3762c88c56e3443efb8eba2a02a2604b680240fd
mkdir -p "$cache/downloads"
python3 -m pip install --target "$cache/uv" uv
if [ ! -x "$cache/venv/bin/python" ]; then
    PYTHONPATH="$cache/uv" python3 -m uv venv --seed --python 3.11 "$cache/venv"
fi
"$cache/venv/bin/python" -m pip install -r "$root/packaging/android/requirements-build.txt"
if [ ! -x "$cache/sdk/cmdline-tools/latest/bin/sdkmanager" ]; then
    curl --retry 3 -fL https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip -o "$cache/downloads/commandlinetools.zip"
    mkdir -p "$cache/sdk/cmdline-tools"
    unzip -q "$cache/downloads/commandlinetools.zip" -d "$cache/sdk/cmdline-tools"
    mv "$cache/sdk/cmdline-tools/cmdline-tools" "$cache/sdk/cmdline-tools/latest"
fi
"$cache/venv/bin/python" - "$cache/sdk" <<'PY'
from pathlib import Path
import subprocess
import sys
sdk = Path(sys.argv[1])
subprocess.run([str(sdk / 'cmdline-tools/latest/bin/sdkmanager'), f'--sdk_root={sdk}', '--licenses'],
               input=b'y\n' * 200, check=True)
PY
"$cache/sdk/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$cache/sdk" 'platform-tools' 'platforms;android-35' 'build-tools;35.0.0' 'ndk;26.1.10909125'
for package in pyside6 shiboken6; do
    wheel="$package-$qt_version-$qt_version-cp311-cp311-android_aarch64.whl"
    if [ ! -f "$cache/downloads/$wheel" ]; then
        curl --retry 3 -fL "https://download.qt.io/official_releases/QtForPython/$package/$wheel" -o "$cache/downloads/$wheel.part"
        mv "$cache/downloads/$wheel.part" "$cache/downloads/$wheel"
    fi
done
if [ ! -d "$cache/p4a/.git" ]; then
    git init "$cache/p4a"
    git -C "$cache/p4a" remote add origin https://github.com/kivy/python-for-android.git
    git -C "$cache/p4a" fetch --depth 1 origin "$p4a_revision"
    git -C "$cache/p4a" checkout --detach FETCH_HEAD
fi
printf 'Android build environment ready: %s\n' "$cache"
