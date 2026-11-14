import argparse
from configparser import ConfigParser
import os
from pathlib import Path
import secrets
import shutil
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


QT_VERSION = '6.11.3'
P4A_REVISION = '3762c88c56e3443efb8eba2a02a2604b680240fd'


def order_qt_libraries(arguments):
    priority = ('Core', 'Concurrent', 'Network', 'Gui', 'OpenGL', 'Widgets', 'OpenGLWidgets',
                'Svg', 'Multimedia', 'MultimediaWidgets', 'Qml', 'Quick', 'QuickWidgets')
    tokens = shlex.split(arguments)
    for index, token in enumerate(tokens):
        if token.startswith('--qt-libs='):
            modules = token.partition('=')[2].split(',')
            modules.sort(key=lambda module: (priority.index(module) if module in priority else len(priority), module))
            tokens[index] = '--qt-libs=' + ','.join(modules)
    return shlex.join(tokens)


def stage_sources(root, stage):
    stage.mkdir(parents=True, exist_ok=True)
    for name in ('src', 'assets', 'licenses'):
        shutil.copytree(root / name, stage / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(root / 'LICENSE', stage / 'LICENSE.txt')
    shutil.copy2(root / 'README.md', stage / 'README.md')
    shutil.copytree(root / 'packaging/android', stage / 'android', dirs_exist_ok=True)
    (stage / 'main.py').write_text(
        "from pathlib import Path\nimport runpy\nimport sys\n\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))\n"
        "runpy.run_module('main', run_name='__main__')\n", encoding='utf-8')


def configure_deployment(root, stage, cache, python, sdk, ndk, source):
    template = subprocess.check_output([
        str(python), '-c',
        'from pathlib import Path; import PySide6; '
        'print(Path(PySide6.__file__).parent / "scripts/deploy_lib/default.spec")'], text=True).strip()
    subprocess.run([str(python), '-m', 'pip', 'install', '-r',
                    str(Path(template).parents[1] / 'requirements-android.txt')], check=True)
    config = ConfigParser(interpolation=None)
    config.read(template)
    values = {
        'app': dict(title='AlbumDrive', project_dir=str(stage), input_file=str(stage / 'main.py'),
                    exec_directory=str(root / 'dist'), icon=str(stage / 'assets/icons/album-drive.png')),
        'qt': dict(modules='Core,Gui,Widgets,Network,Multimedia,Svg'),
        'android': dict(wheel_pyside=str(cache / 'downloads' / f'pyside6-{QT_VERSION}-{QT_VERSION}-cp311-cp311-android_aarch64.whl'),
                        wheel_shiboken=str(cache / 'downloads' / f'shiboken6-{QT_VERSION}-{QT_VERSION}-cp311-cp311-android_aarch64.whl')),
        'buildozer': dict(mode='debug', ndk_path=str(ndk), sdk_path=str(sdk), arch='aarch64'),
    }
    for section, entries in values.items():
        for key, value in entries.items():
            config.set(section, key, value)
    destination = stage / 'pysidedeploy.spec'
    with destination.open('w', encoding='utf-8') as output:
        config.write(output)
    buildozer = stage / 'buildozer.spec'
    if not buildozer.is_file() or not (stage / 'deployment/recipes/PySide6/__init__.py').is_file():
        subprocess.run([str(python.parent / 'pyside6-android-deploy'), '--config-file', str(destination),
                        '--ndk-path', str(ndk), '--sdk-path', str(sdk), '--extra-modules', 'Svg',
                        '--init', '--force', '--keep-deployment-files'], cwd=stage, check=True)
    if not buildozer.is_file():
        raise RuntimeError('Qt did not generate an Android build configuration')
    config = ConfigParser(interpolation=None)
    config.read(buildozer)
    recipes = stage / 'deployment/recipes/Pillow'
    shutil.copytree(cache / 'p4a/pythonforandroid/recipes/Pillow', recipes, dirs_exist_ok=True)
    shutil.copy2(root / 'packaging/android/recipes/Pillow/__init__.py', recipes / '__init__.py')
    entries = {
        'title': 'Album Drive', 'package.name': 'albumdrive', 'package.domain': 'org.albumdrive',
        'source.dir': str(source),
        'version': '0.1.0', 'source.include_exts': 'py,png,jpg,jpeg,webp,svg,ico,ttf,otf,wav,txt,json,ini,md',
        'source.exclude_dirs': 'android,deployment,.buildozer,.git',
        'requirements': 'python3,shiboken6,PySide6,sqlite3,pillow==11.3.0,mutagen==1.47.0',
        'orientation': 'landscape,portrait,landscape-reverse,portrait-reverse',
        'fullscreen': '0', 'android.api': '35', 'android.minapi': '28',
        'android.ndk_api': '28', 'android.accept_sdk_license': 'True',
        'android.ant_path': '/usr/share/ant',
        'android.permissions': 'READ_EXTERNAL_STORAGE,READ_MEDIA_AUDIO,MANAGE_EXTERNAL_STORAGE,INTERNET,'
                               'FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PLAYBACK,POST_NOTIFICATIONS,WAKE_LOCK',
        'android.entrypoint': 'org.albumdrive.AlbumDriveActivity', 'android.add_src': 'android',
        'android.release_artifact': 'apk',
        'p4a.source_dir': str(cache / 'p4a'),
        'p4a.hook': str(stage / 'android/hooks/p4a_hook.py'),
    }
    for key, value in entries.items():
        config.set('app', key, value)
    config.set('app', 'p4a.extra_args', order_qt_libraries(config.get('app', 'p4a.extra_args')))
    with buildozer.open('w', encoding='utf-8') as output:
        config.write(output)


def release_signing():
    folder = Path.home() / '.config/album-drive'
    keystore = folder / 'release.keystore'
    password_file = folder / 'release-key-password.txt'
    if keystore.is_file():
        password = password_file.read_text(encoding='utf-8').strip()
    else:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        password = secrets.token_urlsafe(32)
        password_file.touch(mode=0o600)
        password_file.write_text(password, encoding='utf-8')
    signing = dict(P4A_RELEASE_KEYSTORE=str(keystore), P4A_RELEASE_KEYALIAS='albumdrive',
                   P4A_RELEASE_KEYSTORE_PASSWD=password, P4A_RELEASE_KEYALIAS_PASSWD=password)
    if not keystore.is_file():
        subprocess.run(['keytool', '-genkeypair', '-keystore', str(keystore), '-storetype', 'PKCS12',
                        '-alias', 'albumdrive', '-keyalg', 'RSA', '-keysize', '4096', '-validity', '10000',
                        '-dname', 'CN=Album Drive', '-storepass:env', 'P4A_RELEASE_KEYSTORE_PASSWD'],
                       env={**os.environ, **signing}, check=True)
        print(f'Created the release signing key: {keystore}. Back it up: updates need the same key.')
    return signing


def verify_apk(path):
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        if 'AndroidManifest.xml' not in names or 'classes.dex' not in names:
            raise RuntimeError('The Android package is missing its manifest or Java classes')
        libraries = [name for name in names if name.startswith('lib/arm64-v8a/')]
        for module in ('Qt6Core', 'Qt6Widgets', 'Qt6Multimedia', 'python3.11'):
            if not any(module in name for name in libraries):
                raise RuntimeError(f'The Android package is missing {module}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=Path.home() / '.cache/album-drive-android')
    parser.add_argument('--stage-only', action='store_true')
    parser.add_argument('--release', action='store_true')
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if sys.platform == 'win32':
        # Forward slashes: wsl drops backslashes when started from cmd or PowerShell.
        script = subprocess.check_output(['wsl', '--', 'wslpath', '-a', Path(__file__).resolve().as_posix()],
                                         text=True).strip()
        return subprocess.run(['wsl', '--', 'python3', script, *sys.argv[1:]], check=True).returncode
    if sys.platform != 'linux':
        raise SystemExit('Build the Android APK on Linux or Windows with WSL.')
    cache = arguments.cache.resolve()
    stage = cache / 'app'
    stage_sources(root, stage)
    if arguments.stage_only:
        print(f'Staged Android sources: {stage}')
        return 0
    python = cache / 'venv/bin/python'
    sdk = Path(os.environ.get('ANDROID_SDK_ROOT', str(cache / 'sdk')))
    ndk = Path(os.environ.get('ANDROID_NDK_HOME', str(sdk / 'ndk/26.1.10909125')))
    for path in (python, sdk / 'cmdline-tools/latest/bin/sdkmanager', ndk / 'source.properties', cache / 'p4a'):
        if not path.exists():
            raise SystemExit(f'Android build prerequisite is missing: {path}')
    if not (sdk / 'tools').exists():
        (sdk / 'tools').symlink_to('cmdline-tools/latest', target_is_directory=True)
    revision = subprocess.check_output(['git', '-C', str(cache / 'p4a'), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != P4A_REVISION:
        raise SystemExit(f'Use python-for-android revision {P4A_REVISION} to match the Python 3.11 Android wheels.')
    (root / 'dist').mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment['PATH'] = os.pathsep.join((str(python.parent), environment['PATH']))
    environment['VIRTUAL_ENV'] = str(python.parent.parent)
    environment['ANDROIDSDK'] = str(sdk)
    environment['ANDROIDNDK'] = str(ndk)
    mode = 'release' if arguments.release else 'debug'
    if arguments.release:
        environment.update(release_signing())
    with TemporaryDirectory(prefix='album-drive-android-') as temporary:
        source = Path(temporary)
        stage_sources(root, source)
        configure_deployment(root, stage, cache, python, sdk, ndk, source)
        subprocess.run([str(python), '-m', 'buildozer', 'android', mode], cwd=stage,
                       env=environment, check=True)
    candidates = sorted((root / 'dist').glob(f'albumdrive*{mode}*.apk'), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise RuntimeError(f'The Android build did not produce a {mode} APK')
    apk = root / ('dist/AlbumDrive-android-arm64.apk' if arguments.release else 'dist/AlbumDrive-android-arm64-debug.apk')
    shutil.copy2(candidates[-1], apk)
    verify_apk(apk)
    subprocess.run([str(sdk / 'build-tools/35.0.0/apksigner'), 'verify', str(apk)], check=True)
    print(f'Android APK: {apk}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
