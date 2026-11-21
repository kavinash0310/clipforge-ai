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
FOCUS_STOP_WORDS = {"and", "for", "the", "that", "this", "with", "from", "into", "about", "clip", "clips", "video", "moment"}


def _focus_words(value: str) -> set[str]:
    return set(re.findall(r"[^\W_]{2,}", value.lower(), flags=re.UNICODE))


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


def _sentence_boundary(segment: dict[str, Any]) -> bool:
    return bool(re.search(r"[.!?।؟！？…][\"'’”)}\]]*$", str(segment.get("text", "")).strip()))


def _learned_weights(weights: tuple[float, ...], examples: list[dict[str, Any]]) -> tuple[float, ...]:
    if len(examples) < 8:
        return weights
    good = [item.get("signals", {}) for item in examples if int(item.get("rating", 0)) >= 4]
    low = [item.get("signals", {}) for item in examples if int(item.get("rating", 0)) <= 2]
    if len(good) < 2 or len(low) < 2:
        return weights
    keys = ("audio_energy", "speech_density", "excitement_cues", "scene_changes", "visual_motion")[:len(weights)]

    def value(signals: dict[str, Any], key: str) -> float:
        try:
            number = float(signals.get(key, 0))
        except (TypeError, ValueError):
            return 0.0
        if key in {"excitement_cues", "scene_changes"}:
            number /= 4.0
        return min(1.0, max(0.0, number))

    adjusted = []
    for weight, key in zip(weights, keys, strict=True):
        high_average = sum(value(signals, key) for signals in good) / len(good)
        low_average = sum(value(signals, key) for signals in low) / len(low)
        preference = max(-1.0, min(1.0, high_average - low_average))
        adjusted.append(weight * math.exp(preference * 2.0))
    total = sum(adjusted) or 1.0
    learned = tuple(item / total for item in adjusted)
    # Keep early personal feedback anchored to the stock scoring profile.
    blend = min(0.65, (len(examples) - 7) / 40)
    mixed = tuple((prior * (1 - blend)) + (current * blend) for prior, current in zip(weights, learned, strict=True))
    total = sum(mixed) or 1.0
    return tuple(item / total for item in mixed)


def generate_highlights(
    *,
    duration_seconds: float,
    energy_by_second: list[float],
    scene_cuts: list[float],
    transcript_segments: list[dict[str, Any]],
    max_candidates: int = 5,
    window_seconds: float = 30.0,
    min_window_seconds: float = 15.0,
    max_window_seconds: float | None = None,
    moment_mix: str = "balanced",
    focus_prompt: str = "",
    visual_motion_by_second: list[float] | None = None,
    analysis_mode: str = "fast",
    rating_examples: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rank context-preserving candidate windows from audio, transcript, and scene signals."""
    duration = max(0.0, duration_seconds)
    if duration <= 0:
        return []

    maximum_window = max_window_seconds if max_window_seconds is not None else window_seconds
    maximum_window = min(duration, max(8.0, float(maximum_window)))
    minimum_window = min(maximum_window, max(8.0, float(min_window_seconds)))
    window = maximum_window
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

    motion = visual_motion_by_second or []
    sorted_motion = sorted(max(0.0, item) for item in motion)
    if sorted_motion:
        motion_baseline = median(sorted_motion)
        motion_high = quantiles(sorted_motion, n=10)[-1] if len(sorted_motion) >= 2 else sorted_motion[0]
        motion_spread = max(0.01, motion_high - motion_baseline)
    else:
        motion_baseline = motion_high = motion_spread = 0.0

    global_speech = sum(max(0.0, float(s["end"]) - float(s["start"])) for s in transcript_segments)
    global_speech_density = min(1.0, global_speech / duration)
    focus_terms = _focus_words(focus_prompt) - FOCUS_STOP_WORDS
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
        motion_first = max(0, int(math.floor(start)))
        motion_last = min(len(motion), max(motion_first + 1, int(math.ceil(end))))
        motion_values = motion[motion_first:motion_last]
        motion_peak = max(motion_values, default=0.0)
        motion_signal = min(1.0, max(0.0, (motion_peak - motion_baseline) / motion_spread)) if motion else 0.0

        if analysis_mode == "deep" and motion:
            weights = {
                "balanced": (0.27, 0.20, 0.20, 0.12, 0.21),
                "action": (0.30, 0.10, 0.17, 0.17, 0.26),
                "dialogue": (0.10, 0.39, 0.28, 0.08, 0.15),
            }.get(moment_mix, (0.27, 0.20, 0.20, 0.12, 0.21))
            weights = _learned_weights(weights, rating_examples or [])
            score = 100.0 * sum(weight * signal for weight, signal in zip(
                weights, (energy_signal, speech_signal, excitement_signal, scene_signal, motion_signal), strict=True
            ))
        else:
            weights = {
                "balanced": (0.34, 0.24, 0.27, 0.15),
                "action": (0.46, 0.12, 0.20, 0.22),
                "dialogue": (0.12, 0.48, 0.30, 0.10),
            }.get(moment_mix, (0.34, 0.24, 0.27, 0.15))
            weights = _learned_weights(weights, rating_examples or [])
            score = 100.0 * sum(weight * signal for weight, signal in zip(
                weights, (energy_signal, speech_signal, excitement_signal, scene_signal), strict=True
            ))
        focus_matches = focus_terms.intersection(_focus_words(text))
        focus_signal = min(1.0, len(focus_matches) / max(1, min(3, len(focus_terms)))) if focus_terms else 0.0
        score = min(100.0, score + 12.0 * focus_signal)
        if score < 22 or (not local_segments and not local_cuts and energy_signal < 0.18):
            continue

        reasons = []
        if energy_signal >= 0.35:
            reasons.append("Audio energy spike")
        if cues:
            reasons.append("Excitement cues in transcript")
        if len(local_cuts) >= 2:
            reasons.append("Several scene changes")
        if motion_signal >= 0.35:
            reasons.append("Visible motion spike")
        if speech_density >= 0.12:
            reasons.append("Clear spoken context")
        if focus_signal >= 0.34:
            reasons.append("Focus phrase match")
        if not reasons:
            reasons.append("Combined audio and scene activity")

        title = " ".join(text.split())[:96].strip(" ,.!?")
        if not title:
            title = f"Highlight at {int(start // 60):02d}:{int(start % 60):02d}"
        target_length = minimum_window + (maximum_window - minimum_window) * (0.35 + 0.65 * score / 100.0)
        target_length = min(end - start, max(minimum_window, target_length))
        energy_first = max(0, int(math.floor(start)))
        energy_last = min(len(energy_by_second), max(energy_first + 1, int(math.ceil(end))))
        peak_offset = max(range(max(1, energy_last - energy_first)), key=lambda offset: energy_by_second[energy_first + offset] if energy_first + offset < energy_last else 0.0)
        anchor = min(end, max(start, energy_first + peak_offset + 0.5))
        clip_start = min(max(start, anchor - target_length / 2), max(start, end - target_length))
        clip_end = clip_start + target_length

        sentence_starts = [
            float(item["start"])
            for index, item in enumerate(local_segments)
            if index > 0 and _sentence_boundary(local_segments[index - 1])
        ]
        if sentence_starts:
            nearby_starts = [point for point in sentence_starts if start <= point <= end - minimum_window and abs(point - clip_start) <= 2.0]
            if nearby_starts:
                clip_start = min(nearby_starts, key=lambda point: abs(point - clip_start))
        sentence_ends = [float(item["end"]) for item in local_segments if _sentence_boundary(item)]
        nearby_ends = [point for point in sentence_ends if clip_start + minimum_window <= point <= min(end, clip_start + maximum_window) and abs(point - clip_end) <= 2.5]
        if nearby_ends:
            clip_end = min(nearby_ends, key=lambda point: abs(point - clip_end))
        actual_length = clip_end - clip_start
        if actual_length < minimum_window:
            clip_end = min(end, clip_start + minimum_window)
        elif actual_length > maximum_window:
            clip_end = clip_start + maximum_window

        candidates.append(
            {
                "start_seconds": round(_normal_time(clip_start), 3),
                "end_seconds": round(_normal_time(clip_end), 3),
                "score": round(score, 2),
                "title": title,
                "reasons": reasons,
                "signals": {
                    "audio_energy": round(energy_signal, 4),
                    "speech_density": round(speech_density, 4),
                    "excitement_cues": cues,
                    "scene_changes": len(local_cuts),
                    "visual_motion": round(motion_signal, 4),
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

