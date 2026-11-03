"""Saved color presets, artwork opt-out and smooth folder scrolling."""

import os
import tempfile
import time
import json
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QSettings, Qt, QVariantAnimation
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSlider

from main import PlayerWindow
from theme_settings import ThemeSettingsDialog, custom_color_settings, saved_color_themes
from themes import BUILDING_GRAY, COLOR_SETTINGS
from test_library import make_wave


def wait_until(condition):
    deadline = time.monotonic() + 8
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(20)
        time.sleep(.005)
    assert condition()


def finish_colors(window):
    if getattr(window, 'theme_fade', None) is not None:
        window.theme_fade.setCurrentTime(4000)


app = QApplication([])
app.setStyle('Fusion')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    music = root / 'Music'
    for title, color in (('Blue album', '#162b47'), ('Gold album', '#e7c977')):
        make_wave(music / title / '1.wav')
        Image.new('RGB', (32, 32), color).save(music / title / 'cover.png')
    make_wave(music / 'No artwork' / '1.wav')
    for number in range(70):
        (music / f'Folder {number:02}').mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(music))
    window = PlayerWindow(settings)
    window.show()
    wait_until(lambda: len(window.albums) == 3 and not window.scanners)
    blue, gold, no_art = sorted(window.albums, key=lambda album: album.folder.name)
    base = {key: app.property(prop) for _, _, key, prop, _ in COLOR_SETTINGS}
    window.play_album(blue, 0)
    window.player.pause()
    finish_colors(window)
    snapshot = {key: app.property(prop) for _, _, key, prop, _ in COLOR_SETTINGS}

    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    assert dialog.library_button.text() == 'Choose'
    assert dialog.artwork_theme.isChecked()
    dialog.save_current_colors()
    assert dialog.saved_theme_choice.currentText() == blue.title
    assert dialog.presets[1]['colors'] == snapshot
    assert [preset['name'] for preset in saved_color_themes(settings)] == ['Default']
    dialog.apply()
    preset_id = dialog.presets[1]['id']
    dialog.accept()
    dialog = ThemeSettingsDialog(settings, window)
    dialog.applied.connect(window.apply_settings)
    assert saved_color_themes(settings)[1]['name'] == blue.title
    # Recover old installs where selecting Custom left preset colors in place.
    legacy = QSettings(str(root / 'legacy.ini'), QSettings.IniFormat)
    legacy.setValue('saved_color_themes', json.dumps(dialog.presets))
    for key, value in snapshot.items():
        legacy.setValue(key, value)
    assert custom_color_settings(legacy)['theme_background_color'] == BUILDING_GRAY
    legacy.setValue('selected_color_theme', preset_id)
    assert custom_color_settings(legacy)['theme_background_color'] == BUILDING_GRAY
    assert saved_color_themes(legacy)[1]['colors'] == snapshot
    dialog.save_current_colors()
    assert dialog.saved_theme_choice.currentText() == f'{blue.title} (2)'
    dialog.artwork_theme.setChecked(False)
    dialog.reject()
    assert len(saved_color_themes(settings)) == 2
    assert settings.value('artwork_theme_enabled', False, type=bool)

    # Saving album colors must not replace the artwork-free fallback palette.
    window.queue = [(track, no_art) for track in no_art.tracks]
    window.play_index(0, autoplay=False)
    finish_colors(window)
    assert not app.property('artworkTheme')
    assert not app.property('customColorTheme')
    for _, _, key, prop, _ in COLOR_SETTINGS:
        assert app.property(prop) == base[key], prop
    image = window.centralWidget().grab().toImage()
    assert image.pixelColor(image.width() - 2, 2).name() == base['theme_background_color']
    window.apply_settings()
    assert app.property('themeBackground') == base['theme_background_color']

    window.queue = [(track, gold) for track in gold.tracks]
    window.play_index(0, autoplay=False)
    finish_colors(window)
    assert app.property('themeBackground') != snapshot['theme_background_color']
    manual = ThemeSettingsDialog(settings, window)
    manual.applied.connect(window.apply_settings)
    manual.saved_theme_choice.setCurrentIndex(0)
    manual.saved_theme_choice.setCurrentIndex(manual.saved_theme_choice.findData(preset_id))
    manual.theme_name = 'classic'
    assert not manual.artwork_theme.isChecked()
    for key, value in snapshot.items():
        assert manual.colors[key].color().name() == value
    manual.apply()
    assert not settings.value('artwork_theme_enabled', True, type=bool)
    finish_colors(window)
    for _, _, key, prop, _ in COLOR_SETTINGS:
        assert app.property(prop) == snapshot[key]
    image = window.centralWidget().grab().toImage()
    assert image.pixelColor(image.width() - 2, 2).name() == snapshot['theme_background_color']
    window.play_index(0, autoplay=False)
    assert window.theme_fade is None
    assert app.property('themeBackground') == snapshot['theme_background_color']
    window.show_album(gold)
    assert window.album_table.property('paperBackgroundColor') == '#e7c977'
    window.show_albums()
    # Custom colors restores the base palette rather than leaving the preset.
    manual.saved_theme_choice.setCurrentIndex(0)
    assert not manual.artwork_theme.isChecked()
    assert manual.colors['theme_background_color'].color().name() == base['theme_background_color']
    manual.apply()
    finish_colors(window)
    assert app.property('themeBackground') == base['theme_background_color']
    assert not app.property('customColorTheme')
    assert custom_color_settings(settings)['theme_background_color'] == base['theme_background_color']
    manual.saved_theme_choice.setCurrentIndex(manual.saved_theme_choice.findData(preset_id))
    manual.apply()
    finish_colors(window)
    assert app.property('themeBackground') == snapshot['theme_background_color']
    manual.close()

    # Pixel scrolling eases toward accumulated wheel targets, like the grid.
    tree = window.tree
    bar = tree.verticalScrollBar()
    wait_until(lambda: bar.maximum() > 300)
    bar.setValue(0)

    def wheel(angle=-120, pixels=0):
        point = tree.viewport().rect().center()
        event = QWheelEvent(QPointF(point), QPointF(tree.viewport().mapToGlobal(point)),
                            QPoint(0, pixels), QPoint(0, angle), Qt.NoButton,
                            Qt.NoModifier, Qt.NoScrollPhase, False)
        app.sendEvent(tree.viewport(), event)
        assert event.isAccepted()

    wheel()
    first_target = tree.scroll_target
    assert first_target > 0 and bar.value() == 0
    tree.scroll_animation.setCurrentTime(60)
    assert 0 < bar.value() < first_target
    wheel()
    assert tree.scroll_target == min(first_target * 2, bar.maximum())
    wait_until(lambda: bar.value() == tree.scroll_target)
    wheel(angle=0, pixels=-20)
    assert tree.scroll_target == min(first_target * 2 + 20, bar.maximum())
    wait_until(lambda: bar.value() == tree.scroll_target)
    wheel()
    bar.triggerAction(QAbstractSlider.SliderSingleStepAdd)
    assert tree.scroll_animation.state() != QVariantAnimation.Running
    wheel()
    tree.setRootIndex(tree.rootIndex())
    assert tree.scroll_animation.state() != QVariantAnimation.Running

    window.close()
    QTest.qWait(200)
    settings.sync()
    restored = PlayerWindow(QSettings(settings.fileName(), QSettings.IniFormat))
    restored.show()
    wait_until(lambda: not restored.scanners and len(restored.albums) == 3)
    assert app.property('themeBackground') == snapshot['theme_background_color']
    persisted = ThemeSettingsDialog(restored.settings, restored)
    assert not persisted.artwork_theme.isChecked()
    assert persisted.saved_theme_choice.currentText() == blue.title
    assert len(persisted.presets) == 2  # Built-in Default plus the saved album.
    persisted.applied.connect(restored.apply_settings)
    persisted.artwork_theme.setChecked(True)
    persisted.apply()
    finish_colors(restored)
    assert restored.now_playing_theme_colors() is not None
    # Returning to artwork mode still uses the base for albums without covers.
    restored.queue = [(track, no_art) for track in no_art.tracks]
    restored.play_index(0, autoplay=False)
    finish_colors(restored)
    assert app.property('themeBackground') == base['theme_background_color']
    persisted.restore_defaults()
    assert len(persisted.presets) == 2  # Resetting appearance keeps Default and saved palettes.
    assert persisted.artwork_theme.isChecked()
    assert persisted.saved_theme_choice.currentData() == 'album-drive-default'
    persisted.close()
    restored.close()
    QTest.qWait(200)

print('PASS: album-named color presets, Apply/Cancel, persistence, manual colors, artwork toggle and smooth folder scrolling')
