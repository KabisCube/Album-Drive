from pathlib import Path
import math
import random
import struct
import wave


def swoosh_samples(action, rate=44100):
    opening = action == 'open'
    count = round(rate * (.30 if opening else .26))
    randomizer = random.Random(217 if opening else 218)
    low = smooth = bass = 0.0
    bass_alpha = 1 - math.exp(-2 * math.pi * 180 / rate)
    samples = []
    for index in range(count):
        progress = index / (count - 1)
        cutoff = 650 + 2000 * progress if opening else 2100 - 1500 * progress
        alpha = 1 - math.exp(-2 * math.pi * cutoff / rate)
        low += alpha * (randomizer.uniform(-1, 1) - low)
        smooth += alpha * (low - smooth)
        bass += bass_alpha * (smooth - bass)
        samples.append((smooth - bass) * math.sin(math.pi * progress) ** 2)
    gain = (.26 if opening else .22) / max(abs(sample) for sample in samples)
    return [round(sample * gain * 32767) for sample in samples]


def main():
    target = Path(__file__).resolve().parents[1] / 'assets' / 'sounds'
    target.mkdir(parents=True, exist_ok=True)
    for action in ('open', 'close'):
        samples = swoosh_samples(action)
        with wave.open(str(target / f'case-{action}.wav'), 'wb') as audio:
            audio.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            audio.writeframes(struct.pack(f'<{len(samples)}h', *samples))
    print('Generated soft opening and closing swooshes in', target)


if __name__ == '__main__':
    main()
