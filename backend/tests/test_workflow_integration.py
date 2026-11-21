from __future__ import annotations

import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from clipforge import database, main, worker


class WorkflowIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="clipforge-workflow-")
        self.root = Path(self.temporary_directory.name)
        self.data_directory = self.root / "data"
        self.output_directory = self.data_directory / "output"
        self.database_path = self.data_directory / "clipforge.db"
        self.data_directory.mkdir(parents=True)

        self.patches = ExitStack()
        self.patches.enter_context(patch.object(database, "DATA_DIR", self.data_directory))
        self.patches.enter_context(patch.object(database, "DATABASE_PATH", self.database_path))
        self.patches.enter_context(patch.object(database, "OUTPUT_DIR", self.output_directory))
        self.patches.enter_context(patch.object(main, "DATA_DIR", self.data_directory))
        self.patches.enter_context(patch.object(main, "OUTPUT_DIR", self.output_directory))
        self.patches.enter_context(patch.object(worker, "OUTPUT_DIR", self.output_directory))

        self.patches.enter_context(patch.object(worker, "probe_video", return_value={
            "container": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration_seconds": 30.0,
            "size_bytes": 18,
            "video": {"codec": "h264", "width": 1280, "height": 720},
            "audio": {"codec": "aac", "sample_rate": "48000", "channels": 2},
        }))
        self.patches.enter_context(patch.object(worker, "transcribe_recording", return_value={
            "transcript": {
                "language": "en",
                "language_probability": 0.99,
                "model": "tiny",
                "device": "cpu",
                "compute_type": "int8",
                "segments": [{"start": 2.0, "end": 4.2, "text": "That was a clutch play!", "confidence": -0.1}],
            },
            "transcript_path": str(self.data_directory / "transcript.json"),
            "subtitle_path": str(self.data_directory / "transcript.srt"),
            "audio_profile": {"mean_rms": 0.15, "peak_rms": 0.8, "active_audio_fraction": 0.9, "energy_buckets": [0.1, 0.8]},
            "energy_by_second": [0.1, 0.8, 0.8, 0.1],
            "scene_cuts": [3.0],
        }))
        self.patches.enter_context(patch.object(worker, "generate_highlights", return_value=[{
            "title": "That clutch play",
            "start_seconds": 1.0,
            "end_seconds": 11.0,
            "score": 82.0,
            "reasons": ["Excitement cues in transcript"],
            "signals": {"audio_energy": 0.8, "speech_density": 0.4, "excitement_cues": 1, "scene_changes": 1},
        }]))

        def render_clip(*, destination: Path, **_kwargs: object) -> dict[str, object]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"synthetic rendered mp4")
            return {
                "file_path": str(destination),
                "subtitle_path": str(destination.with_suffix(".srt")),
                "duration_seconds": 10.0,
                "width": 1080,
                "height": 1920,
                "codec": "h264",
            }

        self.patches.enter_context(patch.object(worker, "render_vertical_clip", side_effect=render_clip))
        self.patches.enter_context(patch.object(worker, "generate_clip_metadata", return_value={
            "title": "Clutch play",
            "description": "A clutch gameplay moment.",
            "hashtags": ["#gaming", "#shorts"],
            "tags": ["gameplay", "clutch"],
            "provider": "template",
            "model_name": None,
            "generation_note": "Synthetic integration draft.",
        }))
        self.patches.enter_context(patch.object(worker, "upload_private_video", return_value={"video_id": "integration-video"}))
        self.patches.enter_context(patch.object(main.youtube_oauth, "access_token", return_value="synthetic-token"))
        self.patches.enter_context(patch.object(main, "channel_analytics", return_value={
            "integration-video": {"views": 12, "likes": 3, "comments": 1, "shares": 2},
        }))
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.patches.close()
        self.temporary_directory.cleanup()

    def wait_for_job(self, job_id: str) -> dict[str, object]:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            response = self.client.get("/api/jobs")
            self.assertEqual(response.status_code, 200, response.text)
            job = next((item for item in response.json() if item["id"] == job_id), None)
            if job is not None and job["status"] == "complete":
                return job
            if job is not None and job["status"] == "failed":
                self.fail(f"Job {job_id} failed: {job['error_message']}")
            time.sleep(0.05)
        self.fail(f"Job {job_id} did not complete before timeout.")

    def test_clip_flows_from_import_through_private_upload_and_analytics(self) -> None:
        source_path = self.root / "game-session.mp4"
        original_bytes = b"synthetic source video bytes"
        source_path.write_bytes(original_bytes)

        imported = self.client.post("/api/recordings", json={"path": str(source_path), "authorized": True})
        self.assertEqual(imported.status_code, 202, imported.text)
        recording_id = imported.json()["recording_id"]
        self.wait_for_job(imported.json()["job_id"])

        analysis = self.client.post(f"/api/recordings/{recording_id}/analyze")
        self.assertEqual(analysis.status_code, 202, analysis.text)
        self.wait_for_job(analysis.json()["id"])
        results = self.client.get(f"/api/recordings/{recording_id}/analysis")
        self.assertEqual(results.status_code, 200, results.text)
        self.assertEqual(results.json()["transcript"]["segments"][0]["text"], "That was a clutch play!")
        clip_id = results.json()["candidates"][0]["id"]

        rendered = self.client.post(f"/api/clips/{clip_id}/render")
        self.assertEqual(rendered.status_code, 202, rendered.text)
        self.wait_for_job(rendered.json()["id"])
        preview = self.client.get(f"/api/clips/{clip_id}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.content, b"synthetic rendered mp4")

        metadata = self.client.post(
            f"/api/clips/{clip_id}/metadata/generate",
            json={"game_name": "Valorant", "tone": "hype"},
        )
        self.assertEqual(metadata.status_code, 202, metadata.text)
        self.wait_for_job(metadata.json()["id"])
        self.assertEqual(self.client.get(f"/api/clips/{clip_id}/metadata").json()["title"], "Clutch play")

        upload = self.client.post(f"/api/clips/{clip_id}/youtube-upload")
        self.assertEqual(upload.status_code, 202, upload.text)
        self.wait_for_job(upload.json()["id"])
        publication = self.client.get("/api/youtube/publications").json()[0]
        self.assertEqual(publication["privacy_status"], "private")
        self.assertEqual(publication["remote_id"], "integration-video")

        refreshed = self.client.post("/api/youtube/analytics/refresh")
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertEqual(refreshed.json()["publications"][0]["analytics"]["views"], 12)
        self.assertEqual(source_path.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
