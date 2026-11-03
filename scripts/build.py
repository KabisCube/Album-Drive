"""Build a self-contained executable and a portable archive on Windows/Linux."""

import os
from io import BytesIO
from importlib.metadata import distribution, version
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from zipfile import ZIP_DEFLATED, ZipFile


def copy_license_bundle(root, release):
    target = release / 'licenses'
    shutil.copytree(root / 'licenses', target, dirs_exist_ok=True)
    shutil.copy2(root / 'LICENSE', target / 'AlbumDrive-GPL-3.0.txt')
    runtime = target / 'runtime'
    runtime.mkdir(exist_ok=True)
    for package, filename, destination in (
            ('mutagen', 'COPYING', 'Mutagen-COPYING.txt'),
            ('Pillow', 'LICENSE', 'Pillow-LICENSE.txt'),
            ('pyinstaller', 'COPYING.txt', 'PyInstaller-COPYING.txt')):
        files = distribution(package).files or ()
        license_file = next((item for item in files if item.name == filename
                             and ('license' in str(item).lower() or 'copying' in str(item).lower())), None)
        if license_file is not None:
            shutil.copy2(distribution(package).locate_file(license_file), runtime / destination)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license, runtime / 'Python-LICENSE.txt')
    qt_version = version('PySide6')
    (runtime / 'Qt-LICENSE-INFO.txt').write_text(
        f'PySide6 {qt_version} and Qt are distributed under LGPLv3, GPLv2, or GPLv3 terms. '
        'This GPLv3 project uses compatible GPLv3 terms. Qt Multimedia includes the FFmpeg '
        'backend under LGPLv2.1-or-later and other permissive licenses. Exact third-party '
        'attributions and license terms: https://doc.qt.io/qt-6/licenses-used-in-qt.html '
        'Qt licensing: https://doc.qt.io/qt-6/licensing.html\n', encoding='utf-8')


def main():
    if sys.platform not in ('win32', 'linux'):
        raise SystemExit('Build on Windows or Linux to produce its native executable.')
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, str(root / 'scripts' / 'make_icons.py')], cwd=root, check=True)
    subprocess.run([sys.executable, str(root / 'scripts' / 'make_button_sounds.py')], cwd=root, check=True)
    native = root / 'build' / 'native'
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(native), str(root / 'packaging' / 'AlbumDrive.spec')], cwd=root, check=True)
    system = 'windows' if sys.platform == 'win32' else 'linux'
    architecture = platform.machine().lower()
    architecture = {'amd64': 'x86_64', 'aarch64': 'arm64'}.get(architecture, architecture)
    name = f'AlbumDrive-{system}-{architecture}'
    release = root / 'dist' / name
    release.mkdir(parents=True, exist_ok=True)
    binary = 'AlbumDrive.exe' if sys.platform == 'win32' else 'AlbumDrive'
    try:
        shutil.copy2(native / binary, release / binary)
    except PermissionError:
        # Windows locks a running executable. Preserve that app and its themes
        # and produce a separate, runnable update instead of interrupting it.
        previous = release
        number = 1
        while (root / 'dist' / f'{name}-update-{number}').exists():
            number += 1
        name = f'{name}-update-{number}'
        release = root / 'dist' / name
        release.mkdir()
        if (previous / 'themes').is_dir():
            shutil.copytree(previous / 'themes', release / 'themes')
        shutil.copy2(native / binary, release / binary)
        print('Existing executable is locked; the update has its own folder and a copy of your themes.')
    shutil.copy2(root / 'README.md', release / 'README.md')
    shutil.copy2(root / 'LICENSE', release / 'LICENSE')
    copy_license_bundle(root, release)
    themes = release / 'themes'
    themes.mkdir(exist_ok=True)
    default_settings = '; Album Drive preferences and saved themes live in this folder.\n[General]\n'
    if not (themes / 'settings.ini').exists():
        (themes / 'settings.ini').write_text(default_settings, encoding='utf-8')
    if sys.platform == 'linux':
        os.chmod(release / 'AlbumDrive', 0o755)
    contents = [release / binary, release / 'README.md', release / 'LICENSE']
    contents.extend(sorted((release / 'licenses').rglob('*')))
    contents = [item for item in contents if item.is_file()]
    if sys.platform == 'win32':
        archive = root / 'dist' / f'{name}.zip'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
            for item in contents:
                package.write(item, Path(name) / item.relative_to(release))
            package.writestr(f'{name}/themes/settings.ini', default_settings)
    else:
        archive = root / 'dist' / f'{name}.tar.gz'
        with tarfile.open(archive, 'w:gz') as package:
            for item in contents:
                package.add(item, arcname=str(Path(name) / item.relative_to(release)))
            preferences = default_settings.encode('utf-8')
            entry = tarfile.TarInfo(f'{name}/themes/settings.ini')
            entry.size = len(preferences)
            entry.mode = 0o644
            package.addfile(entry, BytesIO(preferences))
    print(f'Executable: {release / binary}\nArchive: {archive}')


if __name__ == '__main__':
    main()
