from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import tempfile
import zipfile
from uuid import uuid4
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.background import BackgroundTask

from .config import DATA_DIR, OUTPUT_DIR
from .clip_rendering import subtitle_files
from .database import (
    create_analysis_job,
    create_render_job,
    create_render_jobs_for_recording,
    create_youtube_upload_job,
    create_recording,
    create_transcript_clip,
    get_clip_metadata,
    get_clip_render_input,
    get_clip_youtube_upload_input,
    get_recording_source,
    get_recording_analysis,
    get_job,
    initialize_database,
    list_clips,
    list_jobs,
    list_youtube_publications,
    list_recordings,
    read_overview,
    read_settings,
    retry_job,
    queue_metadata_generation,
    save_clip_subtitles,
    save_clip_metadata,
    set_clip_rating,
    update_clip_range,
    utc_now,
    save_youtube_analytics,
    write_settings,
)
from .media import choose_video_file, validate_audio_path, validate_video_path
from .live_capture import live_capture, validate_local_stream_url
from .source_import import SourceImportError, download_direct_video, save_uploaded_music, save_uploaded_video
from .system_info import collect_system_info
from .worker import run_worker
from .youtube_api import YouTubeAPIError, channel_analytics
from .youtube_auth import CLIENT_SECRETS_PATH, youtube_oauth


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    automation_mode: Literal["manual", "semi_automatic", "automatic"] | None = None
    processing_paused: bool | None = None
    emergency_stop: bool | None = None
    max_concurrent_jobs: int | None = Field(default=None, ge=1, le=4)
    cpu_limit_percent: int | None = Field(default=None, ge=25, le=95)
    processing_schedule_enabled: bool | None = None
    processing_schedule_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    processing_schedule_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    processing_schedule_days: list[int] | None = Field(default=None, min_length=1, max_length=7)
    ollama_url: str | None = None
    ollama_model: str | None = None
    transcription_model: Literal["tiny", "base", "small"] | None = None
    public_uploads_enabled: bool | None = None

    @field_validator("ollama_url")
    @classmethod
    def validate_ollama_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip().rstrip("/")
        parsed = urlsplit(cleaned)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
            raise ValueError("Ollama must use a localhost URL in this local-first build.")
        return cleaned

    @field_validator("ollama_model")
    @classmethod
    def validate_ollama_model(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 120:
            raise ValueError("Enter a model name up to 120 characters.")
        return cleaned

    @field_validator("processing_schedule_days")
    @classmethod
    def validate_processing_schedule_days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if len(set(value)) != len(value) or any(day < 0 or day > 6 for day in value):
            raise ValueError("Schedule days must be unique values from 0 (Monday) through 6 (Sunday).")
        return sorted(value)


class RecordingImportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorized: bool
    auto_analyze: bool = False
    clip_count: int = Field(default=1, ge=1, le=100)
    clip_duration_seconds: int = Field(default=30, ge=15, le=45)
    moment_mix: Literal["balanced", "action", "dialogue"] = "balanced"
    transcription_language: Literal["auto", "en", "hi", "es", "fr", "de", "pt", "ja", "ko", "zh", "it", "ru", "ar"] = "auto"
    render_options: dict[str, Any] = Field(default_factory=dict)
    focus_prompt: str = Field(default="", max_length=160)

    @field_validator("render_options")
    @classmethod
    def normalize_render_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        return RenderOptions.model_validate(value).model_dump()

    @field_validator("focus_prompt")
    @classmethod
    def clean_focus_prompt(cls, value: str) -> str:
        return " ".join(value.split())


class RecordingImport(RecordingImportOptions):
    path: str = Field(min_length=1, max_length=2048)


class RecordingLinkImport(RecordingImportOptions):
    url: str = Field(min_length=8, max_length=4096)

    @field_validator("url")
    @classmethod
    def clean_url(cls, value: str) -> str:
        return value.strip()


class AnalyzeRecordingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_count: int = Field(default=1, ge=1, le=100)
    clip_duration_seconds: int = Field(default=30, ge=15, le=45)
    moment_mix: Literal["balanced", "action", "dialogue"] = "balanced"
    transcription_language: Literal["auto", "en", "hi", "es", "fr", "de", "pt", "ja", "ko", "zh", "it", "ru", "ar"] = "auto"
    render_options: dict[str, Any] = Field(default_factory=dict)
    focus_prompt: str = Field(default="", max_length=160)

    @field_validator("render_options")
    @classmethod
    def normalize_render_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        return RenderOptions.model_validate(value).model_dump()

    @field_validator("focus_prompt")
    @classmethod
    def clean_focus_prompt(cls, value: str) -> str:
        return " ".join(value.split())


class DownloadClipsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_ids: list[str] = Field(min_length=1, max_length=500)

    @field_validator("clip_ids")
    @classmethod
    def unique_clip_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Clip IDs must be unique.")
        return values


class YouTubeScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_ids: list[str] = Field(min_length=1, max_length=100)
    start_at: datetime
    interval_minutes: int = Field(default=90, ge=15, le=4320)

    @field_validator("clip_ids")
    @classmethod
    def unique_clip_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Clip IDs must be unique.")
        return values

    @field_validator("start_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Choose a date and time with a timezone.")
        return value


class SubtitleSegmentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float = Field(ge=0, le=600)
    end: float = Field(gt=0, le=600)
    text: str = Field(max_length=500)

    @field_validator("text")
    @classmethod
    def clean_subtitle_text(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_timing(self) -> "SubtitleSegmentEdit":
        if self.end <= self.start:
            raise ValueError("Subtitle end time must be after its start time.")
        return self


class SubtitleEdits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segments: list[SubtitleSegmentEdit] = Field(max_length=300)


class RenderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aspect_ratio: Literal["9:16", "1:1", "4:5", "16:9"] = "9:16"
    layout: Literal["blur", "blur_top", "blur_bottom", "fit", "fill", "fill_top", "fill_bottom"] = "blur"
    format_preset: Literal["youtube_shorts", "tiktok", "instagram_reels", "instagram_portrait", "square", "landscape", "custom"] = "custom"
    resolution: Literal[720, 1080, 2160] = 1080
    frame_rate: Literal["source", 24, 30, 60] = "source"
    caption_style: Literal["neon", "impact", "clean", "hormozi", "mrbeast"] = "neon"
    watermark_text: str = Field(default="", max_length=60)
    opening_hook: str = Field(default="", max_length=100)
    outro_text: str = Field(default="", max_length=100)
    caption_font: Literal["Arial", "Impact", "Tahoma", "Verdana"] = "Arial"
    caption_size: int = Field(default=50, ge=24, le=100)
    caption_text_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    caption_outline_color: str = Field(default="#351633", pattern=r"^#[0-9A-Fa-f]{6}$")
    caption_words_per_line: int = Field(default=5, ge=2, le=12)
    caption_animation: Literal["static", "word_highlight"] = "static"
    music_asset_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    music_name: str = Field(default="", max_length=180)
    music_volume: int = Field(default=20, ge=0, le=100)
    music_fade_seconds: float = Field(default=1.5, ge=0, le=5)

    @model_validator(mode="after")
    def apply_format_preset(self) -> "RenderOptions":
        ratio_by_preset = {
            "youtube_shorts": "9:16", "tiktok": "9:16", "instagram_reels": "9:16",
            "instagram_portrait": "4:5", "square": "1:1", "landscape": "16:9",
        }
        if self.format_preset in ratio_by_preset:
            self.aspect_ratio = ratio_by_preset[self.format_preset]
        return self

    @field_validator("watermark_text")
    @classmethod
    def clean_watermark_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("opening_hook")
    @classmethod
    def clean_opening_hook(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("outro_text")
    @classmethod
    def clean_outro_text(cls, value: str) -> str:
        return " ".join(value.split())


class LiveStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(min_length=8, max_length=2048)

    @field_validator("source_url")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return validate_local_stream_url(value)


class LiveClipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: Literal[15, 30, 45] = 30
    transcription_language: Literal["auto", "en", "hi", "es", "fr", "de", "pt", "ja", "ko", "zh", "it", "ru", "ar"] = "auto"
    render_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("render_options")
    @classmethod
    def normalize_render_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        return RenderOptions.model_validate(value).model_dump()


class ClipRatingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)


class TranscriptClipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_seconds: float = Field(ge=0, le=86400)
    clip_duration_seconds: int = Field(default=30, ge=15, le=45)


class ClipRangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_seconds: float = Field(ge=0, le=86400)
    end_seconds: float = Field(gt=0, le=86445)

    @model_validator(mode="after")
    def validate_range(self) -> "ClipRangeRequest":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Clip end time must be after its start time.")
        return self


class MetadataGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_name: str = Field(default="", max_length=80)
    tone: Literal["hype", "funny", "clean", "competitive"] = "hype"

    @field_validator("game_name")
    @classmethod
    def clean_game_name(cls, value: str) -> str:
        return " ".join(value.split())


class MetadataEditRequest(MetadataGenerateRequest):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=5000)
    hashtags: list[str] = Field(max_length=12)
    tags: list[str] = Field(max_length=20)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("hashtags", "tags")
    @classmethod
    def clean_tag_list(cls, values: list[str]) -> list[str]:
        return [" ".join(value.split())[:100] for value in values if value.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    worker_task = asyncio.create_task(run_worker(), name="clipforge-worker")
    try:
        yield
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
        live_capture.close()


app = FastAPI(
    title="ClipForge AI",
    version="0.1.0",
    description="Local-first gaming content production dashboard.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "clipforge-ai", "version": app.version}


@app.get("/api/live/status")
def live_status() -> dict[str, object]:
    return live_capture.status()


@app.post("/api/live/start")
def start_live_capture(payload: LiveStartRequest) -> dict[str, object]:
    try:
        return live_capture.start(payload.source_url)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/live/stop")
def stop_live_capture() -> dict[str, object]:
    return live_capture.stop()


@app.post("/api/live/clip", status_code=202)
def clip_live_capture(payload: LiveClipRequest) -> dict[str, Any]:
    try:
        path = validate_video_path(str(live_capture.clip_recent(payload.duration_seconds)))
        options = RecordingImportOptions(
            authorized=True,
            auto_analyze=True,
            clip_count=1,
            clip_duration_seconds=payload.duration_seconds,
            moment_mix="balanced",
            transcription_language=payload.transcription_language,
            render_options=payload.render_options,
        )
        return _register_recording(path, f"Live capture · {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}", options)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    return read_overview()


@app.get("/api/system")
def system_status() -> dict[str, Any]:
    settings = read_settings()
    return collect_system_info(settings["ollama_url"], settings["ollama_model"])


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return read_settings()


@app.post("/api/recordings/browse")
def browse_for_recording() -> dict[str, str | None]:
    try:
        return {"path": choose_video_file()}
    except RuntimeError as error:
        raise HTTPException(status_code=501, detail=str(error)) from error


@app.get("/api/recordings")
def recordings() -> list[dict[str, Any]]:
    return list_recordings()


@app.get("/api/recordings/{recording_id}/analysis")
def recording_analysis(recording_id: str) -> dict[str, Any]:
    result = get_recording_analysis(recording_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Recording not found.")
    return result


@app.get("/api/recordings/{recording_id}/source-preview")
def recording_source_preview(recording_id: str) -> FileResponse:
    source = get_recording_source(recording_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Recording not found.")
    if not source["authorized"]:
        raise HTTPException(status_code=403, detail="This recording is not available for preview.")
    try:
        path = validate_video_path(source["file_path"])
    except ValueError as error:
        raise HTTPException(status_code=404, detail="The source video is unavailable.") from error
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@app.get("/api/recordings/{recording_id}/subtitles")
def recording_subtitles(recording_id: str) -> FileResponse:
    result = get_recording_analysis(recording_id)
    if result is None or result["transcript"] is None:
        raise HTTPException(status_code=404, detail="Subtitles are not available for this recording.")
    subtitle_path = Path(result["transcript"]["subtitle_path"]).resolve()
    if not subtitle_path.is_relative_to(DATA_DIR.resolve()) or not subtitle_path.is_file():
        raise HTTPException(status_code=404, detail="Subtitle file is unavailable.")
    return FileResponse(subtitle_path, filename=f"{recording_id}.srt", media_type="application/x-subrip")


@app.get("/api/clips")
def clips() -> list[dict[str, Any]]:
    return list_clips()


@app.patch("/api/clips/{clip_id}/rating")
def rate_clip(clip_id: str, payload: ClipRatingRequest) -> dict[str, Any]:
    clip = set_clip_rating(clip_id, payload.rating)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip candidate not found.")
    return clip


@app.patch("/api/clips/{clip_id}/range")
def trim_clip(clip_id: str, payload: ClipRangeRequest) -> dict[str, Any]:
    try:
        clip = update_clip_range(clip_id, payload.start_seconds, payload.end_seconds)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip candidate not found.")
    return clip


@app.post("/api/recordings/{recording_id}/clips/from-transcript", status_code=201)
def clip_from_transcript(recording_id: str, payload: TranscriptClipRequest) -> dict[str, Any]:
    try:
        clip = create_transcript_clip(recording_id, payload.start_seconds, payload.clip_duration_seconds)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if clip is None:
        raise HTTPException(status_code=404, detail="Recording not found.")
    return clip


@app.post("/api/clips/{clip_id}/render", status_code=202)
def render_clip(clip_id: str, payload: RenderOptions = RenderOptions()) -> dict[str, Any]:
    try:
        return create_render_job(clip_id, render_options=payload.model_dump())
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/recordings/{recording_id}/clips/render", status_code=202)
def render_recording_clips(recording_id: str, payload: RenderOptions = RenderOptions()) -> dict[str, Any]:
    try:
        jobs = create_render_jobs_for_recording(recording_id, payload.model_dump())
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"jobs": jobs, "queued": sum(job["status"] == "queued" and not job["existing"] for job in jobs)}


@app.patch("/api/clips/{clip_id}/subtitles")
def edit_clip_subtitles(clip_id: str, payload: SubtitleEdits) -> dict[str, Any]:
    try:
        result = save_clip_subtitles(
            clip_id,
            [segment.model_dump() for segment in payload.segments],
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Clip candidate not found.")
    return result


@app.get("/api/clips/{clip_id}/subtitles")
def clip_subtitles(clip_id: str) -> Response:
    clip = get_clip_render_input(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip candidate not found.")
    srt, _ass = subtitle_files(clip["subtitles"])
    return Response(
        content=srt,
        media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{clip_id}.srt"'},
    )


@app.get("/api/clips/{clip_id}/metadata")
def clip_metadata(clip_id: str) -> dict[str, Any]:
    result = get_clip_metadata(clip_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Clip candidate not found.")
    return result


@app.post("/api/clips/{clip_id}/metadata/generate", status_code=202)
def generate_metadata(clip_id: str, payload: MetadataGenerateRequest) -> dict[str, Any]:
    try:
        return queue_metadata_generation(clip_id, payload.game_name, payload.tone)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@app.patch("/api/clips/{clip_id}/metadata")
def edit_clip_metadata(clip_id: str, payload: MetadataEditRequest) -> dict[str, Any]:
    try:
        result = save_clip_metadata(clip_id, payload.model_dump())
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Clip candidate not found.")
    return result


@app.get("/api/youtube/status")
def youtube_status() -> dict[str, Any]:
    return youtube_oauth.status()


@app.post("/api/youtube/connect")
def youtube_connect() -> dict[str, str]:
    try:
        return youtube_oauth.start()
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/youtube/connect")
def youtube_disconnect() -> dict[str, Any]:
    try:
        youtube_oauth.disconnect()
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"configured": CLIENT_SECRETS_PATH.is_file(), "connected": False, "status": "not_connected", "error": None, "client_secrets_path": str(CLIENT_SECRETS_PATH)}


@app.get("/api/youtube/publications")
def youtube_publications() -> list[dict[str, Any]]:
    return list_youtube_publications()


@app.post("/api/clips/{clip_id}/youtube-upload", status_code=202)
def queue_youtube_upload(clip_id: str) -> dict[str, Any]:
    try:
        youtube_oauth.access_token()
        clip = get_clip_youtube_upload_input(clip_id)
        if clip is None:
            raise LookupError("Clip candidate not found.")
        output_path = Path(clip["rendered_path"]).resolve() if clip.get("rendered_path") else None
        if output_path is None or not output_path.is_relative_to(OUTPUT_DIR.resolve()) or not output_path.is_file():
            raise RuntimeError("A completed local render is required before uploading.")
        if clip.get("upload_metadata_status") != "complete":
            raise RuntimeError("Wait for generated title, description, and tags before uploading.")
        result = create_youtube_upload_job(clip_id)
        if result["status"] == "failed":
            raise HTTPException(status_code=409, detail="This clip already has a failed YouTube publication. Retry its existing job to avoid a duplicate upload.")
        return result
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/youtube/schedule", status_code=202)
def schedule_youtube_clips(payload: YouTubeScheduleRequest) -> dict[str, Any]:
    start_at = payload.start_at.astimezone(UTC)
    if start_at < datetime.now(UTC) + timedelta(minutes=15):
        raise HTTPException(status_code=422, detail="Schedule the first video at least 15 minutes from now.")

    try:
        youtube_oauth.access_token()
        # Validate the complete batch before queuing anything.
        existing_publications = {
            item["clip_id"]: item
            for item in list_youtube_publications()
        }
        for clip_id in payload.clip_ids:
            if clip_id in existing_publications:
                raise RuntimeError("A clip can have one YouTube publication. Retry its failed upload or choose a clip without a publication record.")
            clip = get_clip_youtube_upload_input(clip_id)
            if clip is None:
                raise LookupError(f"Clip {clip_id} was not found.")
            if not clip["authorized"]:
                raise PermissionError("The source recording has no authorization confirmation.")
            output_path = Path(clip["rendered_path"]).resolve() if clip.get("rendered_path") else None
            if output_path is None or not output_path.is_relative_to(OUTPUT_DIR.resolve()) or not output_path.is_file():
                raise RuntimeError("Every clip must finish rendering before it can be scheduled.")
            if clip.get("upload_metadata_status") != "complete" or not clip.get("upload_title"):
                raise RuntimeError("Wait for generated title, description, and tags before scheduling.")

        scheduled = []
        for index, clip_id in enumerate(payload.clip_ids):
            scheduled_time = start_at + timedelta(minutes=payload.interval_minutes * index)
            scheduled_at = scheduled_time.isoformat(timespec="seconds").replace("+00:00", "Z")
            result = create_youtube_upload_job(clip_id, scheduled_at=scheduled_at)
            if result["status"] == "failed":
                raise HTTPException(status_code=409, detail="A clip in this batch has a failed publication. Retry it before scheduling a new batch.")
            scheduled.append({**result, "scheduled_at": scheduled_at})
        return {"scheduled": scheduled, "interval_minutes": payload.interval_minutes}
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/youtube/analytics/refresh")
def refresh_youtube_analytics() -> dict[str, Any]:
    try:
        youtube_oauth.access_token()
        publications = list_youtube_publications()
        video_ids = [
            item["remote_id"] for item in publications
            if item["status"] == "complete"
            and item["remote_id"]
            and (
                not item["scheduled_at"]
                or datetime.fromisoformat(item["scheduled_at"].replace("Z", "+00:00")) <= datetime.now(UTC)
            )
        ]
        metrics = channel_analytics(video_ids)
        return {"publications": save_youtube_analytics(metrics), "refreshed_at": utc_now()}
    except (RuntimeError, YouTubeAPIError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


def _clip_video_response(clip_id: str, *, download: bool) -> FileResponse:
    clip = get_clip_render_input(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip candidate not found.")
    if clip["status"] != "rendered":
        raise HTTPException(status_code=404, detail="Rendered clip is not available yet.")
    output_path = Path(clip["rendered_path"]).resolve() if clip.get("rendered_path") else None
    if output_path is None or not output_path.is_relative_to(OUTPUT_DIR.resolve()) or not output_path.is_file():
        raise HTTPException(status_code=404, detail="Rendered clip is not available yet.")
    return FileResponse(
        output_path,
        filename=f"{clip_id}.mp4",
        media_type="video/mp4",
        content_disposition_type="attachment" if download else "inline",
    )


@app.get("/api/clips/{clip_id}/preview")
def clip_preview(clip_id: str) -> FileResponse:
    return _clip_video_response(clip_id, download=False)


@app.get("/api/clips/{clip_id}/download")
def clip_download(clip_id: str) -> FileResponse:
    return _clip_video_response(clip_id, download=True)


@app.post("/api/clips/download-all")
def download_all_clips(payload: DownloadClipsRequest) -> FileResponse:
    paths: list[tuple[Path, str]] = []
    output_root = OUTPUT_DIR.resolve()
    for clip_id in payload.clip_ids:
        clip = get_clip_render_input(clip_id)
        if clip is None:
            raise HTTPException(status_code=404, detail=f"Clip {clip_id} was not found.")
        if not clip["authorized"]:
            raise HTTPException(status_code=403, detail="The source recording has no authorization confirmation.")
        if clip["status"] != "rendered":
            raise HTTPException(status_code=409, detail="Wait for every selected clip to finish rendering before downloading the bundle.")
        source = Path(clip["rendered_path"]).resolve() if clip.get("rendered_path") else None
        if source is None or not source.is_relative_to(output_root) or not source.is_file():
            raise HTTPException(status_code=404, detail="A rendered clip is unavailable in ClipForge output storage.")
        paths.append((source, f"{clip_id}.mp4"))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="clipforge-clips-", suffix=".zip", dir=OUTPUT_DIR, delete=False) as archive:
        archive_path = Path(archive.name)
    try:
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for source, archive_name in paths:
                bundle.write(source, arcname=archive_name)
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise
    return FileResponse(
        archive_path,
        filename="clipforge-clips.zip",
        media_type="application/zip",
        background=BackgroundTask(archive_path.unlink, missing_ok=True),
    )


@app.post("/api/recordings/{recording_id}/analyze", status_code=202)
def analyze_recording(
    recording_id: str,
    payload: AnalyzeRecordingRequest | None = None,
) -> dict[str, Any]:
    options = payload or AnalyzeRecordingRequest()
    try:
        return create_analysis_job(
            recording_id,
            clip_count=options.clip_count,
            clip_duration_seconds=options.clip_duration_seconds,
            moment_mix=options.moment_mix,
            transcription_language=options.transcription_language,
            render_options=options.render_options,
            focus_prompt=options.focus_prompt,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


def _register_recording(path: Path, display_name: str, options: RecordingImportOptions) -> dict[str, Any]:
    if not options.authorized:
        raise HTTPException(status_code=400, detail="Confirm that you own or are authorized to use this recording before importing it.")
    normalized_path = os.path.normcase(str(path.resolve()))
    recording_id = uuid4().hex
    auto_analysis = None
    if options.auto_analyze:
        auto_analysis = {
            "clip_count": options.clip_count,
            "clip_duration_seconds": options.clip_duration_seconds,
            "moment_mix": options.moment_mix,
            "transcription_language": options.transcription_language,
            "render_options": options.render_options,
            "focus_prompt": options.focus_prompt,
        }
    try:
        create_recording(recording_id, normalized_path, display_name, True, auto_analysis=auto_analysis)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=f"This recording is already in the library (ID {error.args[0]}).") from error
    return {
        "recording_id": recording_id,
        "job_id": f"job-{recording_id}",
        "status": "queued",
        "display_name": display_name,
        "auto_analyze": options.auto_analyze,
    }


@app.post("/api/recordings", status_code=202)
def import_recording(payload: RecordingImport) -> dict[str, Any]:
    try:
        path = validate_video_path(payload.path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _register_recording(path, path.name, payload)


@app.post("/api/recordings/upload", status_code=202)
async def upload_recording(
    request: Request,
    filename: str = Query(min_length=1, max_length=512),
    authorized: bool = Query(default=False),
    auto_analyze: bool = Query(default=True),
    clip_count: int = Query(default=1, ge=1, le=100),
    clip_duration_seconds: int = Query(default=30, ge=15, le=45),
    moment_mix: Literal["balanced", "action", "dialogue"] = Query(default="balanced"),
    transcription_language: Literal["auto", "en", "hi", "es", "fr", "de", "pt", "ja", "ko", "zh", "it", "ru", "ar"] = Query(default="auto"),
    render_options: str = Query(default="{}", max_length=3000),
    focus_prompt: str = Query(default="", max_length=160),
) -> dict[str, Any]:
    if not authorized:
        raise HTTPException(status_code=400, detail="Confirm that you own or are authorized to use this recording before importing it.")
    try:
        render_options_value = json.loads(render_options)
        if not isinstance(render_options_value, dict):
            raise ValueError("Render options must be a JSON object.")
        options = RecordingImportOptions(
            authorized=authorized,
            auto_analyze=auto_analyze,
            clip_count=clip_count,
            clip_duration_seconds=clip_duration_seconds,
            moment_mix=moment_mix,
            transcription_language=transcription_language,
            render_options=render_options_value,
            focus_prompt=focus_prompt,
        )
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        path, display_name = await save_uploaded_video(filename, request.headers.get("content-type"), request.stream())
        path = validate_video_path(str(path))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _register_recording(path, display_name, options)


@app.post("/api/music/upload", status_code=201)
async def upload_music(request: Request, filename: str = Query(min_length=1, max_length=512)) -> dict[str, str]:
    try:
        path, display_name = await save_uploaded_music(filename, request.stream())
        validate_audio_path(str(path))
    except (SourceImportError, ValueError, RuntimeError) as error:
        if "path" in locals():
            path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"asset_id": path.stem, "display_name": display_name}


@app.post("/api/recordings/import-link", status_code=202)
async def import_video_link(payload: RecordingLinkImport) -> dict[str, Any]:
    if not payload.authorized:
        raise HTTPException(status_code=400, detail="Confirm that you own or are authorized to use this recording before importing it.")
    try:
        path, display_name = await download_direct_video(payload.url)
        path = validate_video_path(str(path))
    except SourceImportError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _register_recording(path, display_name, payload)


@app.get("/api/jobs")
def jobs() -> list[dict[str, Any]]:
    return list_jobs()


@app.post("/api/jobs/{job_id}/retry")
def retry_processing_job(job_id: str) -> dict[str, Any]:
    if get_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    job = retry_job(job_id)
    if job is None:
        raise HTTPException(status_code=409, detail="This job is not retryable or has reached its retry limit.")
    return job


@app.patch("/api/settings")
def patch_settings(patch: SettingsPatch) -> dict[str, Any]:
    updates = {key: value for key, value in patch.model_dump(exclude_unset=True).items() if value is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one setting to update.")
    return write_settings(updates)


web_directory = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if web_directory.exists():
    app.mount("/assets", StaticFiles(directory=web_directory / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def frontend(path: str) -> FileResponse | JSONResponse:
        requested = (web_directory / path).resolve()
        if requested.is_relative_to(web_directory) and requested.is_file():
            return FileResponse(requested)
        index = web_directory / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(status_code=404, content={"detail": "Frontend bundle is missing."})

