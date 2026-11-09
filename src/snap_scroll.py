"""Page scrolling for rows of buttons: only whole buttons are shown, and arrows glide on a damped spring.

Extents are (left, right) pairs in row coordinates. A page starts at one item and holds every following
item that fits completely; arrow buttons take room from the row only while there is somewhere to go.
"""

import math

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, Signal

SPRING_FREQUENCY = 10.0
SETTLE_DISTANCE = .5
SETTLE_SPEED = 4.0
STEP_SECONDS = .004


class SpringScroll(QObject):
    moved = Signal()

    def __init__(self, parent=None, frequency=SPRING_FREQUENCY, damping=1.0,
                 settle_distance=SETTLE_DISTANCE, settle_speed=SETTLE_SPEED):
        super().__init__(parent)
        self.frequency = frequency
        self.damping = damping
        self.settle_distance = settle_distance
        self.settle_speed = settle_speed
        self.value = 0.0
        self.target = 0.0
        self.velocity = 0.0
        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.step)

    @property
    def moving(self):
        return self.timer.isActive()

    def jump(self, value):
        self.timer.stop()
        self.value = self.target = float(value)
        self.velocity = 0.0
        self.moved.emit()

    def glide(self, target):
        self.target = float(target)
        if not self.timer.isActive():
            self.clock.start()
            self.timer.start()

    def step(self):
        elapsed = min(.05, self.clock.restart() / 1000)
        distance = self.value - self.target
        frequency = self.frequency
        if self.damping >= 1:
            decay = math.exp(-frequency * elapsed)
            pull = self.velocity + frequency * distance
            distance = (distance + pull * elapsed) * decay
            self.velocity = (self.velocity - frequency * pull * elapsed) * decay
        else:
            steps = max(1, math.ceil(elapsed / STEP_SECONDS))
            for _ in range(steps):
                acceleration = -frequency * frequency * distance - 2 * self.damping * frequency * self.velocity
                self.velocity += acceleration * elapsed / steps
                distance += self.velocity * elapsed / steps
        if abs(distance) < self.settle_distance and abs(self.velocity) < self.settle_speed:
            self.timer.stop()
            distance = self.velocity = 0.0
        self.value = self.target + distance
        self.moved.emit()


class SnapPager(QObject):
    moved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spring = SpringScroll(self)
        self.spring.moved.connect(self.moved)
        self.extents = []
        self.room = 0
        self.arrow = 0
        self.start = 0
        self.end = 0
        self.left_arrow = 0
        self.right_arrow = 0

    def run_end(self, start, width):
        end = start + 1
        while end < len(self.extents) and self.extents[end][1] - self.extents[start][0] <= width:
            end += 1
        return end

    def page(self, start):
        count = len(self.extents)
        if not count or self.extents[-1][1] - self.extents[0][0] <= self.room:
            return 0, count, 0, 0
        start = max(0, min(start, count - 1))
        left = self.arrow if start else 0
        end = self.run_end(start, self.room - left)
        if end < count:
            return start, self.run_end(start, self.room - left - self.arrow), left, self.arrow
        while start:
            margin = self.arrow if start > 1 else 0
            if self.extents[-1][1] - self.extents[start - 1][0] > self.room - margin:
                break
            start -= 1
            left = margin
        return start, count, left, 0

    def offset_of(self, start):
        return self.extents[start][0] - self.extents[0][0] if self.extents else 0

    def update(self, extents, room, arrow, animate=False):
        self.extents, self.room, self.arrow = list(extents), room, arrow
        self.start, self.end, self.left_arrow, self.right_arrow = self.page(self.start)
        target = self.offset_of(self.start)
        if animate or self.spring.moving:
            self.spring.glide(target)
        elif self.spring.value != target:
            self.spring.jump(target)

    def scroll(self, direction):
        if direction > 0 and self.right_arrow:
            self.start = self.end
        elif direction < 0 and self.start:
            self.start = self.page_ending_at(self.start)
        else:
            return
        self.update(self.extents, self.room, self.arrow, animate=True)

    def reveal(self, index):
        if not 0 <= index < len(self.extents) or self.start <= index < self.end:
            return
        self.start = index if index < self.start else self.page_ending_at(index + 1)
        self.update(self.extents, self.room, self.arrow, animate=True)

    def page_ending_at(self, end):
        width = self.room - 2 * self.arrow
        start = end - 1
        while start > 0 and self.extents[end - 1][1] - self.extents[start - 1][0] <= width:
            start -= 1
        return start

    def reset(self):
        self.start = 0
        self.update(self.extents, self.room, self.arrow)

    @property
    def offset(self):
        return self.spring.value

    @property
    def target(self):
        return self.offset_of(self.start)

    @property
    def maximum(self):
        return self.offset_of(self.page(len(self.extents) - 1)[0]) if self.extents else 0

    @property
    def page_width(self):
        if not self.extents:
            return 0
        return self.extents[self.end - 1][1] - self.extents[self.start][0]
