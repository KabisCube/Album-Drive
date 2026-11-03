"""Portable app preferences and editable INI files for saved themes."""

import hashlib
import json
from pathlib import Path
import re
import sys

from PySide6.QtCore import QSettings, QStandardPaths

from themes import CLEANING_DEFAULT, NUMERIC_DEFAULTS, THEME_DEFAULT, UI_FONT_DEFAULT


APPEARANCE_DEFAULTS = dict(NUMERIC_DEFAULTS, theme=THEME_DEFAULT,
                          ui_font=UI_FONT_DEFAULT, i_like_cleaning=CLEANING_DEFAULT)


def library_cache_path(settings):
    if settings.format() == QSettings.IniFormat:
        folder = Path(settings.fileName()).resolve().parent
        return (folder.parent if folder.name == 'themes' else folder) / 'cache' / 'library.sqlite3'
    return Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / 'library.sqlite3'


def theme_directory(settings):
    if settings.format() == QSettings.IniFormat:
        path = Path(settings.fileName()).resolve()
        return path.parent if path.name == 'settings.ini' and path.parent.name == 'themes' else path.with_name(path.stem + '-themes')
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)) / 'themes'


def read_theme_files(settings):
    """None denotes legacy storage; an empty list denotes no saved INI themes."""
    folder = theme_directory(settings)
    presets = []
    found = False
    for path in sorted(folder.glob('*.ini')):
        if path.name == 'settings.ini':
            continue
        found = True
        ini = QSettings(str(path), QSettings.IniFormat)
        identity = str(ini.value('Theme/id', hashlib.sha256(path.name.encode()).hexdigest()))
        name = str(ini.value('Theme/name', path.stem))
        colors = {key.removeprefix('Colors/'): str(ini.value(key)) for key in ini.allKeys() if key.startswith('Colors/')}
        presets.append(dict(id=identity, name=name, colors=colors,
                            preserve_palette=ini.value('Theme/preserve_palette', False, type=bool)))
    return presets if found or settings.value('theme_files_version', 0, type=int) else None


def write_theme_files(settings, presets):
    folder = theme_directory(settings)
    folder.mkdir(parents=True, exist_ok=True)
    existing = {}
    for path in folder.glob('*.ini'):
        if path.name != 'settings.ini':
            ini = QSettings(str(path), QSettings.IniFormat)
            existing[str(ini.value('Theme/id', ''))] = path
    for preset in presets:
        if preset['id'] == 'album-drive-default':
            continue  # The built-in theme is recreated from the shipped defaults.
        slug = re.sub(r'[^\w.-]+', '-', preset['name']).strip('.-')[:64] or 'custom'
        suffix = hashlib.sha256(preset['id'].encode()).hexdigest()[:8]
        path = existing.get(preset['id'], folder / f'theme-{slug}-{suffix}.ini')
        path.resolve().relative_to(folder.resolve())
        ini = QSettings(str(path), QSettings.IniFormat)
        ini.setValue('Theme/id', preset['id'])
        ini.setValue('Theme/name', preset['name'])
        ini.setValue('Theme/preserve_palette', preset.get('preserve_palette') is True)
        for key, color in preset['colors'].items():
            ini.setValue('Colors/' + key, color)
        ini.remove('Settings')
        ini.sync()
        if ini.status() != QSettings.NoError:
            raise OSError(f'Unable to save theme: {path}')
    settings.setValue('theme_files_version', 1)
    settings.remove('saved_color_themes')
    settings.sync()


def create_app_settings(portable_root=None, legacy=None):
    if portable_root is None and not getattr(sys, 'frozen', False):
        return QSettings('LocalMusicPlayer', 'MusicPlayer')
    root = Path(portable_root) if portable_root is not None else Path(sys.executable).resolve().parent
    folder = root / 'themes'
    folder.mkdir(parents=True, exist_ok=True)
    settings = QSettings(str(folder / 'settings.ini'), QSettings.IniFormat)
    if not settings.contains('storage_version'):
        previous = legacy if legacy is not None else QSettings('LocalMusicPlayer', 'MusicPlayer')
        for key in previous.allKeys():
            if not settings.contains(key):
                settings.setValue(key, previous.value(key))
        presets = read_theme_files(previous)
        if presets is not None:
            write_theme_files(settings, presets)
        elif settings.contains('saved_color_themes'):
            try:
                presets = json.loads(str(settings.value('saved_color_themes', '[]')))
                if isinstance(presets, list) and all(isinstance(p, dict) and isinstance(p.get('colors'), dict)
                                                   and isinstance(p.get('id'), str) and isinstance(p.get('name'), str) for p in presets):
                    write_theme_files(settings, presets)
            except (ValueError, TypeError):
                pass
        settings.setValue('storage_version', 1)
        settings.sync()
    if settings.status() != QSettings.NoError:
        raise OSError(f'Album Drive needs a writable themes folder beside the executable: {folder}')
    return settings
