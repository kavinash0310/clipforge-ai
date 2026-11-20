from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clipforge.database import (
    DEFAULT_SETTINGS,
    create_analysis_job,
    create_recording,
    database_session,
    get_recording_analysis,
    initialize_database,
    read_overview,
    read_settings,
    save_analysis_result,
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

