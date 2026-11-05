import logging

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app_paths import ASSETS_DIR, HANDWRITING_FONTS_DIR


def configure_font_rendering(font):
    font.setStyleStrategy(QFont.ContextFontMerging | QFont.PreferAntialias)
    font.setHintingPreference(QFont.PreferNoHinting if font.family() == 'Album Round'
                              else QFont.PreferDefaultHinting)


def load_handwriting_fonts():
    fonts = []
    for path in sorted(HANDWRITING_FONTS_DIR.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.ttf', '.otf', '.ttc', '.otc'}:
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            logging.warning('Unable to load handwriting font: %s', path)
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        for family in families:
            identity = path.relative_to(HANDWRITING_FONTS_DIR).as_posix()
            if len(families) > 1:
                identity += '::' + family
            styles = QFontDatabase.styles(family)
            fonts.append({'id': identity, 'name': path.name, 'family': family,
                          'style': styles[0] if styles else ''})
    return fonts


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
