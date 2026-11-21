from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .media import probe_video


def _clock(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _ass_clock(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    whole_seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def _ass_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


CAPTION_STYLES = {
    "neon": ("Arial", "&H00FFFFFF", "&H00A13F8B", 5, 2, 1),
    "impact": ("Impact", "&H00FFFFFF", "&H00000000", 5, 1, 1),
    "clean": ("Arial", "&H00FFFFFF", "&H00101010", 2, 1, 0),
    "hormozi": ("Arial", "&H0000A5FF", "&H00101010", 4, 2, 1),
    "mrbeast": ("Arial", "&H0000FFFF", "&H00101010", 5, 2, 1),
}


def subtitle_files(
    segments: list[dict[str, Any]],
    *,
    caption_style: str = "neon",
    width: int = 1080,
    height: int = 1920,
    watermark_text: str = "",
) -> tuple[str, str]:
    srt_blocks: list[str] = []
    ass_events: list[str] = []
    for segment in segments:
        text = _clean_text(segment.get("text", ""))
        start = float(segment["start"])
        end = float(segment["end"])
        if not text or end <= start:
            continue
        srt_blocks.append(f"{len(srt_blocks) + 1}\n{_clock(start)} --> {_clock(end)}\n{text}")
        ass_events.append(f"Dialogue: 0,{_ass_clock(start)},{_ass_clock(end)},Default,,0,0,0,,{_ass_text(text)}")
    watermark = _clean_text(watermark_text)[:60]
    if watermark:
        ass_events.append(f"Dialogue: 1,0:00:00.00,0:10:00.00,Watermark,,0,0,0,,{_ass_text(watermark)}")

    srt = "\n\n".join(srt_blocks) + ("\n" if srt_blocks else "")
    ass = "\n".join([
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{CAPTION_STYLES[caption_style][0]},{max(34, round(height * 0.028))},{CAPTION_STYLES[caption_style][1]},&H000000FF,{CAPTION_STYLES[caption_style][2]},&H96000000,{CAPTION_STYLES[caption_style][5]},0,0,0,100,100,0,0,1,{CAPTION_STYLES[caption_style][3]},{CAPTION_STYLES[caption_style][4]},2,{round(width * 0.078)},{round(width * 0.078)},{round(height * 0.075)},1",
        f"Style: Watermark,Arial,{max(22, round(height * 0.022))},&H00FFFFFF,&H000000FF,&H00101010,&H64000000,1,0,0,0,100,100,0,0,1,2,1,8,{round(width * 0.05)},{round(width * 0.05)},{round(height * 0.035)},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *ass_events,
        "",
    ])
    return srt, ass


def _write_atomic(destination: Path, content: str) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8-sig" if destination.suffix == ".ass" else "utf-8")
    os.replace(temporary, destination)


def render_vertical_clip(
    *,
    source: Path,
    destination: Path,
    start_seconds: float,
    end_seconds: float,
    subtitles: list[dict[str, Any]],
    render_options: dict[str, str] | None = None,
    check_cancel: Callable[[], None],
    progress: Callable[[int, str], None],
    cpu_threads: int | None = None,
) -> dict[str, Any]:
    options = render_options or {}
    aspect_ratio = options.get("aspect_ratio", "9:16")
    layout = options.get("layout", "blur")
    caption_style = options.get("caption_style", "neon")
    watermark_text = options.get("watermark_text", "")
    dimensions = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}
    if aspect_ratio not in dimensions or layout not in {"blur", "fit", "fill"} or caption_style not in CAPTION_STYLES:
        raise ValueError("The selected output format or caption style is not supported.")
    width, height = dimensions[aspect_ratio]
    duration = end_seconds - start_seconds
    if start_seconds < 0 or duration <= 0 or duration > 600:
        raise ValueError("A rendered clip must be between 0 and 600 seconds long.")
    if not source.is_file():
        raise RuntimeError("The source recording is unavailable. Import it again before rendering.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg and restart ClipForge.")
    thread_count = max(1, min(int(cpu_threads or 4), os.cpu_count() or 1))

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_video = destination.with_name(f"{destination.stem}.rendering.mp4")
    ass_path = destination.with_suffix(".ass")
    srt, ass = subtitle_files(subtitles, caption_style=caption_style, width=width, height=height, watermark_text=watermark_text)
    _write_atomic(destination.with_suffix(".srt"), srt)
    _write_atomic(ass_path, ass)
    check_cancel()
    progress(22, "rendering_vertical")

    if layout == "blur":
        framing = (
            f"[0:v]split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=24:8[bgv];[fg]scale={width}:{height}:"
            "force_original_aspect_ratio=decrease:force_divisible_by=2[fgv];"
            "[bgv][fgv]overlay=(W-w)/2:(H-h)/2[framed];"
        )
    elif layout == "fit":
        framing = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black[framed];"
    else:
        framing = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[framed];"
    filter_graph = f"{framing}[framed]fps=30,subtitles=filename='{ass_path.name}'[v]"
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-filter_complex_threads", str(thread_count),
        "-ss", f"{start_seconds:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
        "-filter_complex", filter_graph, "-map", "[v]", "-map", "0:a:0?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-threads", str(thread_count),
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(temporary_video),
    ]
    try:
        process = subprocess.Popen(
            command,
            cwd=destination.parent,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        started_at = time.monotonic()
        while True:
            try:
                _stdout, stderr = process.communicate(timeout=2)
                break
            except subprocess.TimeoutExpired:
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
                if time.monotonic() - started_at > max(600, duration * 120):
                    process.kill()
                    _stdout, stderr = process.communicate()
                    raise RuntimeError("Vertical rendering timed out. The original recording was left unchanged.")
        if process.returncode != 0:
            detail = (stderr or "").strip()[-1000:]
            raise RuntimeError(f"FFmpeg could not render this clip. {detail}".strip())

        check_cancel()
        progress(88, "validating_render")
        metadata = probe_video(temporary_video)
        video = metadata.get("video", {})
        if video.get("width") != width or video.get("height") != height:
            raise RuntimeError(f"FFmpeg returned unexpected dimensions; expected {width} × {height}.")
        if metadata.get("duration_seconds") is None or metadata["duration_seconds"] <= 0:
            raise RuntimeError("The rendered clip has no readable duration.")
        os.replace(temporary_video, destination)
        progress(96, "saving_render")
        return {
            "file_path": str(destination),
            "subtitle_path": str(destination.with_suffix(".srt")),
            "duration_seconds": metadata["duration_seconds"],
            "width": video["width"],
            "height": video["height"],
            "codec": video.get("codec"),
            "settings": {"aspect_ratio": aspect_ratio, "layout": layout, "caption_style": caption_style, "watermark_text": watermark_text},
        }
    except Exception:
        temporary_video.unlink(missing_ok=True)
        raise
