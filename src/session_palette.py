"""Remember the displayed palette without replacing custom colors or presets."""

import json

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from themes import ARTWORK_THEME_DEFAULT, ARTWORK_THEME_MODE_DEFAULT, COLOR_SETTINGS, THEME_DEFAULT


def palette_preferences(settings):
    return {
        'palette_version': 13,
        'theme': settings.value('theme', THEME_DEFAULT),
        'enabled': settings.value('artwork_theme_enabled', ARTWORK_THEME_DEFAULT, type=bool),
        'mode': settings.value('artwork_theme_mode', ARTWORK_THEME_MODE_DEFAULT),
        'preset': settings.value('selected_color_theme', ''),
        'custom': settings.value('custom_theme_colors', ''),
        'colors': {key: settings.value(key, default) for _, _, key, _, default in COLOR_SETTINGS},
    }


def load_session_palette(settings):
    try:
        snapshot = json.loads(str(settings.value('session/palette', '{}')))
        if not isinstance(snapshot, dict) or snapshot.get('preferences') != palette_preferences(settings):
            return None
        colors = snapshot.get('colors')
        if not isinstance(colors, dict) or not all(isinstance(colors.get(prop), str) and QColor(colors[prop]).isValid()
                                                  for _, _, _, prop, _ in COLOR_SETTINGS):
            return None
        if not isinstance(snapshot.get('artwork'), bool):
            return None
        snapshot['colors'] = {prop: colors[prop] for _, _, _, prop, _ in COLOR_SETTINGS}
        return snapshot
    except (ValueError, TypeError):
        return None


def save_session_palette(settings):
    app = QApplication.instance()
    colors = {prop: app.property(prop) for _, _, _, prop, _ in COLOR_SETTINGS}
    snapshot = dict(colors=colors, artwork=bool(app.property('artworkTheme')),
                    preferences=palette_preferences(settings))
    settings.setValue('session/palette', json.dumps(snapshot))
