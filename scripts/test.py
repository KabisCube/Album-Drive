import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('names', nargs='*')
    parser.add_argument('--checks', action='store_true')
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    checks = root / 'tests' / 'checks'
    environment = os.environ.copy()
    environment['PYTHONPATH'] = os.pathsep.join(filter(None, (
        str(root / 'src'), str(root / 'tests'), str(root), environment.get('PYTHONPATH'))))
    environment.setdefault('QT_QPA_PLATFORM', 'offscreen')
    (root / 'build' / 'previews').mkdir(parents=True, exist_ok=True)
    (root / 'build' / 'debug').mkdir(parents=True, exist_ok=True)
    if arguments.names or arguments.checks:
        paths = [checks / (Path(name).stem + '.py') for name in arguments.names] if arguments.names else sorted(checks.glob('check_*.py'))
        missing = [path.name for path in paths if not path.is_file()]
        if missing:
            parser.error('Unknown checks: ' + ', '.join(missing))
        failed = []
        for path in paths:
            print(f'Running {path.stem}', flush=True)
            if subprocess.run([sys.executable, str(path)], cwd=root, env=environment).returncode:
                failed.append(path.stem)
        if failed:
            print('Failed: ' + ', '.join(failed), file=sys.stderr)
        return bool(failed)
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'],
                          cwd=root, env=environment).returncode


if __name__ == '__main__':
    sys.exit(main())
