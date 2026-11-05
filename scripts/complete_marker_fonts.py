from array import array
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import math
import string
import unicodedata

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter, QPainterPath, QPolygonF
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'assets/fonts/handwriting'
PREVIEWS = ROOT / 'docs/fonts'
SCANNED = string.ascii_letters + string.digits + "'\":;()-&@#%+=/.,!?"
STYLE = {
    1: (86, 0.76, 0.16, -14, 60, 72),
    2: (34, 0.68, 0.44, -19, 36, 45),
    3: (91, 0.51, 0.25, -24, 58, 68),
    4: (99, 0.43, 0.57, -31, 62, 74),
}


def name(char):
    return f'uni{ord(char):04X}'


def bounds(glyph):
    points = glyph.coordinates
    return min(x for x, y in points), min(y for x, y in points), max(x for x, y in points), max(y for x, y in points)


def subset(glyph, indexes):
    result = deepcopy(glyph)
    coordinates, flags, ends = [], [], []
    start = 0
    for index, end in enumerate(glyph.endPtsOfContours):
        if index in indexes:
            coordinates.extend(glyph.coordinates[start:end+1])
            flags.extend(glyph.flags[start:end+1])
            ends.append(len(coordinates)-1)
        start = end+1
    result.coordinates = GlyphCoordinates(coordinates)
    result.flags = array('B', flags)
    result.endPtsOfContours = ends
    result.numberOfContours = len(ends)
    result.program.fromBytecode([])
    return result


def fitted(glyph, box):
    result = deepcopy(glyph)
    left, bottom, right, top = bounds(glyph)
    x, y, width, height = box
    result.coordinates = GlyphCoordinates([
        (round(x+(px-left)*width/(right-left)), round(y+(py-bottom)*height/(top-bottom)))
        for px, py in glyph.coordinates
    ])
    result.program.fromBytecode([])
    return result


def combine(glyf, parts):
    pen = TTGlyphPen(glyf)
    for glyph_name, x, y in parts:
        pen.addComponent(glyph_name, (1, 0, 0, 1, round(x), round(y)))
    return pen.glyph()


def outline_glyph(outline):
    pen = TTGlyphPen(None)
    curves = Cu2QuPen(pen, 0.8)
    index = 0
    active = False
    while index < outline.elementCount():
        element = outline.elementAt(index)
        if element.isMoveTo():
            if active:
                curves.closePath()
            curves.moveTo((element.x, element.y))
            active = True
        elif element.isLineTo():
            curves.lineTo((element.x, element.y))
        elif element.isCurveTo():
            second = outline.elementAt(index+1)
            third = outline.elementAt(index+2)
            curves.curveTo((element.x, element.y), (second.x, second.y), (third.x, third.y))
            index += 2
        index += 1
    if active:
        curves.closePath()
    return pen.glyph()


def brush(style, paths, factor=1):
    weight, ratio, slant, angle, _, _ = STYLE[style]
    angle = math.radians(angle)
    major = math.cos(angle), math.sin(angle)
    outline = QPainterPath()
    outline.setFillRule(Qt.FillRule.WindingFill)
    for stroke_index, commands in enumerate(paths):
        path = QPainterPath()
        for command, *values in commands:
            if command == 'M':
                path.moveTo(*values)
            elif command == 'L':
                path.lineTo(*values)
            else:
                path.cubicTo(*values)
        count = max(18, min(150, round(path.length()/7)))
        samples = [path.pointAtPercent(i/count) for i in range(count+1)]
        left, right = [], []
        for index, point in enumerate(samples):
            before, after = samples[max(0, index-1)], samples[min(count, index+1)]
            dx, dy = after.x()-before.x(), after.y()-before.y()
            length = math.hypot(dx, dy) or 1
            nx, ny = -dy/length, dx/length
            projected = math.hypot(nx*major[0]+ny*major[1], ratio*(-nx*major[1]+ny*major[0]))
            t = index/count
            pressure = 0.89+0.07*math.sin(t*math.tau+stroke_index)+0.035*math.sin(t*17+style)
            pressure *= 0.68+0.32*math.sin(math.pi*t)**0.2
            radius = weight*factor*projected*pressure/2
            left.append(QPointF(point.x()+nx*radius+slant*(point.y()+ny*radius), point.y()+ny*radius))
            right.append(QPointF(point.x()-nx*radius+slant*(point.y()-ny*radius), point.y()-ny*radius))
        ribbon = QPainterPath()
        ribbon.addPolygon(QPolygonF(left+right[::-1]))
        ribbon.closeSubpath()
        outline = outline.united(ribbon)
    return outline_glyph(outline)


def symbols(style):
    paths = {
        '[': [[('M', 65, -95), ('C', 75, 145, 95, 490, 105, 745)], [('M', 100, 740), ('C', 165, 745, 225, 765, 285, 755)], [('M', 65, -95), ('C', 140, -100, 215, -80, 275, -70)]],
        ']': [[('M', 255, 745), ('C', 245, 485, 230, 125, 225, -90)], [('M', 75, 730), ('L', 255, 745)], [('M', 55, -100), ('L', 225, -90)]],
        '{': [[('M', 300, 750), ('C', 100, 775, 260, 405, 65, 325), ('C', 245, 250, 80, -115, 285, -95)]],
        '}': [[('M', 65, 740), ('C', 265, 775, 100, 405, 295, 330), ('C', 115, 255, 270, -100, 55, -95)]],
        '*': [[('M', 215, 720), ('L', 195, 400)], [('M', 55, 635), ('L', 355, 480)], [('M', 50, 460), ('L', 370, 655)]],
        '<': [[('M', 400, 540), ('L', 80, 315)], [('M', 80, 315), ('L', 375, 105)]],
        '>': [[('M', 80, 535), ('L', 400, 325)], [('M', 400, 325), ('L', 65, 100)]],
        '\\': [[('M', 65, 750), ('C', 155, 505, 250, 160, 365, -70)]],
        '^': [[('M', 60, 450), ('L', 225, 710)], [('M', 225, 710), ('L', 385, 465)]],
        '_': [[('M', 55, -125), ('C', 190, -135, 345, -105, 450, -110)]],
        '|': [[('M', 125, 760), ('C', 110, 500, 100, 155, 85, -125)]],
        '~': [[('M', 55, 285), ('C', 160, 465, 305, 145, 450, 335)]],
    }
    return {char: brush(style, strokes) for char, strokes in paths.items()}


def top_anchor(glyph, style):
    left, bottom, right, top = bounds(glyph)
    upper = [x for x, y in glyph.coordinates if y > top-(top-bottom)*0.18]
    center = (min(upper)+max(upper))/2 if upper else (left+right)/2
    return round(center+STYLE[style][2]*60), round(top+25)


def complete(path, style):
    font = TTFont(BytesIO(path.read_bytes()))
    glyf = font['glyf']
    metrics = font['hmtx'].metrics
    cmap = dict(font.getBestCmap())
    protected = {cmap[ord(char)] for char in SCANNED}
    originals = {key: (glyf[key].compile(glyf), metrics[key]) for key in protected}

    def put(key, glyph, advance=0, code=None):
        glyf[key] = glyph
        glyph.recalcBounds(glyf)
        metrics[key] = (round(advance), glyph.xMin if glyph.numberOfContours else 0)
        if key not in font.getGlyphOrder():
            font.setGlyphOrder(font.getGlyphOrder()+[key])
        if code is not None:
            cmap[code] = key
        return key

    for char, glyph in symbols(style).items():
        left, bottom, right, top = bounds(glyph)
        glyph.coordinates.translate((43-left, 0))
        put(name(char), glyph, right-left+86, ord(char))

    original_s = glyf[cmap[ord('S')]]
    bar_x = (original_s.xMin+original_s.xMax)/2-STYLE[style][2]*350
    put('marker.dollar.bar', brush(style, [[('M', bar_x, -85), ('C', bar_x+10, 160, bar_x-10, 520, bar_x+15, 795)]], 0.61))
    put(name('$'), combine(glyf, [(cmap[ord('S')], 0, 0), ('marker.dollar.bar', 0, 0)]), metrics[cmap[ord('S')]][0], ord('$'))
    for char, base_char in (('Ø', 'O'), ('ø', 'o')):
        base = cmap[ord(base_char)]
        glyph = glyf[base]
        left, bottom, right, top = bounds(glyph)
        slash = fitted(glyf[cmap[ord('/')]], (left-5, bottom-30, right-left+10, top-bottom+60))
        key = put(f'marker.slash{ord(char):04X}', slash)
        put(name(char), combine(glyf, [(base, 0, 0), (key, 0, 0)]), metrics[base][0], ord(char))

    original_i = glyf[cmap[ord('i')]]
    contours = [subset(original_i, [index]) for index in range(original_i.numberOfContours)]
    dot_index = max(range(len(contours)), key=lambda index: bounds(contours[index])[3])
    dot = contours[dot_index]
    body = subset(original_i, [index for index in range(len(contours)) if index != dot_index])
    dotless = put('dotlessi', body, metrics[cmap[ord('i')]][0], 0x131)
    _, _, _, _, dot_width, dot_height = STYLE[style]
    dot_key = put('marker.dot', fitted(dot, (-dot_width/2, 35, dot_width, dot_height)))
    acute = put('marker.acute', brush(style, [[('M', -65, 30), ('C', -15, 65, 40, 125, 75, 165)]], 0.64))
    grave = put('marker.grave', brush(style, [[('M', -90, 165), ('C', -55, 125, -10, 65, 40, 30)]], 0.64))
    diaeresis = put('marker.dieresis', combine(glyf, [(dot_key, -86, 0), (dot_key, 83, 7)]))
    macron = put('marker.macron', fitted(glyf[cmap[ord('-')]], (-135, 80, 270, {1: 43, 2: 19, 3: 45, 4: 47}[style])))
    ring = put('marker.ring', brush(style, [[('M', 60, 110), ('C', 85, 215, -75, 215, -65, 115), ('C', -65, 15, 60, 10, 60, 110)]], 0.62))
    designs = {
        '\u0302': [[('M', -115, 45), ('L', 0, 165)], [('M', 0, 165), ('L', 115, 50)]],
        '\u0303': [[('M', -130, 65), ('C', -50, 200, 50, -20, 140, 120)]],
        '\u0306': [[('M', -115, 160), ('C', -100, 20, 95, 30, 120, 170)]],
        '\u030C': [[('M', -115, 165), ('L', 0, 45)], [('M', 0, 45), ('L', 120, 170)]],
        '\u0327': [[('M', 10, 0), ('L', -45, -80), ('C', 105, -60, 75, -205, -65, -175)]],
        '\u0328': [[('M', 40, 0), ('C', -110, -75, -60, -210, 75, -160)]],
    }
    accents = {'\u0300': grave, '\u0301': acute, '\u0304': macron, '\u0307': dot_key, '\u0308': diaeresis, '\u030A': ring}
    for mark, paths in designs.items():
        accents[mark] = put(f'marker.accent{ord(mark):04X}', brush(style, paths, 0.64))
    put('marker.doubleacute.left', fitted(glyf[acute], (-110, 25, 90, 145)))
    put('marker.doubleacute.right', fitted(glyf[acute], (40, 25, 90, 150)))
    accents['\u030B'] = put('marker.doubleacute', combine(glyf, [('marker.doubleacute.left', 0, 0), ('marker.doubleacute.right', 0, 0)]))
    accents['\u0323'] = put('marker.dotbelow', fitted(dot, (-dot_width/2, -150, dot_width, dot_height)))
    accents['\u0326'] = put('marker.commabelow', fitted(glyf[cmap[ord(',')]], (-45, -190, 85, 130)))
    spacing = {'`': '\u0300', '´': '\u0301', '¨': '\u0308', '¯': '\u0304', '¸': '\u0327', 'ˆ': '\u0302', 'ˇ': '\u030C', '˘': '\u0306', '˙': '\u0307', '˚': '\u030A', '˜': '\u0303', '˝': '\u030B'}
    for char, mark in spacing.items():
        mark_glyph = glyf[accents[mark]]
        mark_glyph.recalcBounds(glyf)
        width = mark_glyph.xMax-mark_glyph.xMin
        put(name(char), combine(glyf, [(accents[mark], 43-mark_glyph.xMin, 620 if mark not in '\u0327\u0328' else 0)]), width+86, ord(char))
    for code in range(0xC0, 0x180):
        decomposition = unicodedata.normalize('NFD', chr(code))
        if len(decomposition) != 2 or decomposition[0] not in string.ascii_letters or decomposition[1] not in accents:
            continue
        char, mark = decomposition
        base = dotless if char == 'i' and mark not in '\u0323\u0326\u0327\u0328' else cmap[ord(char)]
        glyph = glyf[base]
        if mark in '\u0323\u0326\u0327\u0328':
            x, y = (glyph.xMin+glyph.xMax)/2, min(0, glyph.yMin)
        else:
            x, y = top_anchor(glyph, style)
        put(name(chr(code)), combine(glyf, [(base, 0, 0), (accents[mark], x, y)]), metrics[base][0], code)
    top_class, bottom_class = [], []
    for mark, key in accents.items():
        put(name(mark), combine(glyf, [(key, 0, 0)]), 0, ord(mark))
        (bottom_class if mark in '\u0323\u0326\u0327\u0328' else top_class).append(name(mark))
    feature = [f'markClass {key} <anchor 0 0> @TOP;' for key in top_class]
    feature += [f'markClass {key} <anchor 0 0> @BOTTOM;' for key in bottom_class]
    feature += ['@ABOVE = ['+' '.join(top_class)+'];', f"feature ccmp {{ sub {name('i')}' @ABOVE by {dotless}; }} ccmp;", 'feature mark {']
    for key in [cmap[ord(char)] for char in string.ascii_letters]+[dotless]:
        glyph = glyf[key]
        x, y = top_anchor(glyph, style)
        bottom_x = round((glyph.xMin+glyph.xMax)/2)
        feature.append(f'pos base {key} <anchor {x} {y}> mark @TOP <anchor {bottom_x} {min(0, glyph.yMin)}> mark @BOTTOM;')
    feature.append('} mark;')
    addOpenTypeFeaturesFromString(font, '\n'.join(feature))
    for table in font['cmap'].tables:
        if table.isUnicode():
            table.cmap = dict(cmap)
    used = set(cmap.values()) | {'.notdef'}
    pending = list(used)
    while pending:
        glyph = glyf[pending.pop()]
        for reference in glyph.getComponentNames(glyf):
            if reference not in used:
                used.add(reference)
                pending.append(reference)
    for key in set(font.getGlyphOrder())-used:
        del glyf[key]
        del metrics[key]
    font.setGlyphOrder([key for key in font.getGlyphOrder() if key in used])
    font['OS/2'].recalcUnicodeRanges(font)
    font['head'].fontRevision = 1.001
    font['name'].setName('Licensed under the GNU General Public License, version 3 or later. See AlbumMarker-LICENSE.txt and the project LICENSE.', 13, 3, 1, 0x409)
    font['name'].setName('https://www.gnu.org/licenses/gpl-3.0.html', 14, 3, 1, 0x409)
    for record in font['name'].names:
        if record.nameID == 5:
            font['name'].setName('Version 1.001', record.nameID, record.platformID, record.platEncID, record.langID)
    for key, (encoded, metric) in originals.items():
        assert glyf[key].compile(glyf) == encoded, f'Scanned outline changed: {key}'
        assert metrics[key] == metric, f'Scanned spacing changed: {key}'
    font.save(path)
    loaded = TTFont(BytesIO(path.read_bytes()), checkChecksums=2)
    for key, (encoded, metric) in originals.items():
        assert loaded['glyf'][key].compile(loaded['glyf']) == encoded
        assert loaded['hmtx'][key] == metric
    required = '[]{}*$´~ÅÄÖåäöÀÁÂÃÇÈÉÊËÌÍÎÏÑÒÓÔÕÙÚÛÜÝàáâãçèéêëìíîïñòóôõùúûüýÿŐőŰű'
    assert all(ord(char) in loaded.getBestCmap() for char in required)
    print(f'{path.name}: {len(cmap)} characters; {len(protected)} scanned glyphs and spacing preserved exactly')


def previews():
    app = QGuiApplication.instance() or QGuiApplication([])
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    for focused, filename in ((False, 'album-marker-preview.png'), (True, 'album-marker-symbols.png')):
        image = QImage(2200, 1880, QImage.Format.Format_RGB32)
        image.fill(QColor('#f6f3ec'))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        label = QFont('Segoe UI')
        label.setPixelSize(25)
        for style in range(1, 5):
            top = 30+(style-1)*465
            ident = QFontDatabase.addApplicationFont(str(OUTPUT/f'AlbumMarker{style:02d}-Regular.ttf'))
            family = QFontDatabase.applicationFontFamilies(ident)[0]
            painter.setFont(label)
            painter.setPen(QColor('#736b60'))
            painter.drawText(55, top+28, f'ALBUM MARKER {style:02d} / '+('ADDED SYMBOLS AND ACCENTS' if focused else 'ORIGINAL SCANNED LETTERFORMS'))
            font = QFont(family)
            font.setPixelSize(68 if focused else 64)
            painter.setFont(font)
            painter.setPen(QColor('#25231f'))
            lines = (
                ('A Å Ä O Ö a å ä o ö   É È Ê Ë é è ê ë', '[] {} * $ ´ ` ~ ^ _ | < > \\', 'À Á Â Ã Ç Ñ Ø Ő Ű  à á â ã ç ñ ő ű', 'Ängström  Åke  Björk  Håkan  Mötley Crüe')
                if focused else
                ('The quick brown fox jumps over the lazy dog.', string.ascii_uppercase, string.ascii_lowercase+'  '+string.digits, 'ÅÄÖ åäö éèêñ  []{}*$´~  “Hello” — @#%&+=')
            )
            for index, line in enumerate(lines):
                painter.drawText(55, top+140+index*86, line)
            if style != 4:
                painter.setPen(QColor('#d9d1c5'))
                painter.drawLine(55, top+448, 2145, top+448)
        painter.end()
        image.save(str(PREVIEWS/filename))


def main():
    for style in range(1, 5):
        complete(OUTPUT/f'AlbumMarker{style:02d}-Regular.ttf', style)
    previews()


if __name__ == '__main__':
    main()
