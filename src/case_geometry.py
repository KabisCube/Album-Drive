from PySide6.QtCore import QRectF, QSize


CASE_WIDTH = 180
CASE_HEIGHT = CASE_WIDTH * 1050 / 1202
CASE_PIXMAP_SIZE = QSize(601, 525)


def sleeve_rect(rect):
    border = rect.height() * 23 / 1050
    side = rect.height() - 2 * border
    return QRectF(rect.right() - border - side, rect.top() + border, side, side)
