"""Setup shows only the system, dark or light theme; album colors wait for the first song."""

import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

app = QApplication([])
app.setStyle('Fusion')

from first_run import FIXED_THEMES, FirstRunDialog
from main import PlayerWindow
from theme_settings import ThemeSettingsDialog

BACKGROUND = {mode: colors['theme_background_color'] for mode, colors in FIXED_THEMES.items()}
root = Path(tempfile.mkdtemp())


def settled():
    QTest.qWait(2600)
    return app.property('themeBackground')


for scheme, system, other in ((Qt.ColorScheme.Dark, 'fixed_dark', 'fixed_light'),
                              (Qt.ColorScheme.Light, 'fixed_light', 'fixed_dark')):
    with patch('PySide6.QtGui.QStyleHints.colorScheme', return_value=scheme):
        settings = QSettings(str(root / f'{system}.ini'), QSettings.IniFormat)
        window = PlayerWindow(settings)
        window.show()
        assert app.property('themeBackground') == BACKGROUND[system]
        guide = FirstRunDialog(settings, window)
        guide.show()
        assert guide.selected_mode() == 'any'
        assert settled() == BACKGROUND[system]
        guide.advance()
        same = system.removeprefix('fixed_')
        opposite = other.removeprefix('fixed_')
        guide.choices[opposite].setChecked(True)
        assert settled() == BACKGROUND[other]
        guide.choices['any'].setChecked(True)
        assert settled() == BACKGROUND[system]
        guide.choices[same].setChecked(True)
        assert settled() == BACKGROUND[system]
        guide.choices[system].setChecked(True)
        assert settled() == BACKGROUND[system]
        guide.choices[other].setChecked(True)
        assert settled() == BACKGROUND[other]
        guide.choices[opposite].setChecked(True)
        assert settled() == BACKGROUND[other]
        guide.choices['any'].setChecked(True)
        assert settled() == BACKGROUND[system]
        guide.advance()
        guide.advance()
        assert guide.result() == guide.DialogCode.Accepted
        assert settings.value('artwork_theme_enabled', type=bool)
        assert settings.value('artwork_theme_mode') == 'any'
        assert settings.value('theme_background_color') == BACKGROUND[system]
        assert json.loads(settings.value('custom_theme_colors')) == FIXED_THEMES[system]
        window.apply_settings()
        assert settled() == BACKGROUND[system]

        settings = QSettings(str(root / f'cancel-{system}.ini'), QSettings.IniFormat)
        window = PlayerWindow(settings)
        window.show()
        guide = FirstRunDialog(settings, window)
        guide.show()
        guide.choices[other].setChecked(True)
        assert settled() == BACKGROUND[other]
        guide.reject()
        assert settled() == BACKGROUND[system]
        assert not settings.contains('custom_theme_colors')

        settings = QSettings(str(root / f'settings-{system}.ini'), QSettings.IniFormat)
        settings.setValue('welcome_complete', True)
        settings.setValue('folder', str(root))
        window = PlayerWindow(settings)
        window.show()
        dialog = ThemeSettingsDialog(settings, window)
        dialog.show()

        def pick_each_fixed_theme():
            guide = app.activeModalWidget()
            guide.choices[other.removeprefix('fixed_')].setChecked(True)
            assert settled() == BACKGROUND[other]
            guide.choices['any'].setChecked(True)
            settled()
            for mode in (other, system):
                guide.choices[mode].setChecked(True)
                assert settled() == BACKGROUND[mode], mode
            guide.choices[other].setChecked(True)
            settled()
            guide.accept()

        QTimer.singleShot(0, pick_each_fixed_theme)
        dialog.open_quick_start()
        assert dialog.colors['theme_background_color'].color().name() == BACKGROUND[other]
        dialog.accept()
        assert settings.value('theme_background_color') == BACKGROUND[other]
        assert not settings.value('artwork_theme_enabled', type=bool)
        assert settled() == BACKGROUND[other]

        kept = QSettings(str(root / f'rerun-{system}.ini'), QSettings.IniFormat)
        kept.setValue('custom_theme_colors', '{"theme_background_color": "#123456"}')
        kept.setValue('theme_background_color', '#123456')
        guide = FirstRunDialog(kept)
        guide.choices['dark'].setChecked(True)
        guide.keep_current_colors()
        guide.accept()
        assert kept.value('theme_background_color') == '#123456'
        assert kept.value('custom_theme_colors') == '{"theme_background_color": "#123456"}'

print('PASS: setup follows the system, previews dark or light, and keeps colors on cancel and rerun')
