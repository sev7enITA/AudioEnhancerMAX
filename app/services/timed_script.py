"""Read tab-separated video scripts and place their narration on a sample timeline."""
from dataclasses import dataclass
import re

import numpy as np

from app.config import MAX_FILE_SIZE_MB


class TimedScriptError(ValueError):
    """An invalid scene table or a narration that cannot fit its interval."""


_CLOCK = r"(?:[0-9]{1,4}:)?[0-9]{1,4}:[0-5][0-9](?:[.,][0-9]{1,3})?"
_INTERVAL = re.compile(rf"({_CLOCK})\s*[-\N{{EN DASH}}\N{{EM DASH}}]\s*({_CLOCK})")
_HEADERS = {("tempo", "scena", "testo"), ("time", "scene", "text")}


@dataclass(frozen=True)
class Scene:
    interval: str
    name: str
    text: str
    start_ms: int
    end_ms: int

    def row(self, narration):
        return "\t".join((self.interval, self.name, " ".join(narration.splitlines())))


def _milliseconds(clock):
    fields = clock.replace(",", ".").split(":")
    seconds, _, fraction = fields[-1].partition(".")
    if len(fields) == 3 and int(fields[1]) >= 60:
        raise TimedScriptError(f"Invalid minutes in {clock}.")
    minutes = int(fields[-2]) + (int(fields[0]) * 60 if len(fields) == 3 else 0)
    return (minutes * 60 + int(seconds)) * 1000 + int(fraction.ljust(3, "0"))


def parse_scenes(text):
    source = text.strip()
    if source.startswith('"') and source.endswith('"'):
        source = source[1:-1]
    rows = [(i, line.rstrip().removesuffix("\\").rstrip()) for i, line in
            enumerate(source.splitlines(), 1) if line.strip()]
    if not rows:
        return []
    first = rows[0][1].casefold().split("\t")
    header = tuple(cell.strip() for cell in first) in _HEADERS
    if not header and not (len(first) >= 3 and re.match(r"^\s*[0-9]+:", first[0])):
        return []
    scenes = []
    for number, row in rows[int(header):]:
        fields = row.split("\t", 2)
        interval = fields[0].strip()
        match = _INTERVAL.fullmatch(interval)
        if not match or len(fields) != 3 or not fields[2].strip():
            raise TimedScriptError(f"Row {number}: enter a time range, scene and narration separated by tabs.")
        start, end = map(_milliseconds, match.groups())
        if end <= start or (scenes and start < scenes[-1].end_ms):
            raise TimedScriptError(f"Row {number} ({interval}): each scene must have positive duration and follow the previous scene.")
        scenes.append(Scene(interval, fields[1].strip(), fields[2].strip(), start, end))
    if not scenes:
        raise TimedScriptError("Add at least one scene below the table header.")
    return scenes


def rewrite_script(text, rewrite):
    scenes = parse_scenes(text)
    if not scenes:
        return rewrite(text)
    revised = [rewrite(scene.text) for scene in scenes]
    if all(new == scene.text for new, scene in zip(revised, scenes)):
        return text
    return "\n".join(scene.row(new) for scene, new in zip(scenes, revised))


def render_scenes(scenes, synthesize):
    from pedalboard import time_stretch

    timeline = None
    rewrites = []
    accelerated = 0
    for scene in scenes:
        audio, rate, metadata = synthesize(scene.text)
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim != 1 or not audio.size:
            raise RuntimeError(f"No mono narration available for {scene.interval}.")
        if timeline is None:
            sample_rate = rate
            frames = round(scenes[-1].end_ms * rate / 1000)
            if frames * audio.itemsize > MAX_FILE_SIZE_MB * 1024**2:
                raise TimedScriptError("The final timestamp exceeds the maximum audio size.")
            timeline = np.zeros(frames, dtype=np.float32)
        elif rate != sample_rate:
            raise RuntimeError("The voice changed sample rate between scenes.")
        start = round(scene.start_ms * rate / 1000)
        budget = round(scene.end_ms * rate / 1000) - start
        # Remove digital padding from the voice engine before measuring the spoken line.
        nonzero = np.flatnonzero(audio)
        if not nonzero.size:
            raise RuntimeError(f"The voice produced silence for {scene.interval}.")
        audio = audio[nonzero[0]:nonzero[-1] + 1]
        if len(audio) > budget:
            factor = len(audio) / budget
            if factor > 2:
                raise TimedScriptError(
                    f"{scene.name} ({scene.interval}): the narration needs {len(audio)/rate:.2f}s "
                    f"at the selected speed. Shorten the line or extend the interval (over 2× speed required)."
                )
            audio = time_stretch(audio, rate, stretch_factor=factor).reshape(-1)
            if len(audio) > budget:
                raise RuntimeError(f"Time stretching exceeded the scene duration at {scene.interval}.")
            accelerated += 1
        timeline[start:start + len(audio)] = audio
        if metadata.get("rewritten_text") is not None:
            rewrites.append(scene.row(metadata["rewritten_text"]))
    return timeline, sample_rate, {
        **metadata, "rewritten_text": "\n".join(rewrites) if rewrites else None,
        "scene_count": len(scenes), "accelerated_scenes": accelerated,
    }
