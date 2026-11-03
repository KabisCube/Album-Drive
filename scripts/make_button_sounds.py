"""Generate original, deterministic mouse-to-mechanical button click samples."""

import math
from pathlib import Path
import random
import struct
import wave

SAMPLE_RATE = 44100
DURATION = .11


def click_samples(depth):
    randomizer = random.Random(702)
    blend = (depth - 1) / 11
    blend = blend * blend * (3 - 2 * blend)
    previous_noise = 0
    for index in range(round(SAMPLE_RATE * DURATION)):
        time = index / SAMPLE_RATE
        noise = randomizer.uniform(-1, 1)
        bright_noise = (noise - previous_noise) / 2
        previous_noise = noise
        mouse = 0
        for offset, strength in ((.001, 1), (.014, .45)):
            age = time - offset
            if age >= 0:
                mouse += strength * (bright_noise * .65 + math.sin(2 * math.pi * 2800 * age) * .35) * math.exp(-age / .0018)
        mechanical = 0
        # A click-jacket snap, short plastic bottom-out, then a lighter reset.
        # Avoid low resonant tones: those make a key sound like a wooden knock.
        for offset, strength, pitch, decay in ((.001, 1, 3300, .0013),
                                               (.008, .55, 1800, .0022),
                                               (.038, .6, 4200, .0015)):
            age = time - offset
            if age >= 0:
                mechanical += strength * (
                    (.70 * bright_noise + .24 * math.sin(2 * math.pi * pitch * age)) * math.exp(-age / decay)
                    + .045 * math.sin(2 * math.pi * 1250 * age) * math.exp(-age / .0035)
                    + .018 * math.sin(2 * math.pi * 6400 * age) * math.exp(-age / .005))
        envelope = min(1, time / .0005, (DURATION - time) / .008)
        yield ((1 - blend) * mouse + blend * mechanical) * envelope


def pitched_samples(samples, depth):
    """Shift the whole click, including its noise, from bright to lower-pitched."""
    ratio = 1.3 * (.55 / 1.3) ** ((depth - 1) / 11)
    darkness = (depth - 1) / 11
    # Progressive low-pass filtering takes the sharp edge off thick keys
    # without reintroducing the low, ringing tones of the earlier knock.
    smoothing = .95 - .60 * darkness
    filtered = 0
    for index in range(len(samples)):
        position = index * ratio
        first = int(position)
        if first + 1 >= len(samples):
            sample = 0
        else:
            fraction = position - first
            sample = samples[first] * (1 - fraction) + samples[first + 1] * fraction
        filtered += smoothing * (sample - filtered)
        fade = min(1, (len(samples) - index - 1) / (SAMPLE_RATE * .004))
        yield filtered * fade


def main():
    target = Path(__file__).resolve().parents[1] / 'assets' / 'sounds'
    target.mkdir(parents=True, exist_ok=True)
    for depth in range(1, 13):
        samples = list(pitched_samples(list(click_samples(depth)), depth))
        gain = .65 / max(abs(sample) for sample in samples)
        data = b''.join(struct.pack('<h', round(sample * gain * 32767)) for sample in samples)
        with wave.open(str(target / f'button-{depth:02}.wav'), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)
            output.writeframes(data)
    print('Generated 12 button sounds in', target)


if __name__ == '__main__':
    main()
