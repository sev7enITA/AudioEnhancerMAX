"""Bounded, untrusted client telemetry. This is not hardware attestation."""

import base64
import json
import math


def parse_assessment(raw):
    if not isinstance(raw, str) or len(raw) > 4096:
        return {}
    try:
        value = json.loads(base64.b64decode(raw, validate=True))
    except (ValueError, UnicodeError):
        return {}
    if not isinstance(value, dict) or value.get("schema") != 1:
        return {}
    result = {"schema": 1, "source": "device-reported"}
    for key in ("model", "os", "thermal", "benchmark_at"):
        text = value.get(key)
        if isinstance(text, str):
            result[key] = "".join(c for c in text if c.isprintable())[:100]
    for key, lo, hi in [
        ("ram_bytes", 1, 2**40),
        ("available_bytes", 0, 2**40),
        ("battery_percent", 0, 100),
        ("voice_eq_ms", 0.01, 60000),
        ("round_trip_ms", 0, 120000),
    ]:
        number = value.get(key)
        if (
            isinstance(number, (int, float))
            and not isinstance(number, bool)
            and lo <= number <= hi
            and math.isfinite(number)
        ):
            result[key] = number
    # Only this fixed workload has a comparable time unit. Never rank general AI capability.
    if value.get("benchmark") != "voice-eq-2s-48k-mono-v1":
        result.pop("voice_eq_ms", None)
        result.pop("benchmark_at", None)
    elif "voice_eq_ms" in result:
        result["benchmark"] = value["benchmark"]
    if isinstance(value.get("charging"), bool):
        result["charging"] = value["charging"]
    return result
