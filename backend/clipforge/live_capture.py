from __future__ import annotations

import ipaddress
import shutil
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from .config import OUTPUT_DIR


SEGMENT_SECONDS = 5
SUPPORTED_DURATIONS = {15, 30, 45}


def validate_local_stream_url(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 2048 or any(character in cleaned for character in "\r\n\x00"):
        raise ValueError("Enter a valid local stream URL.")
    try:
        parsed = urlsplit(cleaned)
        host = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError("Enter a valid local stream URL with a valid port.") from error
    if parsed.scheme.lower() not in {"rtmp", "srt", "udp"}:
        raise ValueError("Live clipping accepts RTMP, SRT, or UDP streams from this PC only.")
    if not host or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Use a local stream address without credentials or a fragment.")
    is_loopback = host.lower() == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback:
        raise ValueError("The stream source must resolve to localhost, 127.0.0.1, or ::1.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("The stream port must be between 1 and 65535.")
    return cleaned


class LiveCaptureManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._session_id: str | None = None
        self._source_url: str | None = None
        self._session_dir: Path | None = None
        self._started_at: str | None = None
        self._log_path: Path | None = None

    def start(self, source_url: str) -> dict[str, object]:
        source_url = validate_local_stream_url(source_url)
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg and restart ClipForge.")
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RuntimeError("A live capture is already running. Stop it before starting another stream.")
            session_id = uuid4().hex
            session_dir = OUTPUT_DIR / "live" / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            log_path = session_dir / "capture.log"
            log_file = log_path.open("ab")
            command = [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "warning",
                "-y",
                "-i", source_url,
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c", "copy",
                "-f", "segment",
                "-segment_time", str(SEGMENT_SECONDS),
                "-segment_format", "mpegts",
                "-reset_timestamps", "1",
                str(session_dir / "segment-%06d.ts"),
            ]
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=log_file,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except OSError as error:
                log_file.close()
                raise RuntimeError(f"FFmpeg could not start the live capture: {error}") from error
            log_file.close()
            self._process = process
            self._session_id = session_id
            self._source_url = source_url
            self._session_dir = session_dir
            self._started_at = datetime.now(UTC).isoformat()
            self._log_path = log_path
            return self._status_locked()

    def stop(self) -> dict[str, object]:
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            return self._status_locked()

    def status(self) -> dict[str, object]:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict[str, object]:
        process = self._process
        running = process is not None and process.poll() is None
        segments = self._finished_segments_locked()
        error = None
        if process is not None and not running and process.returncode not in {0, -15} and self._log_path and self._log_path.is_file():
            try:
                error = self._log_path.read_text(encoding="utf-8", errors="replace")[-1000:].strip() or None
            except OSError:
                error = None
        return {
            "running": running,
            "session_id": self._session_id,
            "source_url": self._source_url,
            "started_at": self._started_at,
            "segment_count": len(segments),
            "available_seconds": len(segments) * SEGMENT_SECONDS,
            "error": error,
        }

    def _finished_segments_locked(self) -> list[Path]:
        if self._session_dir is None or not self._session_dir.is_dir():
            return []
        cutoff = time.time() - 0.8
        segments = sorted(
            (path for path in self._session_dir.glob("segment-*.ts") if path.stat().st_mtime <= cutoff),
            key=lambda path: path.name,
        )
        if len(segments) > 36:
            expired, segments = segments[:-36], segments[-36:]
            for path in expired:
                path.unlink(missing_ok=True)
        return segments

    def clip_recent(self, duration_seconds: int) -> Path:
        if duration_seconds not in SUPPORTED_DURATIONS:
            raise ValueError("Choose a recent clip length of 15, 30, or 45 seconds.")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg was not found on PATH. Install FFmpeg and restart ClipForge.")
        with self._lock:
            if self._session_dir is None or self._session_id is None:
                raise RuntimeError("Start a live capture before creating a clip.")
            session_dir = self._session_dir
            segments = self._finished_segments_locked()
        segment_count = (duration_seconds + SEGMENT_SECONDS - 1) // SEGMENT_SECONDS + 2
        selected = segments[-segment_count:]
        if len(selected) < (duration_seconds // SEGMENT_SECONDS):
            raise RuntimeError(f"Not enough live footage yet. Capture at least {duration_seconds} seconds first.")

        output_path = session_dir / f"live-clip-{uuid4().hex}.mp4"
        manifest_path = session_dir / f"concat-{uuid4().hex}.txt"
        manifest_lines = []
        for segment in selected:
            safe_path = str(segment.resolve()).replace("\\", "/").replace("'", "'\\''")
            manifest_lines.append(f"file '{safe_path}'")
        manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        seek_seconds = max(0, len(selected) * SEGMENT_SECONDS - duration_seconds)
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(manifest_path),
            "-ss", str(seek_seconds),
            "-t", str(duration_seconds),
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-c:a", "aac",
            "-movflags", "+faststart",
            str(output_path),
        ]
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as error:
            output_path.unlink(missing_ok=True)
            raise RuntimeError("FFmpeg timed out while preparing the live clip.") from error
        finally:
            manifest_path.unlink(missing_ok=True)
        if result.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            detail = (result.stderr or "").strip()[-800:]
            raise RuntimeError(f"FFmpeg could not create the live clip. {detail}".strip())
        return output_path

    def close(self) -> None:
        self.stop()


live_capture = LiveCaptureManager()
