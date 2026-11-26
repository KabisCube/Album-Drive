"""Turn mouse-wheel turns into whole scroll steps, one per click, whatever the system's scroll speed."""
import time

FULL_NOTCH = 120  # Qt's angleDelta for one click at normal speed.
# Pieces of one high-resolution click arrive within a few milliseconds; separate clicks come further apart.
NOTCH_GAP = .08


class WheelSteps:
	"""A slowed-down system scroll speed hands out less than a full notch per click, so plain adding-up
	would need several clicks per step. Instead, the first piece after a pause moves a step at once, and
	any pieces that follow in the same quick burst only pay that step off, so a high-resolution wheel's
	many small pieces still make one step per click."""

	def __init__(self, notch=FULL_NOTCH):
		self.notch = notch
		self.remainder = 0
		self.direction = 0
		self.last = 0.0

	def reset(self):
		self.remainder = 0
		self.direction = 0

	def add(self, delta, now=None):
		if not delta:
			return 0
		now = time.monotonic() if now is None else now
		direction = 1 if delta > 0 else -1
		fresh = now - self.last > NOTCH_GAP or direction != self.direction
		self.last, self.direction = now, direction
		if fresh:
			self.remainder = 0
		self.remainder += delta
		steps = int(self.remainder / self.notch)
		self.remainder -= steps * self.notch
		if not steps and fresh:
			steps = direction
			self.remainder -= steps * self.notch
		return steps
