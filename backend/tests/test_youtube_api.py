from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from clipforge import youtube_api


class _Auth:
    def __init__(self, session: str | None = None) -> None:
        self.session = session
        self.cleared = False

    def access_token(self) -> str:
        return "test-token"

    def upload_session(self, _event_id: str) -> str | None:
        return self.session

    def set_upload_session(self, _event_id: str, session_uri: str | None) -> None:
        self.session = session_uri
        self.cleared = session_uri is None


class YouTubeAPITests(unittest.TestCase):
    def test_upload_fields_add_hashtags_and_limit_tags(self) -> None:
        title, description, tags = youtube_api.upload_fields({
            "upload_title": "A  clutch round  ",
            "upload_description": "One final round.",
            "hashtags": ["#Valorant", "#Gaming", "#valorant"],
            "tags": [f"tag-{index}" for index in range(40)],
        })
        self.assertEqual(title, "A clutch round")
        self.assertTrue(description.endswith("#Valorant #Gaming"))
        self.assertIn("Valorant", tags)
        self.assertLessEqual(sum(len(tag) for tag in tags) + len(tags), 500)

    def test_resumable_upload_sets_private_and_returns_video_link(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        video = Path(temporary.name) / "clip.mp4"
        video.write_bytes(b"small video")
        auth = _Auth()
        requests = []

        def send(request: object, **_kwargs: object):
            requests.append(request)
            if request.get_method() == "POST":
                return 200, {"Location": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test"}, b""
            return 201, {}, b'{"id":"video-123"}'

        progress = []
        with patch.object(youtube_api, "_send", side_effect=send):
            result = youtube_api.upload_private_video(
                event_id="event-1", file_path=video, title="Title", description="Description", tags=["gaming"],
                progress=lambda value, stage: progress.append((value, stage)), check_cancel=lambda: None, auth=auth,
            )
        self.assertEqual(result["video_id"], "video-123")
        self.assertEqual(result["url"], "https://www.youtube.com/watch?v=video-123")
        request_body = json.loads(requests[0].data)
        self.assertEqual(request_body["status"]["privacyStatus"], "private")
        self.assertEqual(request_body["snippet"]["title"], "Title")
        self.assertEqual(requests[1].get_header("Content-range"), f"bytes 0-{video.stat().st_size - 1}/{video.stat().st_size}")
        self.assertTrue(auth.cleared)
        self.assertEqual(progress[-1], (100, "complete"))

    def test_resume_uses_server_range_after_interruption(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        video = Path(temporary.name) / "clip.mp4"
        video.write_bytes(b"abcdef")
        session = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=existing"
        auth = _Auth(session)
        requests = []

        def send(request: object, **_kwargs: object):
            requests.append(request)
            if len(requests) == 1:
                return 308, {"Range": "bytes=0-2"}, b""
            return 201, {}, b'{"id":"resumed-video"}'

        with patch.object(youtube_api, "_send", side_effect=send):
            result = youtube_api.upload_private_video(
                event_id="event-2", file_path=video, title="Resume", description="", tags=[],
                progress=lambda *_args: None, check_cancel=lambda: None, auth=auth,
            )
        self.assertEqual(requests[0].get_header("Content-range"), f"bytes */{video.stat().st_size}")
        self.assertEqual(requests[1].get_header("Content-range"), f"bytes 3-5/{video.stat().st_size}")
        self.assertEqual(result["video_id"], "resumed-video")

    def test_analytics_parses_per_video_rows(self) -> None:
        response = {
            "columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "likes"}, {"name": "comments"}, {"name": "shares"}],
            "rows": [["video-a", 42, 7, 2, 1]],
        }
        with patch.object(youtube_api, "_api_json", return_value=response) as request:
            result = youtube_api.channel_analytics(["video-a"], today=date(2026, 11, 20), auth=_Auth())
        self.assertEqual(result["video-a"], {"views": 42, "likes": 7, "comments": 2, "shares": 1})
        self.assertEqual(request.call_args.kwargs["query"]["startDate"], "2026-10-23")
        self.assertEqual(request.call_args.kwargs["query"]["endDate"], "2026-11-19")


if __name__ == "__main__":
    unittest.main()
