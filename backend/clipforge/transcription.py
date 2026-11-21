from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Callable

import numpy as np
from faster_whisper import WhisperModel

from .config import DATA_DIR
from .transliteration import to_hinglish


def _output_directory(recording_id: str) -> Path:
    directory = DATA_DIR / "output" / recording_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _clock(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def write_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        text = re.sub(r"\s+", " ", str(segment.get("text", ""))).strip()
        if not text:
            continue
        blocks.append(
            f"{index}\n{_clock(float(segment['start']))} --> {_clock(float(segment['end']))}\n{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _run_cancellable(
    command: list[str],
    timeout_seconds: int,
    check_cancel: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    started_at = time.monotonic()
    while True:
        try:
            stdout, stderr = process.communicate(timeout=2)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            if check_cancel:
                try:
                    check_cancel()
                except Exception:
                    process.terminate()
                    try:
                        process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                    raise
            if time.monotonic() - started_at > timeout_seconds:
                process.kill()
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(command, timeout_seconds, output=stdout, stderr=stderr)


def extract_audio(
    source: Path,
    destination: Path,
    check_cancel: Callable[[], None] | None = None,
    cpu_threads: int = 1,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg and restart ClipForge.")
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-threads", str(max(1, cpu_threads)), "-i", str(source),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(destination),
    ]
    try:
        result = _run_cancellable(command, 1800, check_cancel)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Audio extraction timed out. The source file was left unchanged.") from error
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[-800:]
        raise RuntimeError(f"Audio extraction failed. {detail}".strip())


def analyze_audio_energy(wav_path: Path, check_cancel: Callable[[], None] | None = None) -> tuple[list[float], dict[str, Any]]:
    with wave.open(str(wav_path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise RuntimeError("Extracted analysis audio must be mono 16-bit PCM.")
        sample_rate = source.getframerate()
        if sample_rate != 16000:
            raise RuntimeError(f"Expected 16 kHz analysis audio, received {sample_rate} Hz.")
        frames_per_bucket = sample_rate
        values: list[float] = []
        while True:
            if check_cancel:
                check_cancel()
            raw = source.readframes(frames_per_bucket)
            if not raw:
                break
            samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
            values.append(float(np.sqrt(np.mean(np.square(samples)))))

    duration = sum(1 for _ in values)
    nonzero = [value for value in values if value > 0.0001]
    profile = {
        "sample_rate": sample_rate,
        "bucket_seconds": 1,
        "duration_seconds": duration,
        "mean_rms": float(np.mean(values)) if values else 0.0,
        "peak_rms": max(values, default=0.0),
        "active_audio_fraction": len(nonzero) / max(1, len(values)),
        "energy_buckets": values,
    }
    return values, profile


def detect_scene_cuts(
    source: Path,
    check_cancel: Callable[[], None] | None = None,
    cpu_threads: int = 1,
) -> list[float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg and restart ClipForge.")
    command = [
        ffmpeg, "-hide_banner", "-nostats", "-loglevel", "info",
        "-threads", str(max(1, cpu_threads)), "-filter_threads", str(max(1, cpu_threads)), "-i", str(source),
        "-an", "-vf", "select='gt(scene,0.30)',showinfo", "-fps_mode", "vfr",
        "-f", "null", "-",
    ]
    try:
        result = _run_cancellable(command, 2400, check_cancel)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Scene detection timed out. The source file was left unchanged.") from error
    if check_cancel:
        check_cancel()
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[-800:]
        raise RuntimeError(f"Scene detection failed. {detail}".strip())
    cuts = re.findall(r"pts_time:([0-9]+(?:\.[0-9]+)?)", result.stderr)
    return sorted(set(round(float(value), 3) for value in cuts))


def detect_visual_activity(
    source: Path,
    destination: Path,
    check_cancel: Callable[[], None] | None = None,
    cpu_threads: int = 1,
) -> list[float]:
    """Build a per-second low-resolution frame-difference signal for deep analysis."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg and restart ClipForge.")
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-threads", str(max(1, cpu_threads)),
        "-i", str(source), "-an", "-vf", "fps=1,scale=160:90:flags=fast_bilinear,format=gray",
        "-fps_mode", "vfr", "-f", "rawvideo", str(destination),
    ]
    try:
        result = _run_cancellable(command, 3600, check_cancel)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("The deep visual scan timed out. The source file was left unchanged.") from error
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[-800:]
        raise RuntimeError(f"The deep visual scan failed. {detail}".strip())

    frame_bytes = 160 * 90
    raw = np.fromfile(destination, dtype=np.uint8)
    frame_count = len(raw) // frame_bytes
    if frame_count < 2:
        return [0.0] * max(1, frame_count)
    frames = raw[:frame_count * frame_bytes].reshape((frame_count, 90, 160)).astype(np.int16)
    differences = np.abs(frames[1:] - frames[:-1]).mean(axis=(1, 2)) / 255.0
    return [0.0, *[round(float(value), 5) for value in differences]]


def transcribe_recording(
    *,
    source: Path,
    recording_id: str,
    model_name: str,
    language: str | None,
    analysis_mode: str = "fast",
    cpu_threads: int,
    progress: Callable[[int, int, str], None],
    check_cancel: Callable[[], None],
) -> dict[str, Any]:
    output_dir = _output_directory(recording_id)
    with tempfile.TemporaryDirectory(prefix="audio-", dir=DATA_DIR) as temporary_directory:
        wav_path = Path(temporary_directory) / "analysis.wav"
        progress(12, 0, "extracting_audio")
        extract_audio(source, wav_path, check_cancel, cpu_threads)

        check_cancel()
        progress(20, 0, "analyzing_audio")
        energy_by_second, audio_profile = analyze_audio_energy(wav_path, check_cancel)

        check_cancel()
        progress(34, 0, "detecting_scenes")
        scene_cuts = detect_scene_cuts(source, check_cancel, cpu_threads)
        visual_motion_by_second: list[float] = []
        if analysis_mode == "deep":
            check_cancel()
            progress(39, 0, "scanning_visual_motion")
            motion_path = Path(temporary_directory) / "visual-motion.gray"
            visual_motion_by_second = detect_visual_activity(source, motion_path, check_cancel, cpu_threads)

        check_cancel()
        progress(42, 0, "loading_model")
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, min(cpu_threads, 6)),
            download_root=str(DATA_DIR / "models"),
        )
        progress(49, 0, "transcribing")
        whisper_language = "hi" if language == "hinglish" else language
        generated, info = model.transcribe(
            str(wav_path),
            beam_size=3,
            language=whisper_language,
            vad_filter=True,
            word_timestamps=False,
            condition_on_previous_text=False,
        )
        segments = []
        last_progress = 49
        for segment in generated:
            check_cancel()
            text = segment.text.strip()
            if text and language == "hinglish":
                text = to_hinglish(text)
            if text:
                segments.append(
                    {
                        "start": round(float(segment.start), 3),
                        "end": round(float(segment.end), 3),
                        "text": text,
                        "confidence": round(float(segment.avg_logprob), 4),
                    }
                )
            segment_progress = min(77, 49 + int((float(segment.end) / max(1.0, audio_profile["duration_seconds"])) * 28))
            if segment_progress > last_progress:
                progress(segment_progress, len(segments), "transcribing")
                last_progress = segment_progress

        srt_path = output_dir / "transcript.srt"
        transcript_path = output_dir / "transcript.json"
        transcript = {
            "language": "hi-Latn" if language == "hinglish" else info.language,
            "language_probability": round(float(info.language_probability), 4),
            "model": model_name,
            "device": "cpu",
            "compute_type": "int8",
            "segments": segments,
        }
        progress(80, len(segments), "scoring_highlights")
        for destination, content in (
            (transcript_path, json.dumps(transcript, ensure_ascii=False, indent=2)),
            (srt_path, write_srt(segments)),
        ):
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, destination)

        return {
            "transcript": transcript,
            "subtitle_path": str(srt_path),
            "transcript_path": str(transcript_path),
            "energy_by_second": energy_by_second,
            "audio_profile": audio_profile,
            "scene_cuts": scene_cuts,
            "visual_motion_by_second": visual_motion_by_second,
        }

