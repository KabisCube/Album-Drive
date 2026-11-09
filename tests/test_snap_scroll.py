import unittest

from snap_scroll import SnapPager, SpringScroll


def pager(widths, room, arrow=10):
    extents, x = [], 0
    for width in widths:
        extents.append((x, x + width))
        x += width
    result = SnapPager()
    result.update(extents, room, arrow)
    return result


class SnapPagerTests(unittest.TestCase):
    def test_everything_fits_without_arrows(self):
        page = pager([30, 30, 30], 90)
        self.assertEqual((page.start, page.end, page.left_arrow, page.right_arrow), (0, 3, 0, 0))
        self.assertEqual(page.maximum, 0)

    def test_pages_hold_only_whole_items(self):
        page = pager([30, 30, 30, 30, 30], 75)
        self.assertEqual((page.start, page.end, page.right_arrow), (0, 2, 10))
        self.assertLessEqual(page.page_width, page.room - page.right_arrow)
        page.scroll(1)
        self.assertEqual(page.start, 2)
        self.assertEqual(page.left_arrow, 10)
        self.assertLessEqual(page.page_width, page.room - page.left_arrow - page.right_arrow)

    def test_scrolling_reaches_both_ends(self):
        page = pager([30] * 7, 75)
        for _ in range(10):
            page.scroll(1)
        self.assertEqual(page.end, 7)
        self.assertFalse(page.right_arrow)
        self.assertEqual(page.target, page.maximum)
        for _ in range(10):
            page.scroll(-1)
        self.assertEqual((page.start, page.target), (0, 0))
        self.assertFalse(page.left_arrow)

    def test_an_item_wider_than_the_room_still_shows(self):
        page = pager([200, 30], 60)
        self.assertEqual((page.start, page.end), (0, 1))
        page.scroll(1)
        self.assertEqual((page.start, page.end), (1, 2))

    def test_reveal_brings_an_item_onto_the_page(self):
        page = pager([30] * 8, 75)
        page.reveal(6)
        self.assertTrue(page.start <= 6 < page.end)
        page.reveal(0)
        self.assertEqual(page.start, 0)

    def test_growing_the_room_pulls_earlier_items_back(self):
        page = pager([30] * 6, 75)
        for _ in range(5):
            page.scroll(1)
        page.update(page.extents, 160, page.arrow)
        self.assertEqual(page.end, 6)
        self.assertLessEqual(page.page_width, 160 - page.left_arrow)
        self.assertGreater(page.page_width, 160 - page.left_arrow - 30)


class SpringTests(unittest.TestCase):
    def test_glide_settles_on_target_without_overshoot(self):
        class Frames:
            def restart(self):
                return 16

        spring = SpringScroll()
        spring.jump(0)
        spring.target = 300.0
        spring.clock = Frames()
        positions = []
        for _ in range(200):
            spring.step()
            positions.append(spring.value)
            if spring.value == spring.target and spring.velocity == 0:
                break
        self.assertEqual(spring.value, 300.0)
        self.assertTrue(all(value <= 300.0 for value in positions))
        self.assertTrue(all(b >= a for a, b in zip(positions, positions[1:])))
        self.assertLess(len(positions), 60)


if __name__ == '__main__':
    unittest.main()
