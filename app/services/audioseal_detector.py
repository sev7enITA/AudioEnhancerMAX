"""Optional diagnostic for Meta's AudioSeal 16-bit watermark on a local preview."""
import hashlib
import os
import stat

import numpy as np

from app.config import DATA_DIR

MODEL_NAME = "audioseal-detector.onnx"
MODEL_SHA256 = "3ff3991c4bf4426c5aed8b122610833cb4cd7e02535d6edeae6380199f809ca2"
MODEL_SIZE = 34_759_744
MODEL_REVISION = "aacb1186bedc8118960e5ce8a7849861bf9a4c6c"
RATE = 16_000
MINIMUM_SECONDS = 1
MAXIMUM_SECONDS = 10
HOP = 320


def _verified_model() -> bytes | None:
    path = DATA_DIR / "models" / MODEL_NAME
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != MODEL_SIZE:
            return None
        data = stream.read(MODEL_SIZE + 1)
    if len(data) == MODEL_SIZE and hashlib.sha256(data).hexdigest() == MODEL_SHA256:
        return data
    return None


def frame_scores(model: bytes, samples: np.ndarray) -> np.ndarray:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(model, sess_options=options, providers=["CPUExecutionProvider"])
    padded = np.pad(samples, (0, (-len(samples)) % HOP))
    scores = session.run(["detection"], {"audio": padded.reshape(1, 1, -1)})[0]
    if scores.shape != (1, 2, len(padded)):
        raise ValueError("Unexpected AudioSeal output")
    scores = scores[0, 1, :len(samples)]
    if not np.isfinite(scores).all() or scores.min() < 0 or scores.max() > 1:
        raise ValueError("Invalid AudioSeal output")
    return scores


def evaluate(samples: np.ndarray, source_rate: int) -> dict:
    from scipy.signal import resample_poly

    if len(samples) < source_rate * MINIMUM_SECONDS:
        return {"status": "audio_too_short"}
    samples = samples[:source_rate * MAXIMUM_SECONDS]
    try:
        model = _verified_model()
        if model is None:
            return {"status": "detector_unavailable"}
        mono = resample_poly(samples, RATE, source_rate)
        mono = np.clip(mono, -1, 1).astype(np.float32)
        scores = frame_scores(model, mono)
    except Exception:
        return {"status": "measurement_failed"}
    return {
        "status": "measured",
        "scheme": "Meta AudioSeal 16-bit",
        "method": "first_audio_track_mono_16khz_prefix_v1",
        "model_sha256": MODEL_SHA256,
        "model_revision": MODEL_REVISION,
        "analyzed_seconds": round(len(mono) / RATE, 5),
        "signal_frame_threshold": 0.5,
        "fraction_above_signal_threshold": round(float(np.mean(scores > 0.5)), 5),
        "experimental": True,
    }
