"""A snapshot of a control that springs down to nothing where the control used to be."""

import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QAbstractScrollArea, QGraphicsOpacityEffect, QStackedWidget, QWidget

from snap_scroll import SpringScroll

POP_FREQUENCY = 16.0
POP_DAMPING = .6
SLIDE_DAMPING = .8


def pop_spring(parent, damping=POP_DAMPING):
	return SpringScroll(parent, frequency=POP_FREQUENCY, damping=damping, settle_distance=.004, settle_speed=.05)


class ScaleGhost(QWidget):
	"""`owner` is the control the snapshot shows. A control has one ghost at a time: when a resize goes back
	and forth, its new ghost takes over from the old one at the old one's current size, instead of
	stacking another copy of the control on top.

	`below` tucks a shrinking ghost under the controls beside it, so a control on its way out never
	covers the ones that stay. It also holds its place in the window while its row moves, so it shrinks
	where the control was instead of drifting along with the row."""

	def __init__(self, parent, pixmap, rect, source=None, grow=False, finished=None, follow=None, owner=None,
				below=False):
		super().__init__(parent)
		start = 0.0 if grow else 1.0
		previous = owner_ghost(owner)
		if previous is not None:
			# Carry on from the old ghost's size only in the same spot; elsewhere that would read as the
			# control jumping across, so the new one starts afresh.
			if QRect(previous.mapToGlobal(QPoint()), previous.size()) == QRect(parent.mapToGlobal(rect.topLeft()), rect.size()):
				start = max(0.0, min(1.0, previous.spring.value))
			previous.retire()
		self.owner = owner
		if owner is not None:
			owner._scale_ghost = self
		self.finished = finished
		self.follow = follow
		self.pixmap = pixmap
		ratio = pixmap.devicePixelRatio()
		area = QRectF(source) if source is not None else QRectF(0, 0, rect.width(), rect.height())
		self.source = QRectF(area.x() * ratio, area.y() * ratio, area.width() * ratio, area.height() * ratio)
		self.setGeometry(rect)
		self.spring = pop_spring(self)
		self.spring.jump(start)
		self.spring.moved.connect(self.step)
		self.spring.glide(1 if grow else 0)
		self.anchor = None
		self.show()
		if below:
			self.lower()
			self.anchor = self.mapTo(self.window(), QPoint())
		else:
			self.raise_()

	def follow_target(self):
		try:
			if self.follow is not None and self.follow.isVisible():
				self.setGeometry(QRect(self.follow.mapTo(self.parentWidget(), QPoint()), self.follow.size()))
		except RuntimeError:
			self.follow = None

	def hold_place(self):
		if self.anchor is not None:
			place = self.parentWidget().mapFrom(self.window(), self.anchor)
			if place != self.pos():
				self.move(place)

	def step(self):
		self.follow_target()
		self.hold_place()
		if not self.spring.moving:
			self.retire()
		self.update()

	def retire(self):
		"""Finish at once: run what waits on it (such as revealing a grown control) and go."""
		if getattr(self, 'retired', False):
			return
		self.retired = True
		try:
			if self.owner is not None and getattr(self.owner, '_scale_ghost', None) is self:
				self.owner._scale_ghost = None
		except RuntimeError:
			pass
		if self.finished is not None:
			finished, self.finished = self.finished, None
			finished()
		self.hide()
		self.deleteLater()

	def paintEvent(self, event):
		scale = max(0.0, self.spring.value)
		if scale <= 0:
			return
		painter = QPainter(self)
		painter.setRenderHint(QPainter.SmoothPixmapTransform)
		center = QPointF(self.width() / 2, self.height() / 2)
		size = QPointF(self.width() * scale / 2, self.height() * scale / 2)
		painter.drawPixmap(QRectF(center - size, center + size), self.pixmap, self.source)


def owner_ghost(owner):
	"""The control's ghost that is still springing, if any."""
	if owner is None:
		return None
	try:
		ghost = getattr(owner, '_scale_ghost', None)
		if ghost is None or getattr(ghost, 'retired', False):
			return None
		ghost.isVisible()  # raises if Qt already deleted it
		return ghost
	except RuntimeError:
		return None


def ghost_host(widget):
	"""The nearest scroll viewport holding the control, so its ghost is clipped like the control, else the window."""
	window = widget.window()
	parent = widget.parentWidget()
	while parent is not None and parent is not window:
		area = parent.parentWidget()
		if isinstance(area, QAbstractScrollArea) and area.viewport() is parent:
			return parent
		parent = parent.parentWidget()
	return window


def ghost_rect(widget, host):
	"""Where the control sits in its host, or None when it is scrolled out of view."""
	rect = QRect(widget.mapTo(host, QPoint()), widget.size())
	return rect if rect.intersects(host.rect()) else None


def snapshot(widget):
	"""The control alone on a transparent background, so it never drags a box of window colour over its neighbours."""
	ratio = widget.devicePixelRatioF()
	pixmap = QPixmap(max(1, round(widget.width() * ratio)), max(1, round(widget.height() * ratio)))
	pixmap.setDevicePixelRatio(ratio)
	pixmap.fill(Qt.transparent)
	widget.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
	return pixmap


def ghost_on_hide(widget):
	"""When the layout hides a control, or the small row holding it, shrink a snapshot where it was."""
	window = widget.window()
	if widget is window or not window.isVisible() or isinstance(widget, ScaleGhost):
		return
	hidden = widget
	while hidden is not None and hidden is not window and not hidden.isHidden():
		hidden = hidden.parentWidget()
	if hidden is None or hidden is window:
		return
	parent = hidden.parentWidget()
	if parent is None or not parent.isVisible() or isinstance(parent, QStackedWidget):
		return
	if hidden is not widget and hidden.height() > max(160, 3 * widget.height()):
		return
	now = time.monotonic()
	if now - getattr(hidden, '_ghost_at', 0) < .1:
		return
	hidden._ghost_at = now
	if hidden.width() <= 0 or hidden.height() <= 0:
		return
	if not getattr(hidden, 'own_appear_animation', False):
		hidden._hidden_by_layout = True
	shrink_away(hidden)


def grow_on_show(widget):
	"""A control the layout hid earlier springs back in from nothing when it reappears."""
	window = widget.window()
	shown = widget
	while shown is not None and shown is not window and not getattr(shown, '_hidden_by_layout', False):
		shown = shown.parentWidget()
	if shown is None or shown is window or not window.isVisible():
		return
	shown._hidden_by_layout = False
	veil(shown)
	QTimer.singleShot(0, lambda: grow_widget(shown))


def veil(widget):
	"""Hide a control's paint at once, keeping any opacity effect it already uses, until its snapshot has grown."""
	if getattr(widget, '_veil', None) is not None:
		return widget._veil
	effect = widget.graphicsEffect()
	if effect is not None and not isinstance(effect, QGraphicsOpacityEffect):
		return None
	if effect is None:
		effect = QGraphicsOpacityEffect(widget)
		widget.setGraphicsEffect(effect)
		restore = None
	else:
		restore = effect.opacity()
	effect.setOpacity(0)
	widget._veil = (effect, restore)
	return widget._veil


def lift_veil(widget):
	try:
		effect, restore = widget._veil
		widget._veil = None
		if widget.graphicsEffect() is effect:
			if restore is None:
				widget.setGraphicsEffect(None)
			else:
				effect.setOpacity(restore)
	except (RuntimeError, AttributeError, TypeError):
		pass


def grow_widget(widget, parent=None, rect=None):
	try:
		if not widget.isVisible() or widget.width() <= 0 or getattr(widget, '_growing', False):
			lift_veil(widget)
			return
	except RuntimeError:
		return
	veiled = veil(widget)
	if veiled is None:
		return
	effect, restore = veiled
	parent = parent or ghost_host(widget)
	rect = rect or ghost_rect(widget, parent)
	if rect is None:
		lift_veil(widget)
		return
	effect.setOpacity(1 if restore is None else restore)
	pixmap = snapshot(widget)
	effect.setOpacity(0)
	widget._growing = True

	def reveal():
		widget._growing = False
		lift_veil(widget)
	ScaleGhost(parent, pixmap, rect, grow=True, finished=reveal, follow=widget, owner=widget)


def show_with_grow(widget):
	if not widget.isHidden():
		return
	window = widget.window()
	if window.isVisible():
		veil(widget)
		widget.show()
		QTimer.singleShot(0, lambda: grow_widget(widget))
	else:
		widget.show()


def hide_with_shrink(widget):
	if widget.isHidden():
		return
	window = widget.window()
	if window.isVisible() and widget.isVisible() and widget.width() > 0:
		shrink_away(widget)
	widget.hide()


def shrink_away(widget):
	"""Shrink a snapshot of the control in its own row, under the controls that stay, unless it is
	scrolled out of view."""
	if ghost_rect(widget, ghost_host(widget)) is not None:
		ScaleGhost(widget.parentWidget(), snapshot(widget), widget.geometry(), owner=widget, below=True)
