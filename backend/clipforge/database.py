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
    "processing_schedule_enabled": False,
    "processing_schedule_start": "22:00",
    "processing_schedule_end": "06:00",
    "processing_schedule_days": [0, 1, 2, 3, 4, 5, 6],
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
                clip_id TEXT REFERENCES clips(id) ON DELETE SET NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
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
                subtitle_segments_json TEXT NOT NULL DEFAULT '[]',
                render_metadata_json TEXT NOT NULL DEFAULT '{}',
                rendered_at TEXT,
                status TEXT NOT NULL DEFAULT 'candidate',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS clip_metadata (
                clip_id TEXT PRIMARY KEY REFERENCES clips(id) ON DELETE CASCADE,
                game_name TEXT NOT NULL DEFAULT '',
                tone TEXT NOT NULL DEFAULT 'hype',
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                hashtags_json TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                provider TEXT NOT NULL DEFAULT 'template',
                model_name TEXT,
                status TEXT NOT NULL DEFAULT 'empty',
                generation_note TEXT,
                error_message TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS publish_events (
                id TEXT PRIMARY KEY,
                clip_id TEXT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
                job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
                platform TEXT NOT NULL,
                remote_id TEXT,
                privacy_status TEXT NOT NULL DEFAULT 'private',
                status TEXT NOT NULL DEFAULT 'queued',
                progress REAL NOT NULL DEFAULT 0,
                analytics_json TEXT NOT NULL DEFAULT '{}',
                analytics_updated_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status_updated
                ON jobs(status, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_clips_status_created
                ON clips(status, created_at DESC);
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
            ("subtitle_segments_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("render_metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("rendered_at", "TEXT"),
        ):
            if name not in clip_columns:
                connection.execute(f"ALTER TABLE clips ADD COLUMN {name} {declaration}")
        job_columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
        if "clip_id" not in job_columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN clip_id TEXT REFERENCES clips(id) ON DELETE SET NULL")
        if "payload_json" not in job_columns:
            connection.execute("ALTER TABLE jobs ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}' ")
        publication_columns = {row["name"] for row in connection.execute("PRAGMA table_info(publish_events)").fetchall()}
        for name, declaration in (
            ("job_id", "TEXT REFERENCES jobs(id) ON DELETE SET NULL"),
            ("progress", "REAL NOT NULL DEFAULT 0"),
            ("analytics_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("analytics_updated_at", "TEXT"),
            ("scheduled_at", "TEXT"),
        ):
            if name not in publication_columns:
                connection.execute(f"ALTER TABLE publish_events ADD COLUMN {name} {declaration}")
        legacy_approval_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'approvals'"
        ).fetchone()
        if legacy_approval_table is not None:
            approval_rows = connection.execute("SELECT COUNT(*) AS total FROM approvals").fetchone()["total"]
            if approval_rows == 0:
                connection.execute("DROP TABLE approvals")
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
        "published_total": published["total"] or 0,
        "recent_jobs": [dict(row) for row in recent_jobs],
        "updated_at": utc_now(),
    }


def create_recording(
    recording_id: str,
    file_path: str,
    display_name: str,
    authorized: bool,
    database_path: Path | None = None,
    *,
    auto_analysis: dict[str, int] | None = None,
) -> None:
    timestamp = utc_now()
    inspect_payload = json.dumps({"auto_analysis": auto_analysis}) if auto_analysis else None
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
            "INSERT INTO jobs(id, recording_id, payload_json, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, ?, 'inspect_recording', 'queued', 0, 'queued', ?, ?)",
            (f"job-{recording_id}", recording_id, inspect_payload, timestamp, timestamp),
        )


def create_analysis_job(
    recording_id: str,
    database_path: Path | None = None,
    *,
    clip_count: int = 1,
    clip_duration_seconds: int = 30,
) -> dict[str, Any]:
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
        payload = json.dumps({
            "clip_count": max(1, min(int(clip_count), 100)),
            "clip_duration_seconds": max(15, min(int(clip_duration_seconds), 45)),
            "auto_process": True,
        })
        connection.execute(
            "INSERT INTO jobs(id, recording_id, payload_json, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, ?, 'analyze_recording', 'queued', 0, 'queued', ?, ?)",
            (job_id, recording_id, payload, timestamp, timestamp),
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
            SELECT jobs.id, jobs.recording_id, jobs.clip_id, jobs.job_type, jobs.status, jobs.progress,
                   jobs.stage, jobs.error_message, jobs.attempt_count, jobs.created_at,
                   jobs.updated_at, recordings.display_name AS recording_name
            FROM jobs LEFT JOIN recordings ON recordings.id = jobs.recording_id
            ORDER BY jobs.updated_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def claim_next_job(
    *,
    allow_cpu_intensive: bool = True,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        query = "SELECT id, recording_id, clip_id, payload_json, job_type, attempt_count FROM jobs WHERE status = 'queued'"
        if not allow_cpu_intensive:
            query += " AND job_type NOT IN ('analyze_recording', 'render_clip', 'generate_metadata')"
        row = connection.execute(query + " ORDER BY created_at LIMIT 1").fetchone()
        if row is None:
            return None
        timestamp = utc_now()
        changed = connection.execute(
            "UPDATE jobs SET status = 'running', stage = 'starting', progress = 3, attempt_count = attempt_count + 1, updated_at = ? WHERE id = ? AND status = 'queued'",
            (timestamp, row["id"]),
        ).rowcount
        if changed != 1:
            return None
        if row["job_type"] == "render_clip" and row["clip_id"]:
            connection.execute("UPDATE clips SET status = 'rendering' WHERE id = ?", (row["clip_id"],))
        elif row["job_type"] == "generate_metadata" and row["clip_id"]:
            connection.execute("UPDATE clip_metadata SET status = 'generating', error_message = NULL, updated_at = ? WHERE clip_id = ?", (timestamp, row["clip_id"]))
        elif row["job_type"] == "youtube_upload" and row["clip_id"]:
            connection.execute("UPDATE publish_events SET status = 'uploading', error_message = NULL, updated_at = ? WHERE job_id = ?", (timestamp, row["id"]))
        else:
            connection.execute("UPDATE recordings SET status = 'processing' WHERE id = ?", (row["recording_id"],))
        return dict(row)


def recover_interrupted_jobs() -> None:
    timestamp = utc_now()
    with database_session() as connection:
        rows = connection.execute(
            "SELECT id, recording_id, clip_id, job_type FROM jobs WHERE status = 'running'"
        ).fetchall()
        connection.execute(
            "UPDATE jobs SET status = 'queued', stage = 'recovered', updated_at = ? WHERE status = 'running'",
            (timestamp,),
        )
        for row in rows:
            if row["job_type"] == "render_clip" and row["clip_id"]:
                connection.execute("UPDATE clips SET status = 'queued' WHERE id = ?", (row["clip_id"],))
            elif row["job_type"] == "generate_metadata" and row["clip_id"]:
                connection.execute("UPDATE clip_metadata SET status = 'queued', updated_at = ? WHERE clip_id = ?", (timestamp, row["clip_id"]))
            elif row["job_type"] == "youtube_upload" and row["clip_id"]:
                connection.execute("UPDATE publish_events SET status = 'queued', updated_at = ? WHERE job_id = ?", (timestamp, row["id"]))
            elif row["recording_id"]:
                connection.execute("UPDATE recordings SET status = 'queued' WHERE id = ?", (row["recording_id"],))


def resume_paused_jobs() -> None:
    timestamp = utc_now()
    with database_session() as connection:
        rows = connection.execute(
            "SELECT id, recording_id, clip_id, job_type FROM jobs WHERE status = 'paused'"
        ).fetchall()
        connection.execute(
            "UPDATE jobs SET status = 'queued', stage = 'queued', updated_at = ? WHERE status = 'paused'",
            (timestamp,),
        )
        for row in rows:
            if row["job_type"] == "render_clip" and row["clip_id"]:
                connection.execute("UPDATE clips SET status = 'queued' WHERE id = ?", (row["clip_id"],))
            elif row["job_type"] == "generate_metadata" and row["clip_id"]:
                connection.execute("UPDATE clip_metadata SET status = 'queued', updated_at = ? WHERE clip_id = ?", (timestamp, row["clip_id"]))
            elif row["job_type"] == "youtube_upload" and row["clip_id"]:
                connection.execute("UPDATE publish_events SET status = 'queued', updated_at = ? WHERE job_id = ?", (timestamp, row["id"]))
            elif row["recording_id"]:
                connection.execute("UPDATE recordings SET status = 'queued' WHERE id = ?", (row["recording_id"],))


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


def save_analysis_result(recording_id: str, result: dict[str, Any], candidates: list[dict[str, Any]], database_path: Path | None = None) -> list[str]:
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
        candidate_ids = []
        for candidate in candidates:
            candidate_start = float(candidate["start_seconds"])
            candidate_end = float(candidate["end_seconds"])
            clipped_segments = []
            for segment in transcript["segments"]:
                segment_start = max(candidate_start, float(segment["start"]))
                segment_end = min(candidate_end, float(segment["end"]))
                if segment_end > segment_start:
                    clipped_segments.append({
                        "start": round(segment_start - candidate_start, 3),
                        "end": round(segment_end - candidate_start, 3),
                        "text": str(segment.get("text", "")).strip(),
                    })
            candidate_id = uuid.uuid4().hex
            candidate_ids.append(candidate_id)
            connection.execute(
                "INSERT INTO clips(id, recording_id, file_path, title, score, start_seconds, end_seconds, reason_json, signals_json, subtitle_segments_json, status, created_at) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?)",
                (
                    candidate_id, recording_id, candidate["title"], candidate["score"],
                    candidate["start_seconds"], candidate["end_seconds"],
                    json.dumps(candidate["reasons"], ensure_ascii=False),
                    json.dumps(candidate["signals"], ensure_ascii=False),
                    json.dumps(clipped_segments, ensure_ascii=False), timestamp,
                ),
            )
        connection.execute("UPDATE recordings SET status = 'analyzed' WHERE id = ?", (recording_id,))
    return candidate_ids


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
            "SELECT id, title, score, start_seconds, end_seconds, reason_json, signals_json, subtitle_segments_json, render_metadata_json, rendered_at, status, created_at FROM clips WHERE recording_id = ? ORDER BY score DESC, start_seconds",
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
        value["subtitles"] = json.loads(value.pop("subtitle_segments_json"))
        value["render_metadata"] = json.loads(value.pop("render_metadata_json"))
        candidate_values.append(value)
    return {
        "recording_id": recording_id,
        "transcript": transcript_value,
        "analysis": analysis_value,
        "candidates": candidate_values,
    }


def get_job(job_id: str, database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        row = connection.execute(
            "SELECT id, recording_id, clip_id, job_type, status, progress, stage, error_message, attempt_count FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def _clip_from_row(row: sqlite3.Row) -> dict[str, Any]:
    clip = dict(row)
    clip["reasons"] = json.loads(clip.pop("reason_json"))
    clip["signals"] = json.loads(clip.pop("signals_json"))
    clip["subtitles"] = json.loads(clip.pop("subtitle_segments_json"))
    clip["render_metadata"] = json.loads(clip.pop("render_metadata_json"))
    clip["upload_hashtags"] = json.loads(clip.pop("upload_hashtags_json", "[]"))
    clip["upload_tags"] = json.loads(clip.pop("upload_tags_json", "[]"))
    clip["upload_title"] = clip.get("upload_title") or clip.get("title") or "Gaming highlight"
    clip["upload_description"] = clip.get("upload_description") or ""
    rendered_file_exists = bool(clip.get("file_path") and Path(clip["file_path"]).is_file())
    if clip["status"] == "rendered" and not rendered_file_exists:
        clip["status"] = "failed"
    clip["preview_url"] = f"/api/clips/{clip['id']}/preview" if clip["status"] == "rendered" and rendered_file_exists else None
    clip.pop("file_path", None)
    return clip


def list_clips(database_path: Path | None = None) -> list[dict[str, Any]]:
    with database_session(database_path) as connection:
        rows = connection.execute(
            """
            SELECT clips.id, clips.recording_id, recordings.display_name AS recording_name,
                   clips.file_path, clips.title, clips.score, clips.start_seconds, clips.end_seconds,
                   clips.reason_json, clips.signals_json, clips.subtitle_segments_json,
                   clips.render_metadata_json, clips.rendered_at, clips.status, clips.created_at,
                   clip_metadata.title AS upload_title, clip_metadata.description AS upload_description,
                   COALESCE(clip_metadata.hashtags_json, '[]') AS upload_hashtags_json,
                   COALESCE(clip_metadata.tags_json, '[]') AS upload_tags_json,
                   COALESCE(clip_metadata.status, 'empty') AS upload_metadata_status
            FROM clips JOIN recordings ON recordings.id = clips.recording_id
            LEFT JOIN clip_metadata ON clip_metadata.clip_id = clips.id
            ORDER BY clips.score DESC, clips.created_at DESC
            """
        ).fetchall()
    return [_clip_from_row(row) for row in rows]


def get_clip(clip_id: str, database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        row = connection.execute(
            """
            SELECT clips.id, clips.recording_id, recordings.display_name AS recording_name,
                   clips.file_path, clips.title, clips.score, clips.start_seconds, clips.end_seconds,
                   clips.reason_json, clips.signals_json, clips.subtitle_segments_json,
                   clips.render_metadata_json, clips.rendered_at, clips.status, clips.created_at
            FROM clips JOIN recordings ON recordings.id = clips.recording_id
            WHERE clips.id = ?
            """,
            (clip_id,),
        ).fetchone()
    return _clip_from_row(row) if row else None


def get_clip_render_input(clip_id: str, database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        row = connection.execute(
            """
            SELECT clips.id, clips.recording_id, clips.start_seconds, clips.end_seconds,
                   clips.subtitle_segments_json, clips.status, clips.file_path AS rendered_path,
                   recordings.file_path,
                   recordings.duration_seconds, recordings.authorized
            FROM clips JOIN recordings ON recordings.id = clips.recording_id
            WHERE clips.id = ?
            """,
            (clip_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        **dict(row),
        "authorized": bool(row["authorized"]),
        "subtitles": json.loads(row["subtitle_segments_json"]),
    }


def get_clip_youtube_upload_input(clip_id: str, database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        row = connection.execute(
            """
            SELECT clips.id, clips.recording_id, clips.title AS candidate_title, clips.status AS clip_status,
                   clips.file_path AS rendered_path, recordings.authorized,
                   COALESCE(NULLIF(clip_metadata.title, ''), clips.title, 'Gaming highlight') AS upload_title,
                   COALESCE(clip_metadata.description, '') AS upload_description,
                   COALESCE(clip_metadata.hashtags_json, '[]') AS hashtags_json,
                   COALESCE(clip_metadata.tags_json, '[]') AS tags_json,
                   COALESCE(clip_metadata.status, 'empty') AS upload_metadata_status
            FROM clips
            JOIN recordings ON recordings.id = clips.recording_id
            LEFT JOIN clip_metadata ON clip_metadata.clip_id = clips.id
            WHERE clips.id = ?
            """,
            (clip_id,),
        ).fetchone()
    if row is None:
        return None
    value = dict(row)
    value["authorized"] = bool(value["authorized"])
    value["hashtags"] = json.loads(value.pop("hashtags_json"))
    value["tags"] = json.loads(value.pop("tags_json"))
    return value


def create_render_job(clip_id: str, database_path: Path | None = None) -> dict[str, Any]:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        clip = connection.execute(
            """
            SELECT clips.status, clips.file_path, clips.recording_id, clips.subtitle_segments_json,
                   recordings.authorized
            FROM clips JOIN recordings ON recordings.id = clips.recording_id
            WHERE clips.id = ?
            """,
            (clip_id,),
        ).fetchone()
        if clip is None:
            raise LookupError("Clip candidate not found.")
        if not clip["authorized"]:
            raise PermissionError("The source recording has no authorization confirmation.")
        active = connection.execute(
            "SELECT id, status FROM jobs WHERE clip_id = ? AND job_type = 'render_clip' AND status IN ('queued', 'running', 'paused') ORDER BY created_at DESC LIMIT 1",
            (clip_id,),
        ).fetchone()
        if active is not None:
            return {"id": active["id"], "clip_id": clip_id, "status": active["status"], "existing": True}
        if clip["status"] == "rendered" and clip["file_path"] and Path(clip["file_path"]).is_file():
            return {"id": None, "clip_id": clip_id, "status": "rendered", "existing": True}
        job_id = f"job-{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO jobs(id, recording_id, clip_id, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, ?, 'render_clip', 'queued', 0, 'queued', ?, ?)",
            (job_id, clip["recording_id"], clip_id, timestamp, timestamp),
        )
        connection.execute("UPDATE clips SET status = 'queued' WHERE id = ?", (clip_id,))
    return {"id": job_id, "clip_id": clip_id, "status": "queued", "existing": False}


def create_youtube_upload_job(
    clip_id: str,
    database_path: Path | None = None,
    *,
    scheduled_at: str | None = None,
) -> dict[str, Any]:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        # Serialize duplicate checks across concurrent API calls.
        connection.execute("BEGIN IMMEDIATE")
        clip = connection.execute(
            """
            SELECT clips.recording_id, clips.status, clips.file_path, recordings.authorized
            FROM clips JOIN recordings ON recordings.id = clips.recording_id
            WHERE clips.id = ?
            """,
            (clip_id,),
        ).fetchone()
        if clip is None:
            raise LookupError("Clip candidate not found.")
        if not clip["authorized"]:
            raise PermissionError("The source recording has no authorization confirmation.")
        if clip["status"] != "rendered" or not clip["file_path"] or not Path(clip["file_path"]).is_file():
            raise RuntimeError("Render the clip before uploading it.")
        event = connection.execute(
            "SELECT id, job_id, status, remote_id FROM publish_events WHERE clip_id = ? AND platform = 'youtube' ORDER BY created_at DESC LIMIT 1",
            (clip_id,),
        ).fetchone()
        if event is not None:
            if event["status"] == "failed":
                return {"id": event["job_id"], "event_id": event["id"], "clip_id": clip_id, "status": "failed", "existing": True, "remote_id": event["remote_id"]}
            return {"id": event["job_id"], "event_id": event["id"], "clip_id": clip_id, "status": event["status"], "existing": True, "remote_id": event["remote_id"]}
        job_id = f"job-{uuid.uuid4().hex}"
        event_id = f"publish-{uuid.uuid4().hex}"
        payload = json.dumps({"event_id": event_id, "scheduled_at": scheduled_at})
        connection.execute(
            "INSERT INTO jobs(id, recording_id, clip_id, payload_json, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, ?, ?, 'youtube_upload', 'queued', 0, 'queued', ?, ?)",
            (job_id, clip["recording_id"], clip_id, payload, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO publish_events(id, clip_id, job_id, platform, privacy_status, status, progress, scheduled_at, created_at, updated_at) VALUES (?, ?, ?, 'youtube', 'private', 'queued', 0, ?, ?, ?)",
            (event_id, clip_id, job_id, scheduled_at, timestamp, timestamp),
        )
    return {"id": job_id, "event_id": event_id, "clip_id": clip_id, "status": "queued", "existing": False, "remote_id": None}


def save_clip_subtitles(clip_id: str, subtitles: list[dict[str, Any]], database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        clip = connection.execute(
            "SELECT start_seconds, end_seconds, status FROM clips WHERE id = ?",
            (clip_id,),
        ).fetchone()
        if clip is None:
            return None
        active_render = connection.execute(
            "SELECT 1 FROM jobs WHERE clip_id = ? AND job_type = 'render_clip' AND status IN ('queued', 'running', 'paused') LIMIT 1",
            (clip_id,),
        ).fetchone()
        if clip["status"] in {"queued", "rendering", "paused"} or active_render is not None:
            raise RuntimeError("Captions cannot be changed while this clip is rendering.")
        duration = float(clip["end_seconds"] - clip["start_seconds"])
        normalized = []
        for segment in subtitles:
            start = round(float(segment["start"]), 3)
            end = round(float(segment["end"]), 3)
            text = " ".join(str(segment["text"]).split())
            if start < 0 or end <= start or end > duration + 0.05:
                raise ValueError("Subtitle times must be positive, ordered within the clip, and no later than its end.")
            if not text:
                continue
            normalized.append({"start": start, "end": end, "text": text})
        normalized.sort(key=lambda segment: (segment["start"], segment["end"]))
        for previous, current in zip(normalized, normalized[1:]):
            if current["start"] < previous["end"]:
                raise ValueError("Subtitle segments cannot overlap. Adjust the timing before saving.")
        connection.execute(
            "UPDATE clips SET subtitle_segments_json = ?, status = 'candidate', rendered_at = NULL WHERE id = ?",
            (json.dumps(normalized, ensure_ascii=False), clip_id),
        )
    return get_clip(clip_id, database_path)


def set_clip_render_status(
    clip_id: str,
    status: str,
    *,
    file_path: str | None = None,
    render_metadata: dict[str, Any] | None = None,
    database_path: Path | None = None,
) -> None:
    with database_session(database_path) as connection:
        if status == "rendered":
            connection.execute(
                "UPDATE clips SET status = ?, file_path = ?, render_metadata_json = ?, rendered_at = ? WHERE id = ?",
                (status, file_path, json.dumps(render_metadata or {}), utc_now(), clip_id),
            )
        else:
            connection.execute("UPDATE clips SET status = ?, rendered_at = NULL WHERE id = ?", (status, clip_id))


def _clip_metadata_from_row(row: sqlite3.Row) -> dict[str, Any]:
    metadata = dict(row)
    metadata["hashtags"] = json.loads(metadata.pop("hashtags_json"))
    metadata["tags"] = json.loads(metadata.pop("tags_json"))
    return metadata


def get_clip_metadata(clip_id: str, database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        row = connection.execute(
            "SELECT clip_id, game_name, tone, title, description, hashtags_json, tags_json, provider, model_name, status, generation_note, error_message, updated_at FROM clip_metadata WHERE clip_id = ?",
            (clip_id,),
        ).fetchone()
        if row is not None:
            return _clip_metadata_from_row(row)
        clip = connection.execute("SELECT id FROM clips WHERE id = ?", (clip_id,)).fetchone()
    if clip is None:
        return None
    return {
        "clip_id": clip_id,
        "game_name": "",
        "tone": "hype",
        "title": "",
        "description": "",
        "hashtags": [],
        "tags": [],
        "provider": None,
        "model_name": None,
        "status": "empty",
        "generation_note": None,
        "error_message": None,
        "updated_at": None,
    }


def get_clip_generation_input(clip_id: str, database_path: Path | None = None) -> dict[str, Any] | None:
    with database_session(database_path) as connection:
        row = connection.execute(
            """
            SELECT clips.id, clips.title, clips.score, clips.reason_json, clips.signals_json,
                   clips.subtitle_segments_json, clips.recording_id, recordings.display_name AS recording_name,
                   recordings.authorized
            FROM clips JOIN recordings ON recordings.id = clips.recording_id
            WHERE clips.id = ?
            """,
            (clip_id,),
        ).fetchone()
    if row is None:
        return None
    value = dict(row)
    value["authorized"] = bool(value["authorized"])
    value["reasons"] = json.loads(value.pop("reason_json"))
    value["signals"] = json.loads(value.pop("signals_json"))
    value["subtitles"] = json.loads(value.pop("subtitle_segments_json"))
    return value


def queue_metadata_generation(
    clip_id: str,
    game_name: str,
    tone: str,
    database_path: Path | None = None,
) -> dict[str, Any]:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        clip = connection.execute(
            "SELECT clips.recording_id, recordings.authorized FROM clips JOIN recordings ON recordings.id = clips.recording_id WHERE clips.id = ?",
            (clip_id,),
        ).fetchone()
        if clip is None:
            raise LookupError("Clip candidate not found.")
        if not clip["authorized"]:
            raise PermissionError("The source recording has no authorization confirmation.")
        active = connection.execute(
            "SELECT id, status FROM jobs WHERE clip_id = ? AND job_type = 'generate_metadata' AND status IN ('queued', 'running', 'paused') ORDER BY created_at DESC LIMIT 1",
            (clip_id,),
        ).fetchone()
        if active is not None:
            return {"id": active["id"], "clip_id": clip_id, "status": active["status"], "existing": True}
        payload = json.dumps({"game_name": game_name, "tone": tone}, ensure_ascii=False)
        job_id = f"job-{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO jobs(id, recording_id, clip_id, payload_json, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, ?, ?, 'generate_metadata', 'queued', 0, 'queued', ?, ?)",
            (job_id, clip["recording_id"], clip_id, payload, timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO clip_metadata(clip_id, game_name, tone, title, description, hashtags_json, tags_json, provider, status, generation_note, error_message, updated_at)
            VALUES (?, ?, ?, '', '', '[]', '[]', 'template', 'queued', NULL, NULL, ?)
            ON CONFLICT(clip_id) DO UPDATE SET game_name = excluded.game_name, tone = excluded.tone,
                status = 'queued', generation_note = NULL, error_message = NULL, updated_at = excluded.updated_at
            """,
            (clip_id, game_name, tone, timestamp),
        )
    return {"id": job_id, "clip_id": clip_id, "status": "queued", "existing": False}


def save_clip_metadata(clip_id: str, metadata: dict[str, Any], database_path: Path | None = None) -> dict[str, Any] | None:
    timestamp = utc_now()
    hashtags = json.dumps(metadata["hashtags"], ensure_ascii=False)
    tags = json.dumps(metadata["tags"], ensure_ascii=False)
    with database_session(database_path) as connection:
        clip = connection.execute(
            "SELECT recordings.authorized FROM clips JOIN recordings ON recordings.id = clips.recording_id WHERE clips.id = ?",
            (clip_id,),
        ).fetchone()
        if clip is None:
            return None
        if not clip["authorized"]:
            raise PermissionError("The source recording has no authorization confirmation.")
        active = connection.execute(
            "SELECT 1 FROM jobs WHERE clip_id = ? AND job_type = 'generate_metadata' AND status IN ('queued', 'running', 'paused') LIMIT 1",
            (clip_id,),
        ).fetchone()
        if active is not None:
            raise RuntimeError("Metadata cannot be edited while generation is active.")
        connection.execute(
            """
            INSERT INTO clip_metadata(clip_id, game_name, tone, title, description, hashtags_json, tags_json, provider, model_name, status, generation_note, error_message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', NULL, 'draft', 'Edited locally.', NULL, ?)
            ON CONFLICT(clip_id) DO UPDATE SET game_name = excluded.game_name, tone = excluded.tone,
                title = excluded.title, description = excluded.description, hashtags_json = excluded.hashtags_json,
                tags_json = excluded.tags_json, provider = 'manual', model_name = NULL,
                status = 'draft', generation_note = 'Edited locally.', error_message = NULL,
                updated_at = excluded.updated_at
            """,
            (
                clip_id, metadata["game_name"], metadata["tone"], metadata["title"],
                metadata["description"], hashtags, tags, timestamp,
            ),
        )
    return get_clip_metadata(clip_id, database_path)


def complete_clip_metadata(clip_id: str, metadata: dict[str, Any], database_path: Path | None = None) -> dict[str, Any] | None:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        connection.execute(
            """
            UPDATE clip_metadata SET title = ?, description = ?, hashtags_json = ?, tags_json = ?,
                provider = ?, model_name = ?, status = 'complete', generation_note = ?, error_message = NULL,
                updated_at = ? WHERE clip_id = ?
            """,
            (
                metadata["title"], metadata["description"], json.dumps(metadata["hashtags"], ensure_ascii=False),
                json.dumps(metadata["tags"], ensure_ascii=False), metadata["provider"], metadata["model_name"],
                metadata["generation_note"], timestamp, clip_id,
            ),
        )
    return get_clip_metadata(clip_id, database_path)


def list_youtube_publications(database_path: Path | None = None) -> list[dict[str, Any]]:
    with database_session(database_path) as connection:
        rows = connection.execute(
            """
            SELECT publish_events.id, publish_events.clip_id, publish_events.job_id, publish_events.remote_id,
                   publish_events.privacy_status, publish_events.status, publish_events.progress,
                   publish_events.analytics_json, publish_events.analytics_updated_at,
                   publish_events.error_message, publish_events.scheduled_at,
                   publish_events.created_at, publish_events.updated_at,
                   clips.title AS clip_title, clip_metadata.title AS upload_title
            FROM publish_events
            JOIN clips ON clips.id = publish_events.clip_id
            LEFT JOIN clip_metadata ON clip_metadata.clip_id = clips.id
            WHERE publish_events.platform = 'youtube'
            ORDER BY publish_events.created_at DESC
            """
        ).fetchall()
    results = []
    for row in rows:
        value = dict(row)
        value["analytics"] = json.loads(value.pop("analytics_json"))
        value["video_url"] = f"https://www.youtube.com/watch?v={value['remote_id']}" if value["remote_id"] else None
        results.append(value)
    return results


def set_youtube_publication_status(
    event_id: str,
    status: str,
    *,
    progress: float | None = None,
    error_message: str | None = None,
    database_path: Path | None = None,
) -> None:
    updates: dict[str, Any] = {"status": status, "error_message": error_message, "updated_at": utc_now()}
    if progress is not None:
        updates["progress"] = max(0, min(float(progress), 100))
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with database_session(database_path) as connection:
        connection.execute(f"UPDATE publish_events SET {assignments} WHERE id = ?", (*updates.values(), event_id))


def complete_youtube_publication(event_id: str, video_id: str, database_path: Path | None = None) -> None:
    with database_session(database_path) as connection:
        connection.execute(
            "UPDATE publish_events SET remote_id = ?, status = 'complete', progress = 100, error_message = NULL, updated_at = ? WHERE id = ?",
            (video_id, utc_now(), event_id),
        )


def save_youtube_analytics(metrics_by_video: dict[str, dict[str, int]], database_path: Path | None = None) -> list[dict[str, Any]]:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        rows = connection.execute(
            "SELECT id, remote_id FROM publish_events WHERE platform = 'youtube' AND status = 'complete' AND remote_id IS NOT NULL"
        ).fetchall()
        for row in rows:
            analytics = metrics_by_video.get(row["remote_id"], {"views": 0, "likes": 0, "comments": 0, "shares": 0})
            connection.execute(
                "UPDATE publish_events SET analytics_json = ?, analytics_updated_at = ?, updated_at = ? WHERE id = ?",
                (json.dumps(analytics), timestamp, timestamp, row["id"]),
            )
    return list_youtube_publications(database_path)


def set_clip_metadata_status(
    clip_id: str,
    status: str,
    *,
    error_message: str | None = None,
    database_path: Path | None = None,
) -> None:
    with database_session(database_path) as connection:
        connection.execute(
            "UPDATE clip_metadata SET status = ?, error_message = ?, updated_at = ? WHERE clip_id = ?",
            (status, error_message, utc_now(), clip_id),
        )


def retry_job(job_id: str, max_attempts: int = 3, database_path: Path | None = None) -> dict[str, Any] | None:
    timestamp = utc_now()
    with database_session(database_path) as connection:
        row = connection.execute(
            "SELECT id, recording_id, clip_id, job_type, status, attempt_count FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None or row["status"] != "failed" or row["attempt_count"] >= max_attempts:
            return None
        connection.execute(
            "UPDATE jobs SET status = 'queued', progress = 0, stage = 'queued', error_message = NULL, updated_at = ? WHERE id = ?",
            (timestamp, job_id),
        )
        if row["job_type"] == "render_clip" and row["clip_id"]:
            connection.execute("UPDATE clips SET status = 'queued' WHERE id = ?", (row["clip_id"],))
        elif row["job_type"] == "generate_metadata" and row["clip_id"]:
            connection.execute("UPDATE clip_metadata SET status = 'queued', error_message = NULL, updated_at = ? WHERE clip_id = ?", (timestamp, row["clip_id"]))
        elif row["job_type"] == "youtube_upload" and row["clip_id"]:
            connection.execute("UPDATE publish_events SET status = 'queued', error_message = NULL, updated_at = ? WHERE job_id = ?", (timestamp, row["id"]))
        else:
            connection.execute("UPDATE recordings SET status = 'queued' WHERE id = ?", (row["recording_id"],))
    return get_job(job_id, database_path)

