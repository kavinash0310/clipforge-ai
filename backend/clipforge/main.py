from __future__ import annotations

import asyncio
import os
from uuid import uuid4
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import DATA_DIR, OUTPUT_DIR
from .clip_rendering import subtitle_files
from .database import (
    create_analysis_job,
    create_render_job,
    create_youtube_upload_job,
    create_recording,
    get_clip_metadata,
    get_clip_render_input,
    get_clip_youtube_upload_input,
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
    utc_now,
    save_youtube_analytics,
    write_settings,
)
from .media import choose_video_file, validate_video_path
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


class RecordingImport(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    authorized: bool


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


@app.post("/api/clips/{clip_id}/render", status_code=202)
def render_clip(clip_id: str) -> dict[str, Any]:
    try:
        return create_render_job(clip_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


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


@app.post("/api/youtube/analytics/refresh")
def refresh_youtube_analytics() -> dict[str, Any]:
    try:
        youtube_oauth.access_token()
        publications = list_youtube_publications()
        video_ids = [item["remote_id"] for item in publications if item["status"] == "complete" and item["remote_id"]]
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


@app.post("/api/recordings/{recording_id}/analyze", status_code=202)
def analyze_recording(recording_id: str) -> dict[str, Any]:
    try:
        return create_analysis_job(recording_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/recordings", status_code=202)
def import_recording(payload: RecordingImport) -> dict[str, Any]:
    if not payload.authorized:
        raise HTTPException(status_code=400, detail="Confirm that you own or are authorized to use this recording before importing it.")
    try:
        path = validate_video_path(payload.path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    normalized_path = os.path.normcase(str(path))
    recording_id = uuid4().hex
    try:
        create_recording(recording_id, normalized_path, path.name, True)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=f"This recording is already in the library (ID {error.args[0]}).") from error
    return {
        "recording_id": recording_id,
        "job_id": f"job-{recording_id}",
        "status": "queued",
        "display_name": path.name,
    }


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

