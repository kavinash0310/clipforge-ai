from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import DATA_DIR, DATABASE_PATH, OUTPUT_DIR


DEFAULT_SETTINGS: dict[str, Any] = {
    "automation_mode": "semi_automatic",
    "processing_paused": False,
    "emergency_stop": False,
    "max_concurrent_jobs": 1,
    "cpu_limit_percent": 75,
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "qwen3.5:4b",
    "transcription_model": "base",
    "public_uploads_enabled": False,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    path = database_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def database_session(database_path: Path | None = None):
    connection = connect(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: Path | None = None) -> None:
    data_directory = database_path.parent if database_path else DATA_DIR
    data_directory.mkdir(parents=True, exist_ok=True)
    if database_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with database_session(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recordings (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                duration_seconds REAL,
                status TEXT NOT NULL DEFAULT 'imported',
                authorized INTEGER NOT NULL DEFAULT 0 CHECK (authorized IN (0, 1)),
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0,
                stage TEXT NOT NULL DEFAULT 'queued',
                error_message TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recording_metadata (
                recording_id TEXT PRIMARY KEY REFERENCES recordings(id) ON DELETE CASCADE,
                metadata_json TEXT NOT NULL,
                probed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recording_transcripts (
                recording_id TEXT PRIMARY KEY REFERENCES recordings(id) ON DELETE CASCADE,
                language TEXT,
                language_probability REAL,
                model_name TEXT NOT NULL,
                device TEXT NOT NULL,
                transcript_path TEXT NOT NULL,
                subtitle_path TEXT NOT NULL,
                segments_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recording_analyses (
                recording_id TEXT PRIMARY KEY REFERENCES recordings(id) ON DELETE CASCADE,
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clips (
                id TEXT PRIMARY KEY,
                recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
                file_path TEXT,
                title TEXT,
                score REAL,
                start_seconds REAL NOT NULL DEFAULT 0,
                end_seconds REAL NOT NULL DEFAULT 0,
                reason_json TEXT NOT NULL DEFAULT '[]',
                signals_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'candidate',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                clip_id TEXT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewer_note TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS publish_events (
                id TEXT PRIMARY KEY,
                clip_id TEXT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                remote_id TEXT,
                privacy_status TEXT NOT NULL DEFAULT 'private',
                status TEXT NOT NULL DEFAULT 'queued',
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_updated
                ON jobs(status, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_clips_status_created
                ON clips(status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_approvals_status_created
                ON approvals(status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_publish_events_status_updated
                ON publish_events(status, updated_at DESC);
            """
        )
        clip_columns = {row["name"] for row in connection.execute("PRAGMA table_info(clips)").fetchall()}
        for name, declaration in (
            ("start_seconds", "REAL NOT NULL DEFAULT 0"),
            ("end_seconds", "REAL NOT NULL DEFAULT 0"),
            ("reason_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("signals_json", "TEXT NOT NULL DEFAULT '{}'"),
        ):
            if name not in clip_columns:
                connection.execute(f"ALTER TABLE clips ADD COLUMN {name} {declaration}")
        timestamp = utc_now()
        for key, value in DEFAULT_SETTINGS.items():
            connection.execute(
                "INSERT OR IGNORE INTO app_settings(key, value_json, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), timestamp),
            )


def read_settings(database_path: Path | None = None) -> dict[str, Any]:
    with database_session(database_path) as connection:
        rows = connection.execute(
            "SELECT key, value_json FROM app_settings ORDER BY key"
        ).fetchall()
    settings = dict(DEFAULT_SETTINGS)
    for row in rows:
        settings[row["key"]] = json.loads(row["value_json"])
    return settings


def write_settings(updates: dict[str, Any], database_path: Path | None = None) -> dict[str, Any]:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        for key, value in updates.items():
            connection.execute(
                """
                INSERT INTO app_settings(key, value_json, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), timestamp),
            )
    return read_settings(database_path)


def read_overview(database_path: Path | None = None) -> dict[str, Any]:
    with database_session(database_path) as connection:
        recordings = connection.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN status IN ('ready', 'analyzed') THEN 1 ELSE 0 END) AS ready FROM recordings"
        ).fetchone()
        clips = connection.execute("SELECT COUNT(*) AS total FROM clips").fetchone()
        jobs = connection.execute(
            """
            SELECT
                SUM(CASE WHEN status IN ('queued', 'running', 'paused') THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed
            FROM jobs
            """
        ).fetchone()
        approvals = connection.execute(
            "SELECT COUNT(*) AS total FROM approvals WHERE status = 'pending'"
        ).fetchone()
        published = connection.execute(
            "SELECT COUNT(*) AS total FROM publish_events WHERE status = 'complete'"
        ).fetchone()
        recent_jobs = connection.execute(
            """
            SELECT jobs.id, jobs.job_type, jobs.status, jobs.progress, jobs.stage,
                   jobs.updated_at, recordings.display_name AS recording_name
            FROM jobs
            LEFT JOIN recordings ON recordings.id = jobs.recording_id
            ORDER BY jobs.updated_at DESC
            LIMIT 6
            """
        ).fetchall()

    return {
        "recordings_total": recordings["total"] or 0,
        "recordings_ready": recordings["ready"] or 0,
        "clips_total": clips["total"] or 0,
        "jobs_active": jobs["active"] or 0,
        "jobs_failed": jobs["failed"] or 0,
        "approvals_pending": approvals["total"] or 0,
        "published_total": published["total"] or 0,
        "recent_jobs": [dict(row) for row in recent_jobs],
        "updated_at": utc_now(),
    }


def create_recording(recording_id: str, file_path: str, display_name: str, authorized: bool, database_path: Path | None = None) -> None:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        existing = connection.execute(
            "SELECT id FROM recordings WHERE lower(file_path) = lower(?)",
            (file_path,),
        ).fetchone()
        if existing is not None:
            raise ValueError(existing["id"])
        connection.execute(
            "INSERT INTO recordings(id, file_path, display_name, status, authorized, created_at) VALUES (?, ?, ?, 'queued', ?, ?)",
            (recording_id, file_path, display_name, int(authorized), timestamp),
        )
        connection.execute(
            "INSERT INTO jobs(id, recording_id, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, 'inspect_recording', 'queued', 0, 'queued', ?, ?)",
            (f"job-{recording_id}", recording_id, timestamp, timestamp),
        )


def create_analysis_job(recording_id: str, database_path: Path | None = None) -> dict[str, Any]:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        recording = connection.execute(
            "SELECT status, authorized, duration_seconds FROM recordings WHERE id = ?",
            (recording_id,),
        ).fetchone()
        if recording is None:
            raise LookupError("Recording not found.")
        if not recording["authorized"]:
            raise PermissionError("This recording has no authorization confirmation.")
        active = connection.execute(
            "SELECT id, status FROM jobs WHERE recording_id = ? AND job_type = 'analyze_recording' AND status IN ('queued', 'running', 'paused') ORDER BY created_at DESC LIMIT 1",
            (recording_id,),
        ).fetchone()
        if active is not None:
            return {"id": active["id"], "recording_id": recording_id, "status": active["status"], "existing": True}
        if recording["status"] not in {"ready", "analyzed", "failed"}:
            raise RuntimeError("Wait for recording inspection to finish before analysis.")
        if recording["duration_seconds"] is None:
            raise RuntimeError("Recording inspection did not finish successfully. Retry inspection before analysis.")
        job_id = f"job-{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO jobs(id, recording_id, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, 'analyze_recording', 'queued', 0, 'queued', ?, ?)",
            (job_id, recording_id, timestamp, timestamp),
        )
        connection.execute(
            "UPDATE recordings SET status = 'queued' WHERE id = ?",
            (recording_id,),
        )
    return {"id": job_id, "recording_id": recording_id, "status": "queued", "existing": False}


def list_recordings() -> list[dict[str, Any]]:
    with database_session() as connection:
        rows = connection.execute(
            """
            SELECT recordings.id, recordings.file_path, recordings.display_name,
                   recordings.duration_seconds, recordings.status, recordings.authorized,
                   recordings.created_at, recording_metadata.metadata_json,
                   recording_metadata.probed_at, recording_transcripts.model_name AS transcript_model,
                   recording_transcripts.language AS transcript_language,
                   recording_transcripts.language_probability AS language_probability
            FROM recordings
            LEFT JOIN recording_metadata ON recording_metadata.recording_id = recordings.id
            LEFT JOIN recording_transcripts ON recording_transcripts.recording_id = recordings.id
            ORDER BY recordings.created_at DESC
            """
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["authorized"] = bool(item["authorized"])
        item["metadata"] = json.loads(item.pop("metadata_json")) if item.get("metadata_json") else None
        results.append(item)
    return results


def list_jobs(limit: int = 30) -> list[dict[str, Any]]:
    with database_session() as connection:
        rows = connection.execute(
            """
            SELECT jobs.id, jobs.recording_id, jobs.job_type, jobs.status, jobs.progress,
                   jobs.stage, jobs.error_message, jobs.attempt_count, jobs.created_at,
                   jobs.updated_at, recordings.display_name AS recording_name
            FROM jobs LEFT JOIN recordings ON recordings.id = jobs.recording_id
            ORDER BY jobs.updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def claim_next_job() -> dict[str, Any] | None:
    with database_session() as connection:
        row = connection.execute(
            "SELECT id, recording_id, job_type, attempt_count FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        timestamp = utc_now()
        changed = connection.execute(
            "UPDATE jobs SET status = 'running', stage = 'starting', progress = 3, attempt_count = attempt_count + 1, updated_at = ? WHERE id = ? AND status = 'queued'",
            (timestamp, row["id"]),
        ).rowcount
        if changed != 1:
            return None
        connection.execute(
            "UPDATE recordings SET status = 'processing' WHERE id = ?",
            (row["recording_id"],),
        )
        return dict(row)


def recover_interrupted_jobs() -> None:
    timestamp = utc_now()
    with database_session() as connection:
        rows = connection.execute(
            "SELECT DISTINCT recording_id FROM jobs WHERE status = 'running' AND recording_id IS NOT NULL"
        ).fetchall()
        connection.execute(
            "UPDATE jobs SET status = 'queued', stage = 'recovered', updated_at = ? WHERE status = 'running'",
            (timestamp,),
        )
        for row in rows:
            connection.execute(
                "UPDATE recordings SET status = 'queued' WHERE id = ?",
                (row["recording_id"],),
            )


def resume_paused_jobs() -> None:
    timestamp = utc_now()
    with database_session() as connection:
        rows = connection.execute(
            "SELECT DISTINCT recording_id FROM jobs WHERE status = 'paused' AND recording_id IS NOT NULL"
        ).fetchall()
        connection.execute(
            "UPDATE jobs SET status = 'queued', stage = 'queued', updated_at = ? WHERE status = 'paused'",
            (timestamp,),
        )
        for row in rows:
            connection.execute(
                "UPDATE recordings SET status = 'queued' WHERE id = ?",
                (row["recording_id"],),
            )


def update_job(job_id: str, *, status: str | None = None, progress: float | None = None, stage: str | None = None, error_message: str | None = None) -> None:
    updates = {"updated_at": utc_now()}
    for key, value in (("status", status), ("progress", progress), ("stage", stage), ("error_message", error_message)):
        if value is not None:
            updates[key] = value
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with database_session() as connection:
        connection.execute(
            f"UPDATE jobs SET {assignments} WHERE id = ?",
            (*updates.values(), job_id),
        )


def update_recording_status(recording_id: str, status: str, duration_seconds: float | None = None) -> None:
    with database_session() as connection:
        connection.execute(
            "UPDATE recordings SET status = ?, duration_seconds = COALESCE(?, duration_seconds) WHERE id = ?",
            (status, duration_seconds, recording_id),
        )


def save_recording_metadata(recording_id: str, metadata: dict[str, Any]) -> None:
    with database_session() as connection:
        connection.execute(
            """
            INSERT INTO recording_metadata(recording_id, metadata_json, probed_at) VALUES (?, ?, ?)
            ON CONFLICT(recording_id) DO UPDATE SET metadata_json = excluded.metadata_json,
                probed_at = excluded.probed_at
            """,
            (recording_id, json.dumps(metadata), utc_now()),
        )


def save_analysis_result(recording_id: str, result: dict[str, Any], candidates: list[dict[str, Any]], database_path: Path | None = None) -> None:
    transcript = result["transcript"]
    timestamp = utc_now()
    profile = result["audio_profile"].copy()
    profile.pop("energy_buckets", None)
    analysis = {
        "model": transcript["model"],
        "device": transcript["device"],
        "compute_type": transcript["compute_type"],
        "scene_cuts": result["scene_cuts"],
        "audio_profile": profile,
        "candidate_count": len(candidates),
        "scoring": {
            "method": "deterministic weighted signals",
            "weights": {"audio_energy": 0.34, "speech_context": 0.24, "excitement_cues": 0.27, "scene_changes": 0.15},
        },
    }
    with database_session(database_path) as connection:
        connection.execute(
            """
            INSERT INTO recording_transcripts(recording_id, language, language_probability, model_name, device, transcript_path, subtitle_path, segments_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recording_id) DO UPDATE SET language = excluded.language,
                language_probability = excluded.language_probability, model_name = excluded.model_name,
                device = excluded.device, transcript_path = excluded.transcript_path,
                subtitle_path = excluded.subtitle_path, segments_json = excluded.segments_json,
                created_at = excluded.created_at
            """,
            (
                recording_id, transcript["language"], transcript["language_probability"],
                transcript["model"], transcript["device"], result["transcript_path"],
                result["subtitle_path"], json.dumps(transcript["segments"], ensure_ascii=False), timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO recording_analyses(recording_id, analysis_json, created_at) VALUES (?, ?, ?) ON CONFLICT(recording_id) DO UPDATE SET analysis_json = excluded.analysis_json, created_at = excluded.created_at",
            (recording_id, json.dumps(analysis, ensure_ascii=False), timestamp),
        )
        connection.execute("DELETE FROM clips WHERE recording_id = ? AND status = 'candidate'", (recording_id,))
        for candidate in candidates:
            connection.execute(
                "INSERT INTO clips(id, recording_id, file_path, title, score, start_seconds, end_seconds, reason_json, signals_json, status, created_at) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, 'candidate', ?)",
                (
                    uuid.uuid4().hex, recording_id, candidate["title"], candidate["score"],
                    candidate["start_seconds"], candidate["end_seconds"],
                    json.dumps(candidate["reasons"], ensure_ascii=False),
                    json.dumps(candidate["signals"], ensure_ascii=False), timestamp,
                ),
            )
        connection.execute("UPDATE recordings SET status = 'analyzed' WHERE id = ?", (recording_id,))


def get_recording_analysis(recording_id: str, database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        recording = connection.execute("SELECT id FROM recordings WHERE id = ?", (recording_id,)).fetchone()
        if recording is None:
            return None
        transcript = connection.execute(
            "SELECT language, language_probability, model_name, device, transcript_path, subtitle_path, segments_json, created_at FROM recording_transcripts WHERE recording_id = ?",
            (recording_id,),
        ).fetchone()
        analysis = connection.execute(
            "SELECT analysis_json, created_at FROM recording_analyses WHERE recording_id = ?",
            (recording_id,),
        ).fetchone()
        clips = connection.execute(
            "SELECT id, title, score, start_seconds, end_seconds, reason_json, signals_json, status, created_at FROM clips WHERE recording_id = ? AND status = 'candidate' ORDER BY score DESC, start_seconds",
            (recording_id,),
        ).fetchall()
    if transcript is None:
        return {"recording_id": recording_id, "transcript": None, "analysis": None, "candidates": []}
    transcript_value = dict(transcript)
    transcript_value["segments"] = json.loads(transcript_value.pop("segments_json"))
    analysis_value = json.loads(analysis["analysis_json"]) if analysis else None
    candidate_values = []
    for row in clips:
        value = dict(row)
        value["reasons"] = json.loads(value.pop("reason_json"))
        value["signals"] = json.loads(value.pop("signals_json"))
        candidate_values.append(value)
    return {
        "recording_id": recording_id,
        "transcript": transcript_value,
        "analysis": analysis_value,
        "candidates": candidate_values,
    }


def get_job(job_id: str) -> dict[str, Any] | None:
    with database_session() as connection:
        row = connection.execute(
            "SELECT id, recording_id, job_type, status, progress, stage, error_message, attempt_count FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def retry_job(job_id: str, max_attempts: int = 3) -> dict[str, Any] | None:
    timestamp = utc_now()
    with database_session() as connection:
        row = connection.execute(
            "SELECT id, recording_id, status, attempt_count FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None or row["status"] != "failed" or row["attempt_count"] >= max_attempts:
            return None
        connection.execute(
            "UPDATE jobs SET status = 'queued', progress = 0, stage = 'queued', error_message = NULL, updated_at = ? WHERE id = ?",
            (timestamp, job_id),
        )
        connection.execute(
            "UPDATE recordings SET status = 'queued' WHERE id = ?",
            (row["recording_id"],),
        )
    return get_job(job_id)

