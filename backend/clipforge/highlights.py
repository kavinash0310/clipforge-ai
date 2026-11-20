from __future__ import annotations

import math
import re
from statistics import median, quantiles
from typing import Any


EXCITEMENT_TERMS = {
    "clutch", "insane", "no way", "oh my god", "let's go", "lets go",
    "what", "wow", "unbelievable", "crazy", "bruh", "gg", "laugh",
    "laughing", "haha", "lmao", "lol", "sick", "got him", "one shot",
}


def _normal_time(value: float) -> float:
    return max(0.0, float(value))


def _cue_count(text: str) -> int:
    lowered = text.lower()
    lexical = sum(lowered.count(term) for term in EXCITEMENT_TERMS)
    punctuation = min(text.count("!"), 5)
    return lexical + punctuation


def _window_energy(energy: list[float], start: float, end: float) -> tuple[float, float]:
    first = max(0, int(math.floor(start)))
    last = min(len(energy), max(first + 1, int(math.ceil(end))))
    values = energy[first:last]
    if not values:
        return 0.0, 0.0
    return sum(values) / len(values), max(values)


def _window_segments(segments: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    return [segment for segment in segments if float(segment["end"]) > start and float(segment["start"]) < end]


def _overlap_ratio(left: dict[str, Any], right: dict[str, Any]) -> float:
    overlap = max(0.0, min(left["end_seconds"], right["end_seconds"]) - max(left["start_seconds"], right["start_seconds"]))
    shorter = min(left["end_seconds"] - left["start_seconds"], right["end_seconds"] - right["start_seconds"])
    return overlap / shorter if shorter > 0 else 0.0


def generate_highlights(
    *,
    duration_seconds: float,
    energy_by_second: list[float],
    scene_cuts: list[float],
    transcript_segments: list[dict[str, Any]],
    max_candidates: int = 5,
    window_seconds: float = 30.0,
) -> list[dict[str, Any]]:
    """Rank context-preserving candidate windows from audio, transcript, and scene signals."""
    duration = max(0.0, duration_seconds)
    if duration <= 0:
        return []

    window = min(duration, max(8.0, window_seconds))
    hop = min(6.0, max(2.0, window / 5.0))
    starts: list[float] = []
    cursor = 0.0
    while cursor + window < duration:
        starts.append(cursor)
        cursor += hop
    starts.append(max(0.0, duration - window))
    starts = sorted(set(round(item, 3) for item in starts))

    sorted_energy = sorted(max(0.0, item) for item in energy_by_second)
    if sorted_energy:
        baseline = median(sorted_energy)
        high = quantiles(sorted_energy, n=10)[-1] if len(sorted_energy) >= 2 else sorted_energy[0]
        energy_spread = max(0.01, high - baseline)
    else:
        baseline = high = energy_spread = 0.0

    global_speech = sum(max(0.0, float(s["end"]) - float(s["start"])) for s in transcript_segments)
    global_speech_density = min(1.0, global_speech / duration)
    candidates: list[dict[str, Any]] = []
    for start in starts:
        end = min(duration, start + window)
        local_segments = _window_segments(transcript_segments, start, end)
        text = " ".join(str(item.get("text", "")) for item in local_segments).strip()
        spoken = sum(
            max(0.0, min(end, float(item["end"])) - max(start, float(item["start"])))
            for item in local_segments
        )
        speech_density = min(1.0, spoken / max(1.0, end - start))
        segment_text = " ".join(str(item.get("text", "")) for item in local_segments)
        cues = _cue_count(segment_text)
        mean_energy, peak_energy = _window_energy(energy_by_second, start, end)
        if energy_by_second:
            energy_signal = min(1.0, max(0.0, (peak_energy - baseline) / energy_spread))
            if high <= baseline + 0.01:
                energy_signal = 0.0
        else:
            energy_signal = 0.0

        local_cuts = [cut for cut in scene_cuts if start < cut <= end]
        scene_signal = min(1.0, len(local_cuts) / max(1.0, (end - start) / 12.0))
        baseline_speech = max(0.12, global_speech_density)
        speech_signal = min(1.0, speech_density / baseline_speech)
        excitement_signal = min(1.0, cues / max(1.0, (end - start) / 12.0))

        score = 100.0 * (
            0.34 * energy_signal
            + 0.24 * speech_signal
            + 0.27 * excitement_signal
            + 0.15 * scene_signal
        )
        if score < 22 or (not local_segments and not local_cuts and energy_signal < 0.18):
            continue

        reasons = []
        if energy_signal >= 0.35:
            reasons.append("Audio energy spike")
        if cues:
            reasons.append("Excitement cues in transcript")
        if len(local_cuts) >= 2:
            reasons.append("Several scene changes")
        if speech_density >= 0.12:
            reasons.append("Clear spoken context")
        if not reasons:
            reasons.append("Combined audio and scene activity")

        title = " ".join(text.split())[:96].strip(" ,.!?")
        if not title:
            title = f"Highlight at {int(start // 60):02d}:{int(start % 60):02d}"
        candidates.append(
            {
                "start_seconds": round(_normal_time(start), 3),
                "end_seconds": round(_normal_time(end), 3),
                "score": round(score, 2),
                "title": title,
                "reasons": reasons,
                "signals": {
                    "audio_energy": round(energy_signal, 4),
                    "speech_density": round(speech_density, 4),
                    "excitement_cues": cues,
                    "scene_changes": len(local_cuts),
                    "mean_rms": round(mean_energy, 6),
                    "peak_rms": round(peak_energy, 6),
                },
            }
        )

    ranked = sorted(candidates, key=lambda item: (item["score"], -item["start_seconds"]), reverse=True)
    selected: list[dict[str, Any]] = []
    for candidate in ranked:
        if any(_overlap_ratio(candidate, existing) >= 0.55 for existing in selected):
            continue
        selected.append(candidate)
        if len(selected) >= max_candidates:
            break
    return sorted(selected, key=lambda item: item["start_seconds"])

