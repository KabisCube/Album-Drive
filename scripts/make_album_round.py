from pathlib import Path
from io import BytesIO
import math
import unicodedata

import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath, QPainterPathStroker, QTransform
from ttfautohint import ttfautohint


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'assets' / 'fonts' / 'AlbumRound-Bold.ttf'
PREVIEW = ROOT / 'build' / 'album-round-preview.png'
STROKE = 158
GLYPH_SCALE = 1.07
LETTER_SPACING = 14
GLYPHS = {}


def path(*commands):
    result = QPainterPath()
    for command in commands:
        operation, *values = command
        if operation == 'M':
            result.moveTo(*values)
        elif operation == 'L':
            result.lineTo(*values)
        elif operation == 'C':
            result.cubicTo(*values)
        elif operation == 'Q':
            result.quadTo(*values)
        elif operation == 'Z':
            result.closeSubpath()
    return result


def line(*points):
    return path(('M', *points[0]), *(('L', *point) for point in points[1:]))


def ellipse(x, y, width, height):
    result = QPainterPath()
    result.addEllipse(x, y, width, height)
    return result


def dot(center, bottom):
    return ellipse(center - STROKE / 2, bottom, STROKE, STROKE)


def draw_outline(outline, pen):
    active = False
    index = 0
    while index < outline.elementCount():
        element = outline.elementAt(index)
        if element.isMoveTo():
            if active:
                pen.closePath()
            pen.moveTo((element.x, element.y))
            active = True
        elif element.isLineTo():
            pen.lineTo((element.x, element.y))
        elif element.isCurveTo():
            second = outline.elementAt(index + 1)
            third = outline.elementAt(index + 2)
            pen.curveTo((element.x, element.y), (second.x, second.y), (third.x, third.y))
            index += 2
        index += 1
    if active:
        pen.closePath()


def merge_paths(*outlines):
    merged = pathops.Path()
    for outline in outlines:
        if outline.isEmpty():
            continue
        current = pathops.Path()
        draw_outline(outline, current.getPen())
        merged = pathops.op(merged, current, pathops.PathOp.UNION, clockwise=True)
    result = QPainterPath()
    result.setFillRule(Qt.WindingFill)
    for operation, points in merged.segments:
        if operation == 'moveTo':
            result.moveTo(*points[0])
        elif operation == 'lineTo':
            result.lineTo(*points[0])
        elif operation == 'curveTo':
            result.cubicTo(*(value for point in points for value in point))
        elif operation == 'qCurveTo':
            result.quadTo(*(value for point in points for value in point))
        elif operation == 'closePath':
            result.closeSubpath()
    return result


def ink(*paths, weight=STROKE):
    stroker = QPainterPathStroker()
    stroker.setWidth(weight)
    stroker.setCapStyle(Qt.RoundCap)
    stroker.setJoinStyle(Qt.RoundJoin)
    return merge_paths(*(stroker.createStroke(item) for item in paths))


def put(character, width, *paths, filled=False):
    if filled:
        outline = merge_paths(*paths)
    else:
        outline = ink(*paths)
    GLYPHS[character] = (width, outline)


def draw_alphabet():
    put('A', 760, line((105, 58), (380, 642), (655, 58)), line((186, 230), (574, 230)))
    put('B', 650, line((120, 58), (120, 642)), path(('M', 120, 642), ('L', 350, 642), ('C', 585, 642, 585, 360, 350, 360), ('L', 120, 360)), path(('M', 350, 360), ('C', 620, 360, 620, 58, 350, 58), ('L', 120, 58)))
    put('C', 660, path(('M', 553, 558), ('C', 380, 760, 100, 655, 100, 350), ('C', 100, 45, 380, -60, 553, 142)))
    put('D', 690, line((120, 58), (120, 642)), path(('M', 120, 642), ('L', 310, 642), ('C', 685, 642, 685, 58, 310, 58), ('L', 120, 58)))
    put('E', 635, line((535, 642), (120, 642), (120, 58), (535, 58)), line((120, 358), (485, 358)))
    put('F', 560, line((120, 58), (120, 642), (475, 642)), line((120, 365), (425, 365)))
    put('G', 700, path(('M', 566, 560), ('C', 380, 755, 100, 650, 100, 350), ('C', 100, 40, 415, -50, 583, 130), ('L', 583, 330), ('L', 370, 330)))
    put('H', 700, line((120, 58), (120, 642)), line((580, 58), (580, 642)), line((120, 350), (580, 350)))
    put('I', 280, line((140, 58), (140, 642)))
    put('J', 540, path(('M', 425, 642), ('L', 425, 215), ('C', 425, -20, 110, -10, 100, 205)))
    put('K', 650, line((120, 58), (120, 642)), line((535, 642), (128, 306), (555, 58)))
    put('L', 550, line((120, 642), (120, 58), (465, 58)))
    put('M', 850, line((120, 58), (120, 642), (425, 210), (730, 642), (730, 58)))
    put('N', 710, line((120, 58), (120, 642), (590, 58), (590, 642)))
    put('O', 720, ellipse(100, 50, 520, 600))
    put('P', 630, line((120, 58), (120, 642)), path(('M', 120, 642), ('L', 340, 642), ('C', 625, 642, 625, 300, 340, 300), ('L', 120, 300)))
    put('Q', 740, ellipse(100, 50, 520, 600), line((425, 210), (650, -25)))
    put('R', 660, line((120, 58), (120, 642)), path(('M', 120, 642), ('L', 340, 642), ('C', 625, 642, 625, 320, 340, 320), ('L', 120, 320)), line((340, 320), (565, 58)))
    put('S', 620, path(('M', 514, 555), ('C', 452, 704, 105, 678, 105, 493), ('C', 105, 300, 520, 403, 520, 207), ('C', 520, 13, 185, -5, 99, 143)))
    put('T', 620, line((85, 642), (535, 642)), line((310, 642), (310, 58)))
    put('U', 700, path(('M', 115, 642), ('L', 115, 250), ('C', 115, -15, 585, -15, 585, 250), ('L', 585, 642)))
    put('V', 650, line((95, 642), (325, 58), (555, 642)))
    put('W', 940, line((100, 642), (270, 58), (470, 540), (670, 58), (840, 642)))
    put('X', 650, line((110, 642), (540, 58)), line((540, 642), (110, 58)))
    put('Y', 650, line((95, 642), (325, 350), (555, 642)), line((325, 350), (325, 58)))
    put('Z', 620, line((110, 642), (520, 642), (100, 58), (520, 58)))
    put('a', 600,
        path(('M', 130, 425), ('C', 225, 515, 465, 515, 465, 350), ('L', 465, 58)),
        ellipse(110, 45, 355, 245))
    put('b', 610, line((115, 58), (115, 675)), path(('M', 120, 325), ('C', 205, 555, 510, 525, 510, 255), ('C', 510, -20, 205, -35, 120, 170)))
    put('c', 540, path(('M', 440, 409), ('C', 307, 549, 100, 477, 100, 255), ('C', 100, 33, 307, -39, 440, 101)))
    put('d', 610, line((495, 58), (495, 675)), path(('M', 490, 325), ('C', 405, 555, 100, 525, 100, 255), ('C', 100, -20, 405, -35, 490, 170)))
    put('e', 570, path(('M', 110, 250), ('L', 470, 250),
                       ('C', 470, 380, 415, 485, 300, 485),
                       ('C', 175, 485, 100, 390, 100, 260),
                       ('C', 100, 135, 175, 50, 300, 50),
                       ('Q', 390, 50, 440, 55)))
    put('f', 380, path(('M', 160, 58), ('L', 160, 521), ('C', 160, 676, 242, 709, 325, 667)), line((75, 460), (320, 460)))
    put('g', 610, path(('M', 490, 330), ('C', 405, 555, 100, 525, 100, 265), ('C', 100, 5, 405, -20, 490, 185)), path(('M', 495, 452), ('L', 495, 10), ('C', 495, -189, 235, -219, 135, -112)))
    put('h', 610, line((115, 58), (115, 675)), path(('M', 115, 305), ('C', 220, 551, 495, 512, 495, 315), ('L', 495, 58)))
    put('i', 270, ink(line((135, 58), (135, 452))), ellipse(135 - STROKE / 2, 663 - STROKE / 2, STROKE, STROKE), filled=True)
    put('j', 300, path(('M', 180, 452), ('L', 180, -55), ('C', 180, -139, 142, -175, 65, -160)))
    GLYPHS['j'] = (300, GLYPHS['j'][1].united(ellipse(180 - STROKE / 2, 663 - STROKE / 2, STROKE, STROKE)))
    put('k', 550, line((115, 58), (115, 675)), line((445, 452), (120, 200)), line((260, 310), (465, 58)))
    put('l', 285, path(('M', 125, 675), ('L', 125, 112), ('Q', 125, 58, 185, 58)))
    put('m', 900, line((115, 58), (115, 452)), path(('M', 115, 307), ('C', 190, 549, 450, 510, 450, 314), ('L', 450, 58)), path(('M', 450, 307), ('C', 525, 549, 785, 510, 785, 314), ('L', 785, 58)))
    put('n', 610, line((115, 58), (115, 452)), path(('M', 115, 305), ('C', 220, 551, 495, 512, 495, 315), ('L', 495, 58)))
    put('o', 600, ellipse(100, 50, 400, 410))
    put('p', 610, line((115, -155), (115, 452)), path(('M', 120, 325), ('C', 205, 555, 510, 525, 510, 255), ('C', 510, -20, 205, -35, 120, 170)))
    put('q', 610, line((495, -155), (495, 452)), path(('M', 490, 325), ('C', 405, 555, 100, 525, 100, 255), ('C', 100, -20, 405, -35, 490, 170)))
    put('r', 410, line((115, 58), (115, 452)), path(('M', 115, 297), ('C', 162, 428, 245, 491, 335, 450)))
    put('s', 510, path(('M', 410, 408), ('C', 310, 515, 105, 489, 105, 360), ('C', 105, 231, 415, 300, 415, 158), ('C', 415, 20, 190, 10, 95, 100)))
    put('t', 390, path(('M', 160, 607), ('L', 160, 167), ('C', 160, 57, 241, 32, 320, 76)), line((75, 452), (320, 452)))
    put('u', 610, path(('M', 115, 452), ('L', 115, 195), ('C', 115, -5, 390, -40, 495, 205)), line((495, 452), (495, 58)))
    put('v', 540, line((95, 452), (270, 58), (445, 452)))
    put('w', 800, line((95, 452), (235, 58), (400, 397), (565, 58), (705, 452)))
    put('x', 540, line((110, 452), (430, 58)), line((430, 452), (110, 58)))
    put('y', 550, line((95, 452), (285, 70)), path(('M', 455, 452), ('L', 240, -84), ('Q', 205, -178, 105, -155)))
    put('z', 520, line((110, 452), (420, 452), (100, 58), (420, 58)))


def draw_numbers():
    put('0', 600, ellipse(110, 50, 380, 600))
    put('1', 430, line((100, 550), (250, 642), (250, 58)), line((110, 58), (340, 58)))
    put('2', 590, path(('M', 110, 525), ('C', 130, 700, 490, 710, 490, 515),
                       ('C', 490, 425, 400, 345, 315, 275), ('L', 105, 58), ('L', 490, 58)))
    put('3', 590, path(('M', 110, 562), ('C', 220, 706, 490, 661, 490, 497), ('C', 490, 391, 385, 352, 285, 352), ('C', 575, 376, 568, 49, 315, 49), ('Q', 180, 47, 100, 136)))
    put('4', 610, line((420, 58), (420, 642), (90, 233), (520, 233)))
    put('5', 590, path(('M', 475, 642), ('L', 145, 642), ('L', 120, 365), ('C', 410, 466, 560, 332, 480, 158), ('C', 415, 13, 191, 12, 100, 119)))
    put('6', 600, path(('M', 464, 584), ('C', 229, 793, 56, 473, 115, 203), ('C', 164, -15, 490, -3, 490, 216), ('C', 490, 420, 203, 454, 115, 234)))
    put('7', 570, line((95, 642), (480, 642), (205, 58)))
    put('8', 600, ellipse(125, 350, 350, 300), ellipse(105, 50, 390, 300))
    put('9', 600, path(('M', 136, 116), ('C', 371, -93, 544, 227, 485, 497), ('C', 436, 715, 110, 703, 110, 484), ('C', 110, 280, 397, 246, 485, 466)))


def draw_symbols():
    put(' ', 230)
    put('\u00a0', 230)
    comma = ink(path(('M', 135, STROKE / 2), ('Q', 146, -31, 95, -95)))
    put('.', 260, dot(130, 0), filled=True)
    put(',', 270, comma, filled=True)
    put(':', 270, dot(135, 0), dot(135, 350), filled=True)
    put(';', 270, dot(135, 350), comma, filled=True)
    put('!', 280, ink(line((140, 284), (140, 642))), dot(140, 0), filled=True)
    put('?', 560, ink(path(('M', 105, 540), ('C', 166, 715, 460, 678, 460, 518), ('C', 460, 386, 280, 391, 280, 283))), dot(280, 0), filled=True)
    put('-', 410, line((100, 275), (310, 275)))
    put('_', 590, line((75, -100), (515, -100)))
    put('+', 590, line((100, 300), (490, 300)), line((295, 105), (295, 495)))
    put('=', 590, line((100, 410), (490, 410)), line((100, 190), (490, 190)))
    put('/', 460, line((90, -65), (370, 700)))
    put('\\', 460, line((90, 700), (370, -65)))
    put('|', 260, line((130, -110), (130, 700)))
    put('(', 340, path(('M', 245, 715), ('C', 50, 503, 50, 135, 245, -90)))
    put(')', 340, path(('M', 95, 715), ('C', 290, 503, 290, 135, 95, -90)))
    put('[', 350, line((260, 705), (125, 705), (125, -80), (260, -80)))
    put(']', 350, line((90, 705), (225, 705), (225, -80), (90, -80)))
    put('{', 410, path(('M', 315, 705), ('Q', 185, 705, 185, 560), ('L', 185, 430), ('Q', 185, 315, 90, 315), ('Q', 185, 315, 185, 200), ('L', 185, 65), ('Q', 185, -80, 315, -80)))
    put('}', 410, QTransform(-1, 0, 0, 1, 410, 0).map(GLYPHS['{'][1]), filled=True)
    put('<', 550, line((450, 530), (110, 300), (450, 70)))
    put('>', 550, line((100, 530), (440, 300), (100, 70)))
    put("'", 240, line((120, 660), (120, 510)))
    put('"', 390, line((110, 660), (110, 510)), line((280, 660), (280, 510)))
    put('`', 310, line((110, 720), (225, 620)))
    put('~', 610, path(('M', 100, 295), ('C', 240, 475, 370, 140, 510, 320)))
    put('^', 530, line((100, 450), (265, 650), (430, 450)))
    put('*', 480, line((240, 660), (240, 320)), line((90, 575), (390, 405)), line((90, 405), (390, 575)))
    put('#', 650, line((260, 650), (170, 50)), line((480, 650), (390, 50)), line((115, 450), (555, 450)), line((85, 245), (525, 245)))
    put('$', 620, GLYPHS['S'][1], ink(line((310, -80), (310, 780)), weight=66), filled=True)
    put('%', 800, ellipse(95, 435, 180, 215), ellipse(525, 50, 180, 215), line((160, 50), (640, 650)))
    put('&', 720, path(('M', 600, 58), ('L', 213, 430), ('C', 30, 625, 375, 760, 410, 559), ('C', 440, 408, 109, 376, 110, 205), ('C', 110, -41, 526, -9, 594, 316)))
    put('@', 900, ink(path(('M', 550, 395), ('C', 500, 523, 300, 472, 300, 295), ('C', 300, 128, 520, 127, 557, 310), ('L', 585, 455), ('L', 550, 240), ('C', 525, 73, 785, 142, 785, 380), ('C', 785, 780, 105, 745, 105, 340), ('C', 105, -55, 504, -123, 710, 10)), weight=75), filled=True)
    put('\u2022', 400, ellipse(100, 210, 200, 200), filled=True)
    put('\u2026', 780, *(QTransform.fromTranslate(x, 0).map(GLYPHS['.'][1]) for x in (0, 260, 520)), filled=True)
    for character, width in [('–', 620), ('—', 900), ('−', 590)]:
        put(character, width, line((90, 275), (width - 90, 275)))
    for character, base in [('‘', ','), ('’', "'"), ('‚', ','), ('“', '"'), ('”', '"'), ('„', '"')]:
        width, outline = GLYPHS[base]
        offset = 570 if character == '‘' else -510 if character == '„' else 0
        put(character, width, QTransform.fromTranslate(0, offset).map(outline), filled=True)
    put('×', 590, line((130, 465), (460, 135)), line((460, 465), (130, 135)))
    put('÷', 590, ink(line((100, 300), (490, 300))), dot(295, 490), dot(295, 0), filled=True)
    put('€', 660, GLYPHS['C'][1], ink(line((80, 420), (410, 420)), line((80, 280), (380, 280)), weight=70), filled=True)
    put('£', 590, path(('M', 470, 565), ('C', 370, 728, 155, 655, 170, 478), ('L', 190, 230), ('Q', 200, 120, 100, 58), ('L', 490, 58)), line((95, 320), (350, 320)))
    put('°', 370, ink(ellipse(110, 480, 150, 150), weight=70), filled=True)
    put('©', 820, ink(ellipse(90, 20, 640, 640), weight=60), QTransform(.65, 0, 0, .65, 195, 110).map(GLYPHS['C'][1]), filled=True)
    put('®', 820, ink(ellipse(90, 20, 640, 640), weight=60), QTransform(.59, 0, 0, .59, 210, 135).map(GLYPHS['R'][1]), filled=True)
    put('™', 760, QTransform(.48, 0, 0, .48, 0, 380).map(GLYPHS['T'][1]), QTransform(.48, 0, 0, .48, 320, 380).map(GLYPHS['M'][1]), filled=True)
    for character, angle in [('→', 0), ('↑', 90), ('←', 180), ('↓', 270)]:
        arrow = ink(line((100, 300), (600, 300)), line((410, 490), (600, 300), (410, 110)), weight=85)
        transform = QTransform().translate(350, 300).rotate(angle).translate(-350, -300)
        put(character, 700, transform.map(arrow), filled=True)
    put('♪', 550, ink(line((350, 125), (350, 660), (480, 560)), weight=85), ellipse(100, 0, 250, 160), filled=True)


def draw_accents():
    for codepoint in range(0xC0, 0x180):
        character = chr(codepoint)
        decomposition = unicodedata.normalize('NFD', character)
        if len(decomposition) != 2 or decomposition[0] not in GLYPHS:
            continue
        base, accent = decomposition
        width, outline = GLYPHS[base]
        center = width / 2
        height = 815 if base.isupper() else 640
        marks = {
            '\u0300': ink(line((center - 80, height + 45), (center + 30, height - 30)), weight=72),
            '\u0301': ink(line((center - 30, height - 30), (center + 80, height + 45)), weight=72),
            '\u0302': ink(line((center - 100, height - 25), (center, height + 45), (center + 100, height - 25)), weight=65),
            '\u0303': ink(path(('M', center - 110, height), ('C', center - 30, height + 95, center + 30, height - 95, center + 110, height)), weight=65),
            '\u0308': merge_paths(dot(center - 105, height - 42), dot(center + 105, height - 42)),
            '\u030a': ink(ellipse(center - (STROKE - 48) / 2, height - 18, STROKE - 48, STROKE - 48), weight=48),
            '\u0327': ink(path(('M', center + 20, -25), ('L', center - 20, -95), ('C', center + 105, -75, center + 90, -205, center - 50, -175)), weight=55),
            '\u030c': ink(line((center - 100, height + 40), (center, height - 30), (center + 100, height + 40)), weight=65),
            '\u0304': ink(line((center - 100, height), (center + 100, height)), weight=65),
            '\u0306': ink(path(('M', center - 100, height + 30), ('Q', center, height - 100, center + 100, height + 30)), weight=65),
            '\u0307': dot(center, height - 42),
            '\u030b': ink(line((center - 100, height - 30), (center - 25, height + 45)), line((center + 35, height - 30), (center + 110, height + 45)), weight=60),
            '\u0328': ink(path(('M', center + 80, 0), ('C', center - 80, -145, center + 40, -215, center + 120, -155)), weight=55),
        }
        if accent in marks:
            if base == 'i':
                outline = ink(line((135, 58), (135, 452)))
            put(character, width, outline, marks[accent], filled=True)
    for character, base in [('Ø', 'O'), ('ø', 'o'), ('Ł', 'L'), ('ł', 'l')]:
        width, outline = GLYPHS[base]
        height = 650 if base.isupper() else 460
        put(character, width, outline, ink(line((85, 20), (width - 85, height)), weight=73), filled=True)
    put('\u00d0', 690, GLYPHS['D'][1], ink(line((65, 350), (300, 350))), filled=True)
    put('\u00f0', 600, GLYPHS['o'][1], ink(
        path(('M', 500, 255), ('C', 520, 460, 395, 640, 220, 675)),
        line((210, 555), (420, 665))), filled=True)
    put('\u00de', 630, line((120, 58), (120, 642)),
        path(('M', 120, 520), ('L', 340, 520), ('C', 625, 520, 625, 200, 340, 200), ('L', 120, 200)))
    put('\u00fe', 610, GLYPHS['b'][1], ink(line((115, -155), (115, 58))), filled=True)
    put('ß', 630, path(('M', 115, 58), ('L', 115, 490), ('C', 115, 755, 530, 737, 483, 529), ('C', 464, 442, 366, 430, 330, 365), ('C', 635, 370, 586, -48, 310, 70)))
    for character, left, right in [('Æ', 'A', 'E'), ('æ', 'a', 'e'), ('Œ', 'O', 'E'), ('œ', 'o', 'e')]:
        left_width, left_outline = GLYPHS[left]
        right_width, right_outline = GLYPHS[right]
        scale = .85
        offset = left_width * scale - 65
        put(character, round(offset + right_width * scale), QTransform(scale, 0, 0, 1, 0, 0).map(left_outline), QTransform(scale, 0, 0, 1, offset, 0).map(right_outline), filled=True)
    put('¡', 280, QTransform(1, 0, 0, -1, 0, 500).map(GLYPHS['!'][1]), filled=True)
    put('¿', 560, QTransform(1, 0, 0, -1, 0, 500).map(GLYPHS['?'][1]), filled=True)
    for character, base in [('«', '<'), ('»', '>')]:
        outline = QTransform(.6, 0, 0, .7, 0, 80).map(GLYPHS[base][1])
        put(character, 640, outline, QTransform.fromTranslate(260, 0).map(outline), filled=True)


def build_font():
    GLYPHS.clear()
    draw_alphabet()
    draw_numbers()
    draw_symbols()
    draw_accents()
    names = {character: f'uni{ord(character):04X}' for character in GLYPHS}
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(['.notdef', *names.values()])
    builder.setupCharacterMap({ord(character): name for character, name in names.items()})
    outlines = {}
    metrics = {}
    missing = ink(line((100, 0), (100, 700), (550, 700), (550, 0), (100, 0)), weight=65)
    for character, (width, outline) in {None: (650, missing), **GLYPHS}.items():
        name = '.notdef' if character is None else names[character]
        pen = TTGlyphPen(None)
        curves = Cu2QuPen(pen, 0.5)
        draw_outline(outline, TransformPen(curves, (GLYPH_SCALE, 0, 0, GLYPH_SCALE, 0, 0)))
        outlines[name] = pen.glyph()
        spacing = LETTER_SPACING if character is not None and character.isalnum() else 0
        metrics[name] = (round((width + spacing) * GLYPH_SCALE), math.floor(outline.boundingRect().left() * GLYPH_SCALE) if not outline.isEmpty() else 0)
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=1000, descent=-270)
    builder.setupNameTable({
        'familyName': 'Album Round',
        'styleName': 'Bold',
        'uniqueFontIdentifier': 'Album Drive:Album Round Bold:1.008',
        'fullName': 'Album Round Bold',
        'psName': 'AlbumRound-Bold',
        'version': 'Version 1.008',
        'manufacturer': 'Album Drive',
        'designer': 'Album Drive',
        'description': 'Original rounded geometric Latin display font, drawn from procedural paths.',
        'licenseDescription': 'Distributed under the GNU General Public License version 3. See the project LICENSE.',
        'licenseInfoURL': 'https://www.gnu.org/licenses/gpl-3.0.html',
    })
    builder.setupOS2(sTypoAscender=1000, sTypoDescender=-270, sTypoLineGap=0, usWinAscent=1000, usWinDescent=270, sxHeight=outlines[names['x']].yMax, sCapHeight=outlines[names['H']].yMax, usWeightClass=700, fsSelection=32, fsType=0)
    builder.setupPost()
    builder.setupMaxp()
    builder.font['head'].macStyle = 1
    builder.font['head'].fontRevision = 1.008
    pairs = {
        'AV': -45, 'AW': -35, 'AY': -50, 'AT': -35, 'FA': -25,
        'LT': -25, 'LV': -30, 'LY': -35, 'PA': -30, 'TA': -35,
        'To': -40, 'Ta': -40, 'Te': -40, 'Tu': -25, 'VA': -45,
        'Va': -35, 'Vo': -35, 'WA': -35, 'Wa': -25, 'Wo': -25,
        'YA': -50, 'Ya': -45, 'Yo': -45, 'Ye': -45,
    }
    rules = '\n'.join(f'pos {names[left]} {names[right]} {round(value * GLYPH_SCALE)};' for (left, right), value in pairs.items())
    addOpenTypeFeaturesFromString(builder.font, f'feature kern {{\n{rules}\n}} kern;')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    builder.save(buffer)
    OUTPUT.write_bytes(ttfautohint(in_buffer=buffer.getvalue(), no_info=True, increase_x_height=0,
                                  windows_compatibility=True))
    return len(GLYPHS)


def preview():
    canvas = Image.new('RGB', (1640, 1100), '#f4f1e9')
    draw = ImageDraw.Draw(canvas)
    label_font = ImageFont.truetype(str(OUTPUT), 23)
    draw.text((65, 36), 'ALBUM ROUND / ORIGINAL FONT STUDY', font=label_font, fill='#66705c')
    draw.text((60, 85), 'Album Drive', font=ImageFont.truetype(str(OUTPUT), 116), fill='#233429')
    draw.text((65, 260), 'NEW: ALBUM ROUND BOLD', font=label_font, fill='#66705c')
    draw.text((65, 301), 'Play your favourite albums.', font=ImageFont.truetype(str(OUTPUT), 63), fill='#233429')
    draw.text((65, 416), 'SMALL INTERFACE TEXT', font=label_font, fill='#66705c')
    draw.text((65, 475), 'Albums   Folders   Settings   Now playing', font=ImageFont.truetype(str(OUTPUT), 28), fill='#233429')
    draw.line((65, 574, 1575, 574), fill='#cbd0c0', width=2)
    for y, text, size in [
        (605, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 49),
        (700, 'abcdefghijklmnopqrstuvwxyz', 57),
        (794, '0123456789   ÅÄÖ åäö   Éé Ññ Üü', 54),
        (895, 'Now playing  •  Settings  •  Volume 75%', 39),
        (975, 'The quick brown fox jumps over the lazy dog.', 36),
    ]:
        draw.text((65, y), text, font=ImageFont.truetype(str(OUTPUT), size), fill='#233429')
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(PREVIEW)


if __name__ == '__main__':
    count = build_font()
    preview()
    print(f'Built {OUTPUT.relative_to(ROOT)} with {count} characters')
    print(f'Preview: {PREVIEW.relative_to(ROOT)}')
