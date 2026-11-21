from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import numpy as np


NEUTRAL_GRADE = {
    "brightness": 0.0,
    "contrast": 1.0,
    "saturation": 1.0,
    "red_gain": 1.0,
    "green_gain": 1.0,
    "blue_gain": 1.0,
    "sampled_frames": 0,
    "mean_luminance": None,
    "contrast_range": None,
    "mean_saturation": None,
    "note": "Color analysis was unavailable; a neutral grade was used.",
}


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def analyze_clip_color(
    *,
    source: Path,
    start_seconds: float,
    duration_seconds: float,
    strength_percent: int = 65,
    cpu_threads: int = 1,
    check_cancel: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Estimate a restrained color grade from low-resolution samples of the clip."""
    neutral = dict(NEUTRAL_GRADE)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or duration_seconds <= 0:
        return neutral

    if check_cancel:
        check_cancel()
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-threads", str(max(1, cpu_threads)),
        "-ss", f"{max(0.0, start_seconds):.3f}", "-i", str(source), "-t", f"{duration_seconds:.3f}",
        "-an", "-vf", "fps=0.5,scale=64:36:flags=area,format=rgb24", "-frames:v", "24",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        if check_cancel:
            check_cancel()
        return neutral
    if check_cancel:
        check_cancel()
    if completed.returncode != 0:
        return neutral

    frame_bytes = 64 * 36 * 3
    frame_count = len(completed.stdout) // frame_bytes
    if frame_count < 1:
        return neutral
    rgb = np.frombuffer(completed.stdout[:frame_count * frame_bytes], dtype=np.uint8)
    rgb = rgb.reshape((frame_count, 36, 64, 3)).astype(np.float32) / 255.0
    luma = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    mean_luma = float(np.mean(luma))
    low_luma, high_luma = np.percentile(luma, [8, 92])
    contrast_range = float(high_luma - low_luma)
    maximum = np.max(rgb, axis=-1)
    minimum = np.min(rgb, axis=-1)
    saturation = np.divide(maximum - minimum, np.maximum(maximum, 0.04))
    mean_saturation = float(np.mean(saturation))
    channel_means = np.mean(rgb, axis=(0, 1, 2))
    reference = float(0.2126 * channel_means[0] + 0.7152 * channel_means[1] + 0.0722 * channel_means[2])
    strength = _bounded(int(strength_percent), 0, 100) / 100.0

    brightness = _bounded((0.46 - mean_luma) * 0.24, -0.05, 0.05) * strength
    contrast = 1.0 + _bounded((0.40 - contrast_range) * 0.18, -0.045, 0.045) * strength
    saturation_gain = 1.0 + _bounded((0.28 - mean_saturation) * 0.32, -0.08, 0.11) * strength
    gains = [
        _bounded(reference / max(float(channel), 0.08), 0.96, 1.04)
        for channel in channel_means
    ]
    gains = [1.0 + (gain - 1.0) * strength for gain in gains]

    return {
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
        "saturation": round(saturation_gain, 4),
        "red_gain": round(gains[0], 4),
        "green_gain": round(gains[1], 4),
        "blue_gain": round(gains[2], 4),
        "sampled_frames": int(frame_count),
        "mean_luminance": round(mean_luma, 4),
        "contrast_range": round(contrast_range, 4),
        "mean_saturation": round(mean_saturation, 4),
        "note": "Estimated from low-resolution source frames with limited correction strength.",
    }


def portrait_cleanup_filters(strength_percent: int) -> str:
    """Return light denoise and detail-recovery filters for a webcam/portrait crop."""
    strength = _bounded(int(strength_percent), 0, 100) / 100.0
    if strength <= 0:
        return ""
    spatial = 0.35 + 0.85 * strength
    temporal = 1.0 + 2.0 * strength
    sharpen = 0.06 + 0.20 * strength
    return (
        f"hqdn3d={spatial:.3f}:{spatial * 0.75:.3f}:{temporal:.3f}:{temporal * 0.75:.3f},"
        f"unsharp=5:5:{sharpen:.3f}:3:3:0.0"
    )
