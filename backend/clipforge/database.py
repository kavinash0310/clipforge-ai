from __future__ import annotations

import json
import sqlite3
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

            CREATE TABLE IF NOT EXISTS clips (
                id TEXT PRIMARY KEY,
                recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
                file_path TEXT,
                title TEXT,
                score REAL,
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
            "SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END) AS ready FROM recordings"
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

