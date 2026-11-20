from __future__ import annotations

import tempfile
import sqlite3
import unittest
from pathlib import Path

from clipforge.database import (
    DEFAULT_SETTINGS,
    create_analysis_job,
    create_render_job,
    create_recording,
    get_clip_render_input,
    database_session,
    get_recording_analysis,
    initialize_database,
    read_overview,
    read_settings,
    retry_job,
    save_analysis_result,
    save_clip_subtitles,
    set_clip_render_status,
    write_settings,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "clipforge.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_initialization_is_idempotent_and_keeps_defaults(self) -> None:
        initialize_database(self.database_path)
        settings = read_settings(self.database_path)

        self.assertEqual(settings, DEFAULT_SETTINGS)
        self.assertEqual(read_overview(self.database_path)["recordings_total"], 0)

    def test_phase_three_database_is_migrated_without_losing_rows(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.db"
        with sqlite3.connect(legacy_path) as connection:
            connection.executescript(
                """
                CREATE TABLE recordings (
                    id TEXT PRIMARY KEY, file_path TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
                    duration_seconds REAL, status TEXT NOT NULL DEFAULT 'imported',
                    authorized INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
                CREATE TABLE jobs (
                    id TEXT PRIMARY KEY, recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
                    job_type TEXT NOT NULL, status TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'queued', error_message TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE clips (
                    id TEXT PRIMARY KEY, recording_id TEXT REFERENCES recordings(id) ON DELETE SET NULL,
                    file_path TEXT, title TEXT, score REAL, status TEXT NOT NULL DEFAULT 'candidate', created_at TEXT NOT NULL
                );
                INSERT INTO recordings VALUES ('legacy-recording', 'C:/clips/legacy.mp4', 'legacy.mp4', 10, 'analyzed', 1, '2026-11-20');
                INSERT INTO jobs VALUES ('legacy-job', 'legacy-recording', 'analyze_recording', 'complete', 100, 'complete', NULL, 1, '2026-11-20', '2026-11-20');
                INSERT INTO clips VALUES ('legacy-clip', 'legacy-recording', NULL, 'Legacy moment', 75, 'candidate', '2026-11-20');
                """
            )
        connection.close()

        initialize_database(legacy_path)

        with database_session(legacy_path) as connection:
            job_columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)")}
            clip_columns = {row["name"] for row in connection.execute("PRAGMA table_info(clips)")}
            self.assertEqual(connection.execute("SELECT display_name FROM recordings WHERE id = 'legacy-recording'").fetchone()[0], "legacy.mp4")
            self.assertEqual(connection.execute("SELECT title FROM clips WHERE id = 'legacy-clip'").fetchone()[0], "Legacy moment")
        self.assertIn("clip_id", job_columns)
        self.assertIn("subtitle_segments_json", clip_columns)
        self.assertIn("render_metadata_json", clip_columns)

    def test_settings_are_persisted(self) -> None:
        settings = write_settings(
            {"automation_mode": "manual", "emergency_stop": True},
            self.database_path,
        )

        self.assertEqual(settings["automation_mode"], "manual")
        self.assertTrue(settings["emergency_stop"])
        self.assertEqual(settings["max_concurrent_jobs"], 1)

    def test_analysis_results_and_candidates_are_persisted(self) -> None:
        create_recording("recording-analysis", "C:/clips/session.mp4", "session.mp4", True, self.database_path)
        with database_session(self.database_path) as connection:
            connection.execute("UPDATE recordings SET status = 'ready', duration_seconds = 18 WHERE id = 'recording-analysis'")

        job = create_analysis_job("recording-analysis", self.database_path)
        self.assertFalse(job["existing"])
        active_job = create_analysis_job("recording-analysis", self.database_path)
        self.assertTrue(active_job["existing"])
        self.assertEqual(active_job["id"], job["id"])

        result = {
            "transcript": {
                "language": "en",
                "language_probability": 0.98,
                "model": "tiny",
                "device": "cpu",
                "compute_type": "int8",
                "segments": [{"start": 1.2, "end": 2.8, "text": "No way!", "confidence": -0.2}],
            },
            "transcript_path": "C:/data/output/recording-analysis/transcript.json",
            "subtitle_path": "C:/data/output/recording-analysis/transcript.srt",
            "audio_profile": {"mean_rms": 0.12, "peak_rms": 0.91, "active_audio_fraction": 0.9, "energy_buckets": [0.1, 0.9]},
            "scene_cuts": [2.0],
        }
        candidates = [{
            "title": "No way",
            "start_seconds": 0.0,
            "end_seconds": 18.0,
            "score": 81.5,
            "reasons": ["Excitement cues in transcript"],
            "signals": {"audio_energy": 0.8, "speech_density": 0.3, "excitement_cues": 1, "scene_changes": 1},
        }]
        save_analysis_result("recording-analysis", result, candidates, self.database_path)
        saved = get_recording_analysis("recording-analysis", self.database_path)

        self.assertEqual(saved["transcript"]["segments"][0]["text"], "No way!")
        self.assertEqual(saved["analysis"]["candidate_count"], 1)
        self.assertEqual(saved["candidates"][0]["score"], 81.5)
        self.assertEqual(saved["candidates"][0]["reasons"], candidates[0]["reasons"])
        self.assertEqual(saved["candidates"][0]["subtitles"], [{"start": 1.2, "end": 2.8, "text": "No way!"}])

        with database_session(self.database_path) as connection:
            connection.execute("UPDATE jobs SET status = 'complete' WHERE recording_id = 'recording-analysis'")
        clip_id = saved["candidates"][0]["id"]
        render_job = create_render_job(clip_id, self.database_path)
        self.assertFalse(render_job["existing"])
        self.assertEqual(create_render_job(clip_id, self.database_path)["id"], render_job["id"])
        render_input = get_clip_render_input(clip_id, self.database_path)
        self.assertTrue(render_input["authorized"])
        self.assertEqual(render_input["subtitles"][0]["text"], "No way!")

        with self.assertRaises(RuntimeError):
            save_clip_subtitles(clip_id, [{"start": 1.0, "end": 2.4, "text": "Unsaved while queued"}], self.database_path)
        with database_session(self.database_path) as connection:
            connection.execute("UPDATE jobs SET status = 'complete' WHERE clip_id = ?", (clip_id,))
        set_clip_render_status(clip_id, "candidate", database_path=self.database_path)
        edited = save_clip_subtitles(
            clip_id,
            [{"start": 1.0, "end": 2.4, "text": "No way, clutch!"}],
            self.database_path,
        )
        self.assertEqual(edited["status"], "candidate")
        self.assertEqual(edited["subtitles"][0]["text"], "No way, clutch!")
        with self.assertRaises(ValueError):
            save_clip_subtitles(clip_id, [{"start": 0, "end": 19, "text": "Out of range"}], self.database_path)
        with database_session(self.database_path) as connection:
            connection.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (render_job["id"],))
        set_clip_render_status(clip_id, "failed", database_path=self.database_path)
        retried = retry_job(render_job["id"], database_path=self.database_path)
        self.assertEqual(retried["status"], "queued")
        self.assertEqual(get_clip_render_input(clip_id, self.database_path)["status"], "queued")

    def test_overview_is_derived_from_database_rows(self) -> None:
        with database_session(self.database_path) as connection:
            connection.execute(
                "INSERT INTO recordings(id, file_path, display_name, status, authorized, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("recording-1", "C:/clips/session.mp4", "session.mp4", "ready", 1, "2026-11-20T00:00:00+00:00"),
            )
            connection.execute(
                "INSERT INTO jobs(id, recording_id, job_type, status, progress, stage, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("job-1", "recording-1", "ingest", "running", 25, "probing", "2026-11-20T00:00:00+00:00", "2026-11-20T00:01:00+00:00"),
            )
            connection.execute(
                "INSERT INTO clips(id, recording_id, title, score, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("clip-1", "recording-1", "Test clip", 0.8, "candidate", "2026-11-20T00:01:00+00:00"),
            )
            connection.execute(
                "INSERT INTO approvals(id, clip_id, status, created_at) VALUES (?, ?, ?, ?)",
                ("approval-1", "clip-1", "pending", "2026-11-20T00:01:00+00:00"),
            )

        overview = read_overview(self.database_path)

        self.assertEqual(overview["recordings_total"], 1)
        self.assertEqual(overview["recordings_ready"], 1)
        self.assertEqual(overview["clips_total"], 1)
        self.assertEqual(overview["jobs_active"], 1)
        self.assertEqual(overview["approvals_pending"], 1)
        self.assertEqual(overview["recent_jobs"][0]["recording_name"], "session.mp4")


if __name__ == "__main__":
    unittest.main()

