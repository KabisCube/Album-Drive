import os
from pathlib import Path


def filesystem_path(path):
    path = Path(path)
    if os.name != 'nt':
        return path
    value = os.path.normpath(str(path if path.is_absolute() else Path.cwd() / path))
    if value.startswith('\\\\?\\'):
        return path
    if value.startswith('\\\\'):
        return Path('\\\\?\\UNC\\' + value[2:])
    return Path('\\\\?\\' + value)


def library_path(path):
    value = os.fspath(path)
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return Path(value)
