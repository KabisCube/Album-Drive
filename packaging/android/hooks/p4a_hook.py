"""Adds manifest entries python-for-android's template has no option for, and swaps in the
patched Qt audio device manager from android/qt so Bluetooth media uses A2DP instead of SCO."""

from pathlib import Path
from zipfile import ZipFile

SERVICE = ('<service android:name="org.albumdrive.PlaybackService" android:exported="false" '
           'android:foregroundServiceType="mediaPlayback" android:stopWithTask="true" />')
KEEP_RUNNING = '<meta-data android:name="android.app.background_running" android:value="true" />'
PATCHED_CLASS = 'org/qtproject/qt/android/multimedia/QtAudioDeviceManager'


def drop_patched_classes(jar):
    with ZipFile(jar) as source:
        entries = [(info, source.read(info)) for info in source.infolist()]
    if not any(info.filename.startswith(PATCHED_CLASS) for info, _ in entries):
        return
    temporary = jar.with_suffix('.tmp')
    with ZipFile(temporary, 'w') as target:
        for info, data in entries:
            if not info.filename.startswith(PATCHED_CLASS):
                target.writestr(info, data)
    temporary.replace(jar)


def before_apk_assemble(toolchain):
    dist = Path(toolchain._dist.dist_dir)
    manifest = dist / 'src/main/AndroidManifest.xml'
    text = manifest.read_text(encoding='utf-8')
    if SERVICE not in text:
        text = text.replace('</activity>', KEEP_RUNNING + '</activity>', 1)
        text = text.replace('</application>', SERVICE + '</application>', 1)
        manifest.write_text(text, encoding='utf-8')
    jars = list((dist / 'src/main/libs').glob('Qt6AndroidMultimedia.jar'))
    if not jars:
        raise RuntimeError('Qt6AndroidMultimedia.jar was not found, so the Bluetooth audio fix cannot be applied')
    for jar in jars:
        drop_patched_classes(jar)
