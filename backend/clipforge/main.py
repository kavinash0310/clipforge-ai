from __future__ import annotations

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
from .database import initialize_database, read_overview, read_settings, write_settings
from .system_info import collect_system_info


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    automation_mode: Literal["manual", "semi_automatic", "automatic"] | None = None
    processing_paused: bool | None = None
    emergency_stop: bool | None = None
    max_concurrent_jobs: int | None = Field(default=None, ge=1, le=4)
    cpu_limit_percent: int | None = Field(default=None, ge=25, le=95)
    ollama_url: str | None = None
    ollama_model: str | None = None
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


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
    allow_methods=["GET", "PATCH", "OPTIONS"],
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

