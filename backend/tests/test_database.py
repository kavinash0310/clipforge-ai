from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clipforge.database import (
    DEFAULT_SETTINGS,
    database_session,
    initialize_database,
    read_overview,
    read_settings,
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

