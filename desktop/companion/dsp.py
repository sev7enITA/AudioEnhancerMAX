"""Portable Voice EQ v1: identical RBJ stages and float32 stage output on all peers."""

from array import array
import math

STAGES = [
    ("highpass", 80, 0.707, 0),
    ("lowShelf", 150, 0.707, 1),
    ("peak", 250, 1, -1.5),
    ("peak", 2500, 1, 1.5),
    ("peak", 5000, 0.7, 1),
    ("highShelf", 8000, 0.707, 0.5),
    ("lowpass", 16000, 0.707, 0),
]


def voice_eq(samples, rate, channels=1):
    values = array("f", samples)
    if (
        not 8000 <= rate <= 96000
        or channels not in (1, 2)
        or not values
        or len(values) % channels
        or not all(math.isfinite(v) for v in values)
    ):
        raise ValueError("Invalid audio layout")
    for kind, f, q, g in STAGES:
        w = 2 * math.pi * min(f, rate * 0.45) / rate
        c = math.cos(w)
        a = math.sin(w) / (2 * q)
        A = 10 ** (g / 40)
        r = 2 * math.sqrt(A) * a
        if kind == "highpass":
            b0, b1, b2, a0, a1, a2 = (
                (1 + c) / 2,
                -(1 + c),
                (1 + c) / 2,
                1 + a,
                -2 * c,
                1 - a,
            )
        elif kind == "lowpass":
            b0, b1, b2, a0, a1, a2 = (
                (1 - c) / 2,
                1 - c,
                (1 - c) / 2,
                1 + a,
                -2 * c,
                1 - a,
            )
        elif kind == "lowShelf":
            b0, b1, b2, a0, a1, a2 = (
                A * ((A + 1) - (A - 1) * c + r),
                2 * A * ((A - 1) - (A + 1) * c),
                A * ((A + 1) - (A - 1) * c - r),
                (A + 1) + (A - 1) * c + r,
                -2 * ((A - 1) + (A + 1) * c),
                (A + 1) + (A - 1) * c - r,
            )
        elif kind == "highShelf":
            b0, b1, b2, a0, a1, a2 = (
                A * ((A + 1) + (A - 1) * c + r),
                -2 * A * ((A - 1) + (A + 1) * c),
                A * ((A + 1) + (A - 1) * c - r),
                (A + 1) - (A - 1) * c + r,
                2 * ((A - 1) - (A + 1) * c),
                (A + 1) - (A - 1) * c - r,
            )
        else:
            b0, b1, b2, a0, a1, a2 = (
                1 + a * A,
                -2 * c,
                1 - a * A,
                1 + a / A,
                -2 * c,
                1 - a / A,
            )
        for ch in range(channels):
            x1 = x2 = y1 = y2 = 0.0
            for i in range(ch, len(values), channels):
                x = values[i]
                y = (b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2) / a0
                x2, x1, y2, y1 = x1, x, y1, y
                values[i] = y
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Non-finite output")
    return values
