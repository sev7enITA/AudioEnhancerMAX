"""
AudioEnhancerMAX by Fd - Adaptive Timing Engine
Tracks real processing times per filter/operation, persists to disk,
and provides calibrated estimates using historical data.

3-Level Estimation:
  Level 1: Static benchmarks (first run, no history)
  Level 2: Server-side per-step progress + live ETA via WebSocket
  Level 3: Adaptive history (accumulated real timing data)
"""
import json
import time
import logging
import threading
from typing import Dict, List, Optional, Tuple

from app.config import TIMING_HISTORY_FILE

logger = logging.getLogger(__name__)

# ── Persistence path ──
HISTORY_FILE = TIMING_HISTORY_FILE

# ── Static benchmarks: seconds per 60s of audio (M3 MAX calibrated) ──
STATIC_BENCHMARKS = {
    # Noise filters
    "remove_noise":           {"secs_per_60": 8.0,   "model_load": 5.0,   "group": "deepfilter"},
    "wind_noise_remover":     {"secs_per_60": 2.5,   "model_load": 0.0,   "group": "dsp"},
    "buzzing_noise_remover":  {"secs_per_60": 0.5,   "model_load": 0.0,   "group": "dsp"},
    "static_noise_remover":   {"secs_per_60": 2.5,   "model_load": 0.0,   "group": "dsp"},
    "reverb_echo_remover":    {"secs_per_60": 4.0,   "model_load": 0.0,   "group": "dsp"},
    # Speech cleanup (Whisper-based)
    "remove_filler_words":    {"secs_per_60": 35.0,  "model_load": 12.0,  "group": "whisper"},
    "eliminate_hesitations":  {"secs_per_60": 35.0,  "model_load": 12.0,  "group": "whisper"},
    "remove_stuttering":      {"secs_per_60": 35.0,  "model_load": 12.0,  "group": "whisper"},
    # Speech cleanup (DSP)
    "remove_mouth_sounds":    {"secs_per_60": 2.0,   "model_load": 0.0,   "group": "dsp"},
    "remove_breaths":         {"secs_per_60": 3.0,   "model_load": 0.0,   "group": "dsp"},
    # Silence
    "remove_long_silences":   {"secs_per_60": 1.0,   "model_load": 0.0,   "group": "dsp"},
    # Enhancement
    "auto_eq":                {"secs_per_60": 0.3,   "model_load": 0.0,   "group": "dsp"},
    "studio_sound":           {"secs_per_60": 0.5,   "model_load": 0.0,   "group": "dsp"},
    "normalize":              {"secs_per_60": 0.3,   "model_load": 0.0,   "group": "dsp"},
    # Advanced
    "keep_music":             {"secs_per_60": 25.0,  "model_load": 8.0,   "group": "demucs"},
    "frequency_restoration":  {"secs_per_60": 5.0,   "model_load": 0.0,   "group": "dsp"},
}

# Non-filter operations
OPERATION_BENCHMARKS = {
    "transcribe":   {"secs_per_60": 90.0,  "model_load": 12.0, "group": "whisper"},
    "diarize":      {"secs_per_60": 1.5,   "model_load": 5.0,  "group": "diarization"},
    "tts":          {"secs_per_60": 0.0,   "model_load": 15.0, "group": "tts"},
    "smart_mode":   {"secs_per_60": 0.0,   "model_load": 12.0, "group": "gemma"},
}

# Maximum history samples per key
MAX_SAMPLES = 20


class TimingEngine:
    """
    Adaptive timing engine that learns from actual processing times.
    Thread-safe, persists data to disk.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._history: Dict = {"filter_timings": {}, "operation_timings": {}}
        self._active_steps: Dict[str, Dict] = {}  # job_id -> {step_name: start_time}
        self._job_meta: Dict[str, Dict] = {}       # job_id -> {audio_duration, steps_estimates, ...}
        self._groups_loaded: set = set()            # model groups loaded this session
        self._load_history()

    # ══════════════════════════════════════════════════════════
    # Persistence
    # ══════════════════════════════════════════════════════════

    def _load_history(self):
        """Load timing history from disk."""
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r") as f:
                    data = json.load(f)
                self._history = data
                total = sum(len(v.get("samples", [])) for v in data.get("filter_timings", {}).values())
                total += sum(len(v.get("samples", [])) for v in data.get("operation_timings", {}).values())
                logger.info(f" Timing history loaded: {total} samples from {HISTORY_FILE}")
        except Exception as e:
            logger.warning(f"Could not load timing history: {e}")

    def _save_history(self):
        """Persist timing history to disk."""
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(self._history, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save timing history: {e}")

    # ══════════════════════════════════════════════════════════
    # Step Tracking (called during processing)
    # ══════════════════════════════════════════════════════════

    def start_job(self, job_id: str, audio_duration: float, active_steps: List[str]):
        """Register a new processing job."""
        with self._lock:
            self._active_steps[job_id] = {}
            estimates = self.get_adaptive_estimate(active_steps, audio_duration)
            self._job_meta[job_id] = {
                "audio_duration": audio_duration,
                "active_steps": active_steps,
                "start_time": time.monotonic(),
                "estimates": estimates,
                "completed_steps": [],
                "step_actuals": {},
            }
        return estimates

    def start_step(self, job_id: str, step_name: str):
        """Mark the start of a processing step."""
        with self._lock:
            if job_id not in self._active_steps:
                self._active_steps[job_id] = {}
            self._active_steps[job_id][step_name] = time.monotonic()

    def end_step(self, job_id: str, step_name: str):
        """Mark the end of a processing step and record the elapsed time."""
        with self._lock:
            if job_id not in self._active_steps:
                return 0.0
            start = self._active_steps[job_id].pop(step_name, None)
            if start is None:
                return 0.0

            elapsed = time.monotonic() - start
            audio_dur = self._job_meta.get(job_id, {}).get("audio_duration", 60.0)

            # Record in job meta
            if job_id in self._job_meta:
                self._job_meta[job_id]["step_actuals"][step_name] = elapsed
                self._job_meta[job_id]["completed_steps"].append(step_name)

            # Persist to history
            self._record_timing("filter_timings", step_name, audio_dur, elapsed)

            return elapsed

    def end_job(self, job_id: str):
        """Finalize a job and persist all data."""
        with self._lock:
            meta = self._job_meta.pop(job_id, None)
            self._active_steps.pop(job_id, None)

            if meta:
                total_elapsed = time.monotonic() - meta["start_time"]
                logger.info(
                    f" Job {job_id[:8]} complete: {total_elapsed:.1f}s total, "
                    f"{len(meta['completed_steps'])} steps"
                )

            self._save_history()

    def record_operation(self, operation: str, audio_duration: float, elapsed: float):
        """Record timing for a non-filter operation (transcription, diarization, etc.)."""
        with self._lock:
            self._record_timing("operation_timings", operation, audio_duration, elapsed)
            self._save_history()

    def _record_timing(self, category: str, key: str, audio_duration: float, elapsed: float):
        """Internal: add a timing sample."""
        if category not in self._history:
            self._history[category] = {}
        if key not in self._history[category]:
            self._history[category][key] = {"samples": []}

        samples = self._history[category][key]["samples"]
        samples.append({
            "audio_duration": round(audio_duration, 2),
            "elapsed": round(elapsed, 3),
            "timestamp": time.time(),
        })

        # Keep only the most recent samples
        if len(samples) > MAX_SAMPLES:
            self._history[category][key]["samples"] = samples[-MAX_SAMPLES:]

    # ══════════════════════════════════════════════════════════
    # Estimation
    # ══════════════════════════════════════════════════════════

    def mark_group_loaded(self, group: str):
        """Mark a model group as already loaded (skip load cost on next estimate)."""
        self._groups_loaded.add(group)

    def get_adaptive_estimate(
        self, active_steps: List[str], audio_duration: float
    ) -> Dict:
        """
        Compute a calibrated estimate for a set of processing steps.

        Returns:
        {
            "total_seconds": float,
            "confidence": "high" | "medium" | "low",
            "source": "history" | "benchmark",
            "per_step": {
                "remove_noise": {"estimated_seconds": 8.2, "source": "history", "confidence": "high"},
                ...
            },
            "breakdown_text": "16 filtri - stima calibrata su 12 esecuzioni precedenti",
        }
        """
        total = 2.0  # base I/O overhead
        per_step = {}
        groups_costed = set()
        history_count = 0
        benchmark_count = 0

        for step in active_steps:
            est, source, conf = self._estimate_single_step(step, audio_duration, groups_costed)
            per_step[step] = {
                "estimated_seconds": round(est, 1),
                "source": source,
                "confidence": conf,
            }
            total += est
            if source == "history":
                history_count += 1
            else:
                benchmark_count += 1

        # Overall confidence
        if history_count > 0 and benchmark_count == 0:
            confidence = "high"
            source = "history"
        elif history_count > benchmark_count:
            confidence = "medium"
            source = "history+benchmark"
        else:
            confidence = "low"
            source = "benchmark"

        # Human-readable summary
        total_steps = len(active_steps)
        if confidence == "high":
            n = self._get_sample_count(active_steps)
            breakdown_text = (
                f"{total_steps} filtri - stima calibrata su {n} esecuzioni precedenti "
                f"per {self._fmt_duration(audio_duration)} di audio"
            )
        elif confidence == "medium":
            breakdown_text = (
                f"{total_steps} filtri - stima mista (dati reali + benchmark) "
                f"per {self._fmt_duration(audio_duration)} di audio"
            )
        else:
            breakdown_text = (
                f"{total_steps} filtri - stima iniziale da benchmark M3 MAX "
                f"per {self._fmt_duration(audio_duration)} di audio"
            )

        return {
            "total_seconds": round(total, 1),
            "confidence": confidence,
            "source": source,
            "per_step": per_step,
            "breakdown_text": breakdown_text,
            "audio_duration": round(audio_duration, 1),
        }

    def estimate_operation(self, operation: str, audio_duration: float) -> Dict:
        """
        Estimate time for a non-filter operation (transcribe, diarize, tts, smart_mode).
        """
        samples = self._get_samples("operation_timings", operation)

        if len(samples) >= 2:
            est = self._interpolate(samples, audio_duration)
            confidence = "high" if len(samples) >= 5 else "medium"
            source = "history"
            reason = (
                f"Stima calibrata su {len(samples)} esecuzioni precedenti "
                f"per {self._fmt_duration(audio_duration)} di audio"
            )
        elif len(samples) == 1:
            # Single sample: scale proportionally
            s = samples[0]
            ratio = audio_duration / max(s["audio_duration"], 1)
            est = s["elapsed"] * ratio
            confidence = "low"
            source = "history"
            reason = f"Stima basata su 1 esecuzione precedente - bassa confidenza"
        else:
            # Fall back to static benchmark
            bench = OPERATION_BENCHMARKS.get(operation, {"secs_per_60": 1.0, "model_load": 5.0})
            scale = audio_duration / 60.0
            est = bench["secs_per_60"] * scale + bench["model_load"]
            # Skip model load if already loaded
            group = bench.get("group", "")
            if group in self._groups_loaded:
                est -= bench["model_load"]
            confidence = "low"
            source = "benchmark"
            reason = (
                f"Stima iniziale da benchmark M3 MAX - "
                f"nessuna esecuzione precedente registrata"
            )

        return {
            "total_seconds": round(max(2, est), 1),
            "confidence": confidence,
            "source": source,
            "reason": reason,
            "audio_duration": round(audio_duration, 1),
        }

    def get_live_eta(self, job_id: str) -> Optional[Dict]:
        """
        Calculate live ETA for an in-progress job based on completed step actuals
        and estimates for remaining steps.
        """
        with self._lock:
            meta = self._job_meta.get(job_id)
            if not meta:
                return None

            elapsed = time.monotonic() - meta["start_time"]
            completed = set(meta["completed_steps"])
            remaining_steps = [s for s in meta["active_steps"] if s not in completed]

            # Sum actual time for completed steps
            actual_completed = sum(meta["step_actuals"].values())

            # Sum estimated time for remaining steps
            estimated_remaining = 0.0
            per_step = meta["estimates"].get("per_step", {})
            for step in remaining_steps:
                step_est = per_step.get(step, {}).get("estimated_seconds", 5.0)
                estimated_remaining += step_est

            # Total estimated = actual completed + estimated remaining
            total_estimated = actual_completed + estimated_remaining + 2.0  # I/O overhead
            remaining_seconds = max(0, total_estimated - elapsed)

            return {
                "elapsed_seconds": round(elapsed, 1),
                "remaining_seconds": round(remaining_seconds, 1),
                "total_estimated_seconds": round(total_estimated, 1),
                "completed_steps": len(completed),
                "remaining_steps": len(remaining_steps),
                "progress": min(0.99, elapsed / max(total_estimated, 1)),
            }

    # ── Internal helpers ──

    def _estimate_single_step(
        self, step: str, audio_duration: float, groups_costed: set
    ) -> Tuple[float, str, str]:
        """Estimate a single step. Returns (seconds, source, confidence)."""
        samples = self._get_samples("filter_timings", step)

        if len(samples) >= 3:
            # Enough history: interpolate
            est = self._interpolate(samples, audio_duration)
            conf = "high" if len(samples) >= 6 else "medium"
            return est, "history", conf

        if len(samples) >= 1:
            # Some history: use weighted average with benchmark
            hist_est = self._interpolate(samples, audio_duration)
            bench_est = self._benchmark_estimate(step, audio_duration, groups_costed)
            # Weight history more as we get more samples
            w = len(samples) / 3.0  # 0.33 for 1 sample, 0.66 for 2
            blended = hist_est * w + bench_est * (1 - w)
            return blended, "history+benchmark", "medium"

        # No history: pure benchmark
        est = self._benchmark_estimate(step, audio_duration, groups_costed)
        return est, "benchmark", "low"

    def _benchmark_estimate(
        self, step: str, audio_duration: float, groups_costed: set
    ) -> float:
        """Static benchmark estimate for a step."""
        bench = STATIC_BENCHMARKS.get(step, {"secs_per_60": 2.0, "model_load": 0, "group": "dsp"})
        scale = audio_duration / 60.0
        est = bench["secs_per_60"] * scale

        group = bench["group"]
        load_cost = bench["model_load"]
        if load_cost > 0 and group not in groups_costed and group not in self._groups_loaded:
            est += load_cost
            groups_costed.add(group)

        return est

    def _interpolate(self, samples: List[Dict], audio_duration: float) -> float:
        """
        Weighted linear interpolation from historical samples.
        More recent samples get higher weight.
        """
        if not samples:
            return 5.0

        if len(samples) == 1:
            s = samples[0]
            ratio = audio_duration / max(s["audio_duration"], 1)
            return s["elapsed"] * max(0.1, ratio)

        # Weighted linear regression (more recent = heavier weight)
        n = len(samples)
        weights = [0.5 + 0.5 * (i / (n - 1)) for i in range(n)]  # 0.5 to 1.0

        # Calculate weighted means
        sum_w = sum(weights)
        mean_x = sum(w * s["audio_duration"] for w, s in zip(weights, samples)) / sum_w
        mean_y = sum(w * s["elapsed"] for w, s in zip(weights, samples)) / sum_w

        # Weighted slope
        num = sum(w * (s["audio_duration"] - mean_x) * (s["elapsed"] - mean_y)
                  for w, s in zip(weights, samples))
        den = sum(w * (s["audio_duration"] - mean_x) ** 2
                  for w, s in zip(weights, samples))

        if abs(den) < 1e-10:
            # All samples at same duration, use weighted mean
            return mean_y

        slope = num / den
        intercept = mean_y - slope * mean_x

        est = intercept + slope * audio_duration
        return max(0.5, est)  # minimum 0.5s

    def _get_samples(self, category: str, key: str) -> List[Dict]:
        """Get historical samples for a key."""
        return self._history.get(category, {}).get(key, {}).get("samples", [])

    def _get_sample_count(self, steps: List[str]) -> int:
        """Get average sample count across steps."""
        counts = [len(self._get_samples("filter_timings", s)) for s in steps]
        return round(sum(counts) / max(len(counts), 1))

    def _fmt_duration(self, seconds: float) -> str:
        """Format seconds as human-readable duration."""
        if seconds < 60:
            return f"{int(seconds)}s"
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"

    def get_history_summary(self) -> Dict:
        """Return a summary of stored timing data for the API."""
        summary = {"filters": {}, "operations": {}}
        for key, data in self._history.get("filter_timings", {}).items():
            samples = data.get("samples", [])
            if samples:
                durations = [s["elapsed"] for s in samples]
                audio_durs = [s["audio_duration"] for s in samples]
                summary["filters"][key] = {
                    "sample_count": len(samples),
                    "avg_elapsed": round(sum(durations) / len(durations), 2),
                    "min_elapsed": round(min(durations), 2),
                    "max_elapsed": round(max(durations), 2),
                    "avg_audio_duration": round(sum(audio_durs) / len(audio_durs), 1),
                }
        for key, data in self._history.get("operation_timings", {}).items():
            samples = data.get("samples", [])
            if samples:
                durations = [s["elapsed"] for s in samples]
                summary["operations"][key] = {
                    "sample_count": len(samples),
                    "avg_elapsed": round(sum(durations) / len(durations), 2),
                }
        return summary


# ── Global singleton ──
timing_engine = TimingEngine()
