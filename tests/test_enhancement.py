from __future__ import annotations

import numpy as np
import pytest

from app.services.enhancement import apply_auto_eq, normalize_volume


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

@pytest.mark.parametrize("channels", [1, 2])
def test_normalize_volume_falls_back_for_short_audio(channels: int) -> None:
    sample_rate = 16_000
    source = np.linspace(-0.25, 0.25, 1600, dtype=np.float32)
    if channels == 2:
        source = np.column_stack((source, source / 2))

    processed = normalize_volume(source, sample_rate)

    assert processed.shape == source.shape
    assert np.max(np.abs(processed)) == pytest.approx(10 ** (-1 / 20))
    if channels == 2:
        np.testing.assert_allclose(processed[:, 1], processed[:, 0] / 2)
