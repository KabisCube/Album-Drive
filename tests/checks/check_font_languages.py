import os
from pathlib import Path
import tempfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import QRect, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QTextLayout
from PySide6.QtWidgets import QApplication

from font_support import font_families
from main import PlayerWindow


def rendered_families(text, font):
    layout = QTextLayout(text, font)
    layout.beginLayout()
    layout.createLine()
    layout.endLayout()
    runs = layout.glyphRuns()
    assert runs
    assert all(0 not in run.glyphIndexes() for run in runs), text
    return {run.rawFont().familyName() for run in runs}


app = QApplication([])
app.setStyle('Fusion')
samples = [
    ('LATIN', 'Album Drive — Play your favourite albums.'),
    ('JAPANESE', '日本語の音楽を再生する。ひらがな カタカナ'),
    ('KOREAN', '한국어 음악을 재생합니다. 앨범과 노래'),
    ('SIMPLIFIED CHINESE', '播放音乐，浏览专辑。设置与音量'),
    ('TRADITIONAL CHINESE', '播放音樂，瀏覽專輯。設定與音量'),
    ('MIXED', 'Album Drive • 音楽 • 음악 • 音乐 • 音樂'),
]
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    music = root / 'Music'
    music.mkdir()
    settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
    settings.setValue('folder', str(music))
    window = PlayerWindow(settings)
    window.show()
    app.processEvents()
    expected = ['Album Round', 'Resource Han Rounded SC']
    assert app.font().families() == expected
    assert window.tree.font().families() == expected
    assert window.album_table.font().families() == expected
    assert font_families('Some Other Font') == ['Some Other Font']
    for font in (app.font(), window.tree.font(), window.album_table.font()):
        assert rendered_families('Album Drive', font) == {'Album Round'}
        assert rendered_families('\u00d0\u00f0 \u00de\u00fe Mi\u00f0vikudags', font) == {'Album Round'}
        for _, sample in samples[1:]:
            assert 'Resource Han Rounded SC' in rendered_families(sample, font)
    settings.setValue('ui_font', 'missing-font.ttf')
    window.apply_settings()
    assert app.font().families() == expected
    assert window.album_table.font().families() == expected
    image = QImage(1560, 1030, QImage.Format_RGB32)
    image.fill(QColor('#f4f1e9'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.TextAntialiasing)
    title = QFont(app.font())
    title.setPixelSize(62)
    painter.setFont(title)
    painter.setPen(QColor('#233429'))
    painter.drawText(QRect(60, 25, 1440, 100), Qt.AlignVCenter, 'Album Round / CJK')
    for index, (label, text) in enumerate(samples):
        y = 155 + index * 140
        font = QFont(app.font())
        font.setPixelSize(18)
        painter.setFont(font)
        painter.setPen(QColor('#66705c'))
        painter.drawText(QRect(60, y, 1440, 30), Qt.AlignVCenter, label)
        font.setPixelSize(42)
        painter.setFont(font)
        painter.setPen(QColor('#233429'))
        painter.drawText(QRect(60, y + 35, 1440, 75), Qt.AlignVCenter, text)
    painter.end()
    preview = Path('build/previews/album-round-cjk.png')
    preview.parent.mkdir(parents=True, exist_ok=True)
    assert image.save(str(preview))
    window.close()
    app.processEvents()

print('PASS: bundled rounded CJK glyphs, Latin preservation, interface/track inheritance, missing-font fallback and mixed-language preview')
