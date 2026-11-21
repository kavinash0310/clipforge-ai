from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR


VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mkv", ".mov", ".avi", ".webm", ".mpeg", ".mpg"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".opus"}


def validate_video_path(path_value: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError("That file does not exist or is not a regular file.")
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Choose a supported video file (MP4, MKV, MOV, AVI, or WebM).")
    if path.stat().st_size == 0:
        raise ValueError("The selected video file is empty.")
    return path


def validate_audio_path(path_value: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.exists() or not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS or path.stat().st_size == 0:
        raise ValueError("That audio file is unavailable or uses an unsupported format.")
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe was not found on PATH. Install FFmpeg and restart ClipForge.")
    result = subprocess.run(
        [executable, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0 or result.stdout.strip() != "audio":
        raise ValueError("The selected file does not contain a readable audio stream.")
    return path


def resolve_music_asset(asset_id: str) -> Path:
    import re

    if not re.fullmatch(r"[a-f0-9]{32}", asset_id):
        raise ValueError("The selected music asset is invalid.")
    directory = OUTPUT_DIR / "assets" / "music"
    candidates = list(directory.glob(f"{asset_id}.*"))
    if len(candidates) != 1:
        raise ValueError("The selected music file is unavailable. Import it again.")
    return validate_audio_path(str(candidates[0]))


def resolve_image_asset(asset_id: str) -> Path:
    import re

    if not re.fullmatch(r"[a-f0-9]{32}", asset_id):
        raise ValueError("The selected image asset is invalid.")
    directory = OUTPUT_DIR / "assets" / "images"
    candidates = list(directory.glob(f"{asset_id}.*"))
    if len(candidates) != 1 or candidates[0].suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("The selected image is unavailable. Import it again.")
    if not candidates[0].is_file() or candidates[0].stat().st_size == 0:
        raise ValueError("The selected image is unavailable. Import it again.")
    return candidates[0].resolve()


def probe_video(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe was not found on PATH. Install FFmpeg and restart ClipForge.")
    command = [
        executable,
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("ffprobe timed out while reading the selected video.") from error
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[-800:]
        raise RuntimeError(f"ffprobe could not read this video. {detail}".strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("ffprobe returned invalid media metadata.") from error

    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if video is None:
        raise RuntimeError("The selected file does not contain a video stream.")
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    format_info = payload.get("format", {})
    duration_value = format_info.get("duration") or video.get("duration")
    try:
        duration = float(duration_value) if duration_value is not None else None
    except (ValueError, TypeError):
        duration = None
    stat = path.stat()
    return {
        "container": format_info.get("format_name"),
        "duration_seconds": duration,
        "size_bytes": stat.st_size,
        "modified_at": stat.st_mtime,
        "video": {
            "codec": video.get("codec_name"),
            "width": video.get("width"),
            "height": video.get("height"),
            "frame_rate": video.get("avg_frame_rate"),
            "pixel_format": video.get("pix_fmt"),
        },
        "audio": {
            "codec": audio.get("codec_name") if audio else None,
            "sample_rate": audio.get("sample_rate") if audio else None,
            "channels": audio.get("channels") if audio else None,
        },
    }


def choose_video_file() -> str | None:
    if os.name != "nt":
        raise RuntimeError("The native file picker is available in the Windows build only.")
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as error:
        raise RuntimeError("Python's Windows file picker is unavailable in this installation.") from error

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title="Choose a gaming recording",
            filetypes=[("Video recordings", "*.mp4 *.m4v *.mkv *.mov *.avi *.webm *.mpeg *.mpg"), ("All files", "*.*")],
        )
    except tk.TclError as error:
        raise RuntimeError(f"The Windows file picker could not open: {error}") from error
    finally:
        root.destroy()
    return str(Path(selected).resolve()) if selected else None

