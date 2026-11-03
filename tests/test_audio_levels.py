"""The volume taper preserves endpoints and makes quiet levels easier to select."""

import unittest

from audio_levels import volume_gain


class VolumeTests(unittest.TestCase):
    def test_mute_full_volume_and_bounds(self):
        self.assertEqual(volume_gain(0), 0)
        self.assertEqual(volume_gain(100), 1)
        self.assertEqual(volume_gain(-20), 0)
        self.assertEqual(volume_gain(120), 1)

    def test_more_control_at_quiet_levels(self):
        self.assertEqual(volume_gain(50), .25)
        self.assertEqual(volume_gain(25), .0625)
        values = [volume_gain(i) for i in range(101)]
        self.assertTrue(all(a < b for a, b in zip(values, values[1:])))
        self.assertLess(volume_gain(11) - volume_gain(10), volume_gain(91) - volume_gain(90))


if __name__ == '__main__':
    unittest.main()
