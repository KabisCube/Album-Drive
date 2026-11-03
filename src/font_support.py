from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from app_paths import ASSETS_DIR


def load_round_fallbacks():
    path = ASSETS_DIR / 'fonts' / 'cjk' / 'ResourceHanRoundedSC-Bold.ttf'
    font_id = QFontDatabase.addApplicationFont(str(path))
    families = QFontDatabase.applicationFontFamilies(font_id)
    QApplication.instance().setProperty('albumRoundFallbacks', families)
    return families


def font_families(family):
    app = QApplication.instance()
    fallbacks = (app.property('albumRoundFallbacks') or []) if app is not None and family == 'Album Round' else []
    return list(dict.fromkeys([family, *fallbacks]))


def font_family_css(family):
    families = [name.replace('\\', '\\\\').replace('"', '\\"') for name in font_families(family)]
    return ', '.join(f'"{name}"' for name in families)
