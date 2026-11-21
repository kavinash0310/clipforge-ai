from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .media import probe_video
from .video_enhancement import NEUTRAL_GRADE, analyze_clip_color, portrait_cleanup_filters


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


def _ass_color(value: str) -> str:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6 or not re.fullmatch(r"[0-9A-Fa-f]{6}", cleaned):
        return "&H00FFFFFF"
    red, green, blue = cleaned[0:2], cleaned[2:4], cleaned[4:6]
    return f"&H00{blue}{green}{red}".upper()


def _wrap_words(value: str, words_per_line: int) -> str:
    words = value.split()
    chunks = [" ".join(words[index:index + words_per_line]) for index in range(0, len(words), words_per_line)]
    return r"\N".join(_ass_text(chunk) for chunk in chunks)


def _karaoke_words(value: str, duration: float, words_per_line: int) -> str:
    words = value.split()
    if not words:
        return ""
    total_centiseconds = max(len(words), int(round(duration * 100)))
    base, remainder = divmod(total_centiseconds, len(words))
    entries = []
    for index, word in enumerate(words):
        units = base + (1 if index < remainder else 0)
        entries.append(f"{{\\k{units}}}{_ass_text(word)}")
    lines = [" ".join(entries[index:index + words_per_line]) for index in range(0, len(entries), words_per_line)]
    return r"\N".join(lines)


CAPTION_STYLES = {
    "neon": ("Arial", "&H00FFFFFF", "&H00A13F8B", 5, 2, 1),
    "impact": ("Impact", "&H00FFFFFF", "&H00000000", 5, 1, 1),
    "clean": ("Arial", "&H00FFFFFF", "&H00101010", 2, 1, 0),
    "hormozi": ("Arial", "&H0000A5FF", "&H00101010", 4, 2, 1),
    "mrbeast": ("Arial", "&H0000FFFF", "&H00101010", 5, 2, 1),
}
CAPTION_HIGHLIGHTS = {
    "neon": "&H00E65CF2",
    "impact": "&H00FFFFFF",
    "clean": "&H00FFFFFF",
    "hormozi": "&H0000A5FF",
    "mrbeast": "&H0000FFFF",
}


def subtitle_files(
    segments: list[dict[str, Any]],
    *,
    caption_style: str = "neon",
    width: int = 1080,
    height: int = 1920,
    watermark_text: str = "",
    opening_hook: str = "",
    opening_hook_seconds: float = 8.0,
    outro_text: str = "",
    outro_seconds: float = 3.0,
    template: str = "none",
    template_name: str = "",
    template_handle: str = "",
    credit_text: str = "",
    clip_duration: float = 0.0,
    caption_font: str = "Arial",
    caption_size: int = 50,
    caption_text_color: str = "#FFFFFF",
    caption_outline_color: str = "#351633",
    caption_words_per_line: int = 5,
    caption_animation: str = "static",
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
        words = text.split()
        if caption_animation in {"one_by_one", "build_up"} and words:
            word_duration = (end - start) / len(words)
            for word_index, word in enumerate(words):
                event_start = start + word_index * word_duration
                event_end = start + (word_index + 1) * word_duration if caption_animation == "one_by_one" else end
                shown = word if caption_animation == "one_by_one" else " ".join(words[:word_index + 1])
                ass_events.append(f"Dialogue: 0,{_ass_clock(event_start)},{_ass_clock(event_end)},Default,,0,0,0,,{_ass_text(shown)}")
        else:
            line_text = _karaoke_words(text, end - start, caption_words_per_line) if caption_animation == "word_highlight" else _wrap_words(text, caption_words_per_line)
            if caption_animation == "pop_in":
                line_text = "{\\fscx0\\fscy0\\t(0,140,\\fscx100\\fscy100)}" + line_text
            elif caption_animation == "pop_in_line":
                line_text = "{\\fad(0,120)}" + line_text
            ass_events.append(f"Dialogue: 0,{_ass_clock(start)},{_ass_clock(end)},Default,,0,0,0,,{line_text}")
    watermark = _clean_text(watermark_text)[:60]
    if watermark:
        ass_events.append(f"Dialogue: 1,0:00:00.00,0:10:00.00,Watermark,,0,0,0,,{_ass_text(watermark)}")
    hook = _clean_text(opening_hook)[:100]
    if hook:
        ass_events.append(f"Dialogue: 2,0:00:00.00,{_ass_clock(min(clip_duration, max(2.0, opening_hook_seconds)))},Hook,,0,0,0,,{_ass_text(hook)}")
    outro = _clean_text(outro_text)[:100]
    if outro:
        outro_start = max(0.0, clip_duration - max(1.5, outro_seconds))
        ass_events.append(f"Dialogue: 3,{_ass_clock(outro_start)},{_ass_clock(clip_duration)},Outro,,0,0,0,,{_ass_text(outro)}")

    credit = _clean_text(credit_text)[:100]
    if credit:
        ass_events.append(f"Dialogue: 5,0:00:00.00,{_ass_clock(clip_duration)},Default,,0,0,0,,{{\\an3\\pos({width - 48},{height - 36})\\fs28\\bord2\\shad1}}{_ass_text(credit)}")
    template = template if template in {"x_light", "x_dark", "tiktok_hook", "breaking_news"} else "none"
    if template != "none":
        banner_height = round(height * (0.12 if template == "breaking_news" else 0.10))
        banner_y = height - banner_height if template == "breaking_news" else 0
        background_color = {
            "x_light": "&H00F1F4F3", "x_dark": "&H00110E13", "tiktok_hook": "&H00110E13", "breaking_news": "&H00221EEA",
        }[template]
        text_color = "&H00000000" if template == "x_light" else "&H00FFFFFF"
        ass_events.append(
            f"Dialogue: 4,0:00:00.00,{_ass_clock(clip_duration)},Default,,0,0,0,,"
            f"{{\\an7\\pos(0,{banner_y})\\bord0\\shad0\\1c{background_color}\\p1}}"
            f"m 0 0 l {width} 0 l {width} {banner_height} l 0 {banner_height}"
        )
        label = {"x_light": "POST", "x_dark": "POST", "tiktok_hook": "WATCH THIS", "breaking_news": "BREAKING"}[template]
        title = _clean_text(template_name)[:60] or _clean_text(opening_hook)[:60] or label
        handle = _clean_text(template_handle)[:60]
        copy = title + (f"  ·  {handle}" if handle else "")
        ass_events.append(
            f"Dialogue: 6,0:00:00.00,{_ass_clock(clip_duration)},Default,,0,0,0,,"
            f"{{\\an7\\pos({round(width * 0.055)},{banner_y + round(banner_height * 0.35)})\\fs{max(30, round(height * 0.026))}\\bord0\\shad0\\b1\\1c{text_color}}}{_ass_text(copy)}"
        )

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
        f"Style: Default,{caption_font},{caption_size},{_ass_color(caption_text_color)},{CAPTION_HIGHLIGHTS[caption_style]},{_ass_color(caption_outline_color)},&H96000000,{CAPTION_STYLES[caption_style][5]},0,0,0,100,100,0,0,1,{CAPTION_STYLES[caption_style][3]},{CAPTION_STYLES[caption_style][4]},2,{round(width * 0.078)},{round(width * 0.078)},{round(height * 0.075)},1",
        f"Style: Watermark,Arial,{max(22, round(height * 0.022))},&H00FFFFFF,&H000000FF,&H00101010,&H64000000,1,0,0,0,100,100,0,0,1,2,1,8,{round(width * 0.05)},{round(width * 0.05)},{round(height * 0.035)},1",
        f"Style: Hook,Arial,{max(30, round(height * 0.035))},&H00FFFFFF,&H000000FF,&H00101010,&HAA100A18,1,0,0,0,100,100,0,0,3,2,1,8,{round(width * 0.08)},{round(width * 0.08)},{round(height * 0.13)},1",
        f"Style: Outro,Arial,{max(28, round(height * 0.03))},&H00FFFFFF,&H000000FF,&H00101010,&HAA100A18,1,0,0,0,100,100,0,0,3,2,1,2,{round(width * 0.08)},{round(width * 0.08)},{round(height * 0.11)},1",
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


def _region_crop(region: dict[str, float] | None) -> str:
    if not region:
        return ""
    x = min(1.0, max(0.0, float(region["x"])))
    y = min(1.0, max(0.0, float(region["y"])))
    width = min(1.0 - x, max(0.01, float(region["width"])))
    height = min(1.0 - y, max(0.01, float(region["height"])))
    return f"crop=iw*{width:.6f}:ih*{height:.6f}:iw*{x:.6f}:ih*{y:.6f}"


def _write_gradient_ppm(destination: Path, first: str, second: str) -> None:
    def channels(value: str) -> tuple[int, int, int]:
        cleaned = value.lstrip("#")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", cleaned):
            return 24, 19, 38
        return tuple(int(cleaned[index:index + 2], 16) for index in (0, 2, 4))

    top = channels(first)
    bottom = channels(second)
    rows = bytearray()
    for y in range(256):
        ratio = y / 255
        row = bytes(round(top[channel] * (1 - ratio) + bottom[channel] * ratio) for channel in range(3))
        rows.extend(row * 256)
    destination.write_bytes(b"P6\n256 256\n255\n" + rows)


def render_vertical_clip(
    *,
    source: Path,
    destination: Path,
    start_seconds: float,
    end_seconds: float,
    subtitles: list[dict[str, Any]],
    render_options: dict[str, Any] | None = None,
    music_source: Path | None = None,
    logo_source: Path | None = None,
    background_source: Path | None = None,
    check_cancel: Callable[[], None],
    progress: Callable[[int, str], None],
    cpu_threads: int | None = None,
) -> dict[str, Any]:
    options = render_options or {}
    aspect_ratio = options.get("aspect_ratio", "9:16")
    layout = options.get("layout", "blur")
    caption_style = options.get("caption_style", "neon")
    template = options.get("template", "none")
    template_name = options.get("template_name", "")
    template_handle = options.get("template_handle", "")
    background_mode = options.get("background_mode", "none")
    background_color = options.get("background_color", "#181326")
    background_color2 = options.get("background_color2", "#542558")
    background_dim_percent = max(0, min(int(options.get("background_dim_percent", 22)), 80))
    card_padding_percent = max(0, min(int(options.get("card_padding_percent", 14)), 30))
    logo_position = options.get("logo_position", "top_right")
    logo_size_percent = max(5, min(int(options.get("logo_size_percent", 16)), 35))
    logo_opacity = max(10, min(int(options.get("logo_opacity", 85)), 100)) / 100
    credit_text = options.get("credit_text", "")
    watermark_text = options.get("watermark_text", "")
    opening_hook = options.get("opening_hook", "")
    opening_hook_seconds = max(2, min(int(options.get("opening_hook_seconds", 8)), 60))
    outro_text = options.get("outro_text", "")
    outro_seconds = max(1.5, min(float(options.get("outro_seconds", 3)), 8))
    caption_font = options.get("caption_font", "Arial")
    caption_size = int(options.get("caption_size", 50))
    caption_text_color = options.get("caption_text_color", "#FFFFFF")
    caption_outline_color = options.get("caption_outline_color", "#351633")
    caption_words_per_line = int(options.get("caption_words_per_line", 5))
    caption_animation = options.get("caption_animation", "static")
    music_volume = max(0, min(int(options.get("music_volume", 20)), 100)) / 100
    music_peak_volume = max(0, min(int(options.get("music_peak_volume", 85)), 100)) / 100
    music_riser_seconds = max(1, min(int(options.get("music_riser_seconds", 4)), 15))
    music_fade_seconds = max(0.0, min(float(options.get("music_fade_seconds", 1.5)), 5.0))
    auto_enhance = bool(options.get("auto_enhance", True))
    enhancement_strength = max(0, min(int(options.get("enhancement_strength", 65)), 100))
    portrait_cleanup = bool(options.get("portrait_cleanup", True))
    portrait_cleanup_strength = max(0, min(int(options.get("portrait_cleanup_strength", 45)), 100))
    dimensions = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}
    supported_layouts = {
        "blur", "blur_top", "blur_bottom", "fit", "fill", "fill_top", "fill_bottom",
        "gameplay_only", "facecam_overlay", "facecam_circle", "camera_top", "camera_bottom", "side_by_side", "no_facecam",
    }
    gameplay_box = options.get("gameplay_box")
    facecam_box = options.get("facecam_box")
    facecam_position = options.get("facecam_position", "top_right")
    facecam_size_percent = max(16, min(int(options.get("facecam_size_percent", 31)), 50))
    resolution = int(options.get("resolution", 1080))
    frame_rate = options.get("frame_rate", "source")
    if resolution not in {720, 1080, 2160}:
        raise ValueError("Choose 720p, 1080p, or 2160p output resolution.")
    if frame_rate not in {"source", 24, 30, 60}:
        raise ValueError("Choose the source frame rate, 24, 30, or 60 fps.")
    if aspect_ratio not in dimensions or layout not in supported_layouts or caption_style not in CAPTION_STYLES:
        raise ValueError("The selected output format or caption style is not supported.")
    base_width, base_height = dimensions[aspect_ratio]
    scale = resolution / 1080
    width, height = round(base_width * scale), round(base_height * scale)
    duration = end_seconds - start_seconds
    if start_seconds < 0 or duration <= 0 or duration > 600:
        raise ValueError("A rendered clip must be between 0 and 600 seconds long.")
    if not source.is_file():
        raise RuntimeError("The source recording is unavailable. Import it again before rendering.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg and restart ClipForge.")
    thread_count = max(1, min(int(cpu_threads or 4), os.cpu_count() or 1))
    if auto_enhance and enhancement_strength > 0:
        progress(14, "balancing_clip_color")
        enhancement = analyze_clip_color(
            source=source,
            start_seconds=start_seconds,
            duration_seconds=duration,
            strength_percent=enhancement_strength,
            cpu_threads=thread_count,
            check_cancel=check_cancel,
        )
    else:
        enhancement = dict(NEUTRAL_GRADE)
        enhancement["note"] = "Automatic color balancing is disabled or set to zero strength."
    facecam_layout = layout in {"facecam_overlay", "facecam_circle", "camera_top", "camera_bottom", "side_by_side"} and bool(facecam_box)
    cleanup_filters = portrait_cleanup_filters(portrait_cleanup_strength) if portrait_cleanup else ""
    facecam_cleanup_enabled = bool(cleanup_filters and facecam_layout)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_video = destination.with_name(f"{destination.stem}.rendering.mp4")
    ass_path = destination.with_suffix(".ass")
    srt, ass = subtitle_files(
        subtitles,
        caption_style=caption_style,
        width=width,
        height=height,
        watermark_text=watermark_text,
        opening_hook=opening_hook,
        opening_hook_seconds=opening_hook_seconds,
        outro_text=outro_text,
        outro_seconds=outro_seconds,
        template=template,
        template_name=template_name,
        template_handle=template_handle,
        credit_text=credit_text,
        clip_duration=duration,
        caption_font=caption_font,
        caption_size=caption_size,
        caption_text_color=caption_text_color,
        caption_outline_color=caption_outline_color,
        caption_words_per_line=caption_words_per_line,
        caption_animation=caption_animation,
    )
    _write_atomic(destination.with_suffix(".srt"), srt)
    _write_atomic(ass_path, ass)
    check_cancel()
    progress(22, "rendering_vertical")

    if layout in {"blur", "blur_top", "blur_bottom"}:
        foreground_y = "0" if layout == "blur_top" else "H-h" if layout == "blur_bottom" else "(H-h)/2"
        framing = (
            f"[0:v]split=2[bg][fg];[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=24:8[bgv];[fg]scale={width}:{height}:"
            "force_original_aspect_ratio=decrease:force_divisible_by=2[fgv];"
            f"[bgv][fgv]overlay=(W-w)/2:{foreground_y}[framed];"
        )
    elif layout == "fit":
        framing = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black[framed];"
    elif layout == "gameplay_only":
        if not gameplay_box:
            raise ValueError("Draw a gameplay region before choosing gameplay-only framing.")
        framing = f"[0:v]{_region_crop(gameplay_box)},scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[framed];"
    elif layout in {"facecam_overlay", "facecam_circle"}:
        if not facecam_box:
            raise ValueError("Draw a facecam region before choosing a camera layout.")
        camera_width = max(96, (round((min(width, height) if layout == "facecam_circle" else width) * facecam_size_percent / 100) // 2) * 2)
        camera_height = camera_width if layout == "facecam_circle" else max(96, (round(height * facecam_size_percent / 100) // 2) * 2)
        game_crop = f"{_region_crop(gameplay_box)}," if gameplay_box else ""
        margin_x = round(width * 0.04)
        margin_y = round(height * 0.04)
        overlay_position = {
            "top_left": f"{margin_x}:{margin_y}",
            "top_right": f"W-w-{margin_x}:{margin_y}",
            "bottom_left": f"{margin_x}:H-h-{margin_y}",
            "bottom_right": f"W-w-{margin_x}:H-h-{margin_y}",
            "bottom_center": f"(W-w)/2:H-h-{margin_y}",
        }.get(facecam_position, f"W-w-{margin_x}:{margin_y}")
        camera_filter = f"scale={camera_width}:{camera_height}:force_original_aspect_ratio=decrease:force_divisible_by=2,format=rgba"
        facecam_filter = f"{_region_crop(facecam_box)},"
        if facecam_cleanup_enabled:
            facecam_filter += f"scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p,{cleanup_filters},"
        if layout == "facecam_circle":
            camera_filter += ",geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte((X-W/2)*(X-W/2)+(Y-H/2)*(Y-H/2),(min(W,H)/2)*(min(W,H)/2)),alpha(X,Y),0)'"
        framing = (
            f"[0:v]split=2[bg][cam];[bg]{game_crop}scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[bgv];[cam]{facecam_filter}{camera_filter}[camv];"
            f"[bgv][camv]overlay={overlay_position}[framed];"
        )
    elif layout in {"camera_top", "camera_bottom"}:
        if not facecam_box:
            raise ValueError("Draw a facecam region before choosing a camera layout.")
        camera_height = (round(height * 0.34) // 2) * 2
        game_height = height - camera_height
        game_crop = f"{_region_crop(gameplay_box)}," if gameplay_box else ""
        facecam_filter = f"{_region_crop(facecam_box)},"
        if facecam_cleanup_enabled:
            facecam_filter += f"scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p,{cleanup_filters},"
        framing = (
            f"[0:v]split=2[game][cam];[game]{game_crop}scale={width}:{game_height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{game_height}[gamev];[cam]{facecam_filter}"
            f"scale={width}:{camera_height}:force_original_aspect_ratio=increase,crop={width}:{camera_height}[camv];"
        f"{('[camv][gamev]' if layout == 'camera_top' else '[gamev][camv]')}vstack=inputs=2[framed];"
        )
    elif layout == "side_by_side":
        if not facecam_box:
            raise ValueError("Draw a facecam region before choosing a camera layout.")
        gameplay_width = width // 2
        camera_width = width - gameplay_width
        game_crop = f"{_region_crop(gameplay_box)}," if gameplay_box else ""
        facecam_filter = f"{_region_crop(facecam_box)},"
        if facecam_cleanup_enabled:
            facecam_filter += f"scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p,{cleanup_filters},"
        framing = (
            f"[0:v]split=2[game][cam];[game]{game_crop}scale={gameplay_width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={gameplay_width}:{height}[gamev];[cam]{facecam_filter}"
            f"scale={camera_width}:{height}:force_original_aspect_ratio=increase,crop={camera_width}:{height}[camv];"
            "[gamev][camv]hstack=inputs=2[framed];"
        )
    else:
        crop_y = "0" if layout == "fill_top" else f"in_h-{height}" if layout == "fill_bottom" else f"(in_h-{height})/2"
        framing = f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:(in_w-{width})/2:{crop_y}[framed];"
    input_command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-filter_complex_threads", str(thread_count),
        "-ss", f"{start_seconds:.3f}", "-i", str(source),
    ]
    generated_gradient_path: Path | None = None
    next_input = 1
    background_input = None
    if background_mode == "image":
        if background_source is None or not background_source.is_file():
            raise ValueError("Upload a background image before rendering this style.")
        background_input = next_input
        next_input += 1
        input_command.extend(["-loop", "1", "-framerate", "30", "-i", str(background_source)])
    elif background_mode == "gradient":
        generated_gradient_path = destination.with_name(f".{destination.stem}-{uuid.uuid4().hex}.ppm")
        _write_gradient_ppm(generated_gradient_path, background_color, background_color2)
        background_input = next_input
        next_input += 1
        input_command.extend(["-loop", "1", "-framerate", "30", "-i", str(generated_gradient_path)])
    logo_input = None
    if logo_source is not None:
        if not logo_source.is_file():
            raise ValueError("The saved logo image is unavailable. Import it again.")
        logo_input = next_input
        next_input += 1
        input_command.extend(["-loop", "1", "-framerate", "30", "-i", str(logo_source)])

    filter_graph = framing
    current_video_label = "framed"
    if background_mode in {"blur", "color", "gradient", "image"}:
        pad_x = round(width * card_padding_percent / 100)
        pad_y = round(height * card_padding_percent / 100)
        card_width = max(2, ((width - 2 * pad_x) // 2) * 2)
        card_height = max(2, ((height - 2 * pad_y) // 2) * 2)
        filter_graph += f"[framed]scale={card_width}:{card_height}:force_original_aspect_ratio=decrease:force_divisible_by=2[card];"
        if background_mode == "color":
            clean_color = background_color.lstrip("#") if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(background_color)) else "181326"
            filter_graph += f"color=c=0x{clean_color}:s={width}x{height}:r=30:d={duration:.3f}[bgv];"
        elif background_mode == "blur":
            filter_graph += f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=24:8[bgblur];[bgblur]eq=brightness=-{background_dim_percent / 100:.2f}[bgv];"
        else:
            filter_graph += f"[{background_input}:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},eq=brightness=-{background_dim_percent / 100:.2f}[bgv];"
        filter_graph += "[bgv][card]overlay=(W-w)/2:(H-h)/2:shortest=1[styled];"
        current_video_label = "styled"

    if auto_enhance:
        filter_graph += (
            f"[{current_video_label}]eq=brightness={enhancement['brightness']:.4f}:"
            f"contrast={enhancement['contrast']:.4f}:saturation={enhancement['saturation']:.4f},"
            f"colorchannelmixer=rr={enhancement['red_gain']:.4f}:gg={enhancement['green_gain']:.4f}:"
            f"bb={enhancement['blue_gain']:.4f}[balanced];"
        )
        current_video_label = "balanced"

    if cleanup_filters and not facecam_cleanup_enabled:
        filter_graph += f"[{current_video_label}]{cleanup_filters}[cleaned];"
        current_video_label = "cleaned"

    if logo_input is not None:
        logo_width = max(48, round(width * logo_size_percent / 100))
        margin_x = round(width * 0.035)
        margin_y = round(height * 0.025)
        logo_position_expr = {
            "top_left": f"{margin_x}:{margin_y}",
            "top_right": f"W-w-{margin_x}:{margin_y}",
            "bottom_left": f"{margin_x}:H-h-{margin_y}",
            "bottom_right": f"W-w-{margin_x}:H-h-{margin_y}",
        }.get(logo_position, f"W-w-{margin_x}:{margin_y}")
        filter_graph += (
            f"[{logo_input}:v]scale={logo_width}:-1:force_original_aspect_ratio=decrease,format=rgba,"
            f"colorchannelmixer=aa={logo_opacity:.3f}[logo];"
            f"[{current_video_label}][logo]overlay={logo_position_expr}:shortest=1[withlogo];"
        )
        current_video_label = "withlogo"

    frame_rate_filter = "" if frame_rate == "source" else f"fps={frame_rate},"
    filter_graph += f"[{current_video_label}]{frame_rate_filter}subtitles=filename='{ass_path.name}'[v]"
    audio_map = ["-map", "0:a:0?"]
    if music_source is not None:
        music_input = next_input
        input_command.extend(["-stream_loop", "-1", "-i", str(music_source)])
        source_has_audio = bool(probe_video(source).get("audio", {}).get("codec"))
        fade = min(music_fade_seconds, duration / 2)
        riser = min(float(music_riser_seconds), duration)
        ramp = f"{music_volume:.3f}+({music_peak_volume - music_volume:.3f})*min(t/{max(0.1, riser):.3f},1)"
        music_chain = f"[{music_input}:a:0]aresample=44100,volume='{ramp}':eval=frame"
        if fade > 0:
            music_chain += f",afade=t=in:st=0:d={fade:.3f},afade=t=out:st={max(0, duration - fade):.3f}:d={fade:.3f}"
        music_chain += "[bed]"
        filter_graph += ";" + music_chain
        if source_has_audio:
            filter_graph += ";[0:a:0]aresample=44100[game];[game][bed]amix=inputs=2:duration=first:dropout_transition=1[a]"
        else:
            filter_graph += ";[bed]anull[a]"
        audio_map = ["-map", "[a]"]
    command = [
        *input_command,
        "-t", f"{duration:.3f}",
        "-filter_complex", filter_graph, "-map", "[v]", *audio_map,
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
            "enhancement": {
                "auto_enhance": auto_enhance,
                "strength_percent": enhancement_strength,
                "portrait_cleanup": portrait_cleanup,
                "portrait_cleanup_strength": portrait_cleanup_strength,
                "grade": enhancement,
                "facecam_cleanup_applied": facecam_cleanup_enabled,
            },
            "settings": {
                "aspect_ratio": aspect_ratio, "format_preset": options.get("format_preset", "youtube_shorts"),
                "resolution": resolution, "frame_rate": frame_rate, "layout": layout, "caption_style": caption_style,
                "template": template, "template_name": template_name, "template_handle": template_handle,
                "background_mode": background_mode, "background_color": background_color, "background_color2": background_color2,
                "background_asset_id": options.get("background_asset_id"), "background_name": options.get("background_name", ""),
                "background_dim_percent": background_dim_percent, "card_padding_percent": card_padding_percent,
                "gameplay_box": gameplay_box, "facecam_box": facecam_box,
                "facecam_position": facecam_position, "facecam_size_percent": facecam_size_percent,
                "watermark_text": watermark_text, "logo_asset_id": options.get("logo_asset_id"), "logo_name": options.get("logo_name", ""),
                "logo_position": logo_position, "logo_size_percent": logo_size_percent, "logo_opacity": logo_opacity * 100,
                "credit_text": credit_text, "opening_hook": opening_hook, "opening_hook_seconds": opening_hook_seconds,
                "outro_text": outro_text, "outro_seconds": outro_seconds,
                "caption_font": caption_font,
                "caption_size": caption_size, "caption_text_color": caption_text_color,
                "caption_outline_color": caption_outline_color, "caption_words_per_line": caption_words_per_line,
                "caption_animation": caption_animation,
                "auto_enhance": auto_enhance, "enhancement_strength": enhancement_strength,
                "portrait_cleanup": portrait_cleanup, "portrait_cleanup_strength": portrait_cleanup_strength,
                "music_asset_id": options.get("music_asset_id"), "music_name": options.get("music_name", ""),
                "music_volume": music_volume * 100, "music_peak_volume": music_peak_volume * 100,
                "music_riser_seconds": music_riser_seconds, "music_fade_seconds": music_fade_seconds,
            },
        }
    except Exception:
        temporary_video.unlink(missing_ok=True)
        raise
    finally:
        if generated_gradient_path is not None:
            generated_gradient_path.unlink(missing_ok=True)
