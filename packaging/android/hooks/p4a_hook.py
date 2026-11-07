"""Adds the manifest entries python-for-android's template has no option for."""

from pathlib import Path

SERVICE = ('<service android:name="org.albumdrive.PlaybackService" android:exported="false" '
           'android:foregroundServiceType="mediaPlayback" android:stopWithTask="true" />')
KEEP_RUNNING = '<meta-data android:name="android.app.background_running" android:value="true" />'


def before_apk_assemble(toolchain):
    manifest = Path(toolchain._dist.dist_dir) / 'src/main/AndroidManifest.xml'
    text = manifest.read_text(encoding='utf-8')
    if SERVICE not in text:
        text = text.replace('</activity>', KEEP_RUNNING + '</activity>', 1)
        text = text.replace('</application>', SERVICE + '</application>', 1)
        manifest.write_text(text, encoding='utf-8')
