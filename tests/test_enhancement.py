from __future__ import annotations

import numpy as np

from app.services.enhancement import apply_auto_eq


def test_auto_eq_preserves_audible_signal_at_16_khz() -> None:
    """Regression: out-of-band fixed filters must not collapse voice notes."""
    sample_rate = 16_000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    source = (0.35 * np.sin(2 * np.pi * 440.0 * time)).astype(np.float32)

    processed = apply_auto_eq(source, sample_rate)

    assert processed.shape == source.shape
    assert np.isfinite(processed).all()
    source_rms = float(np.sqrt(np.mean(np.square(source))))
    processed_rms = float(np.sqrt(np.mean(np.square(processed))))
    assert processed_rms > source_rms * 0.25
