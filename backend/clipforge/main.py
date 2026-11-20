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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import DATA_DIR
from .database import (
    create_analysis_job,
    create_recording,
    get_recording_analysis,
    get_job,
    initialize_database,
    list_jobs,
    list_recordings,
    read_overview,
    read_settings,
    retry_job,
    write_settings,
)
from .media import choose_video_file, validate_video_path
from .system_info import collect_system_info
from .worker import run_worker


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    automation_mode: Literal["manual", "semi_automatic", "automatic"] | None = None
    processing_paused: bool | None = None
    emergency_stop: bool | None = None
    max_concurrent_jobs: int | None = Field(default=None, ge=1, le=4)
    cpu_limit_percent: int | None = Field(default=None, ge=25, le=95)
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


class RecordingImport(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    authorized: bool


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

