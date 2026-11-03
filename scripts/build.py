"""Build a self-contained executable and a portable archive on Windows/Linux."""

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
from zipfile import ZIP_DEFLATED, ZipFile


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
    shutil.copy2(root / 'README.txt', release / 'README.txt')
    themes = release / 'themes'
    themes.mkdir(exist_ok=True)
    if not (themes / 'settings.ini').exists():
        (themes / 'settings.ini').write_text('; Album Drive preferences and saved themes live in this folder.\n[General]\n', encoding='utf-8')
    if sys.platform == 'linux':
        os.chmod(release / 'AlbumDrive', 0o755)
    contents = (release / binary, release / 'README.txt', release / 'themes')
    if sys.platform == 'win32':
        archive = root / 'dist' / f'{name}.zip'
        with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
            for item in contents:
                paths = sorted(item.rglob('*')) if item.is_dir() else (item,)
                for path in paths:
                    if path.is_file():
                        package.write(path, Path(name) / path.relative_to(release))
    else:
        archive = root / 'dist' / f'{name}.tar.gz'
        with tarfile.open(archive, 'w:gz') as package:
            for item in contents:
                package.add(item, arcname=str(Path(name) / item.relative_to(release)))
    print(f'Executable: {release / binary}\nArchive: {archive}')


if __name__ == '__main__':
    main()
