from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from clipforge.clip_rendering import render_vertical_clip
from clipforge.media import probe_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires FFmpeg and ffprobe")
class FFmpegIntegrationTests(unittest.TestCase):
    def test_synthetic_video_renders_to_valid_vertical_mp4(self) -> None:
        ffmpeg = shutil.which("ffmpeg")
        self.assertIsNotNone(ffmpeg)
        with tempfile.TemporaryDirectory(prefix="clipforge-ffmpeg-") as directory:
            root = Path(directory)
            source = root / "source.mp4"
            destination = root / "rendered.mp4"
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                    "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(source),
                ],
                check=True,
                timeout=30,
            )

            result = render_vertical_clip(
                source=source,
                destination=destination,
                start_seconds=0,
                end_seconds=3,
                subtitles=[{"start": 0.5, "end": 2, "text": "ClipForge integration render"}],
                check_cancel=lambda: None,
                progress=lambda *_: None,
                cpu_threads=1,
            )

            metadata = probe_video(destination)
            self.assertEqual(metadata["video"]["width"], 1080)
            self.assertEqual(metadata["video"]["height"], 1920)
            self.assertAlmostEqual(result["duration_seconds"], 3.0, delta=0.15)
            self.assertTrue(destination.with_suffix(".srt").is_file())


if __name__ == "__main__":
    unittest.main()
