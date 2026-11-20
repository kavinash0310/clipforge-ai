from __future__ import annotations

import unittest

from clipforge.highlights import generate_highlights
from clipforge.transcription import write_srt


class HighlightTests(unittest.TestCase):
    def test_ranks_audio_and_excitement_with_context_window(self) -> None:
        energy = [0.1] * 120
        energy[52:59] = [0.8, 0.9, 0.95, 1.0, 0.9, 0.85, 0.8]
        segments = [
            {"start": 51.5, "end": 53.0, "text": "Wait!", "confidence": -0.1},
            {"start": 53.1, "end": 55.0, "text": "No way, that clutch was insane!", "confidence": -0.1},
        ]
        candidates = generate_highlights(
            duration_seconds=120,
            energy_by_second=energy,
            scene_cuts=[52.2, 53.7, 57.0],
            transcript_segments=segments,
            window_seconds=30,
        )

        self.assertTrue(candidates)
        candidate = max(candidates, key=lambda item: item["score"])
        self.assertLessEqual(candidate["start_seconds"], 51.5)
        self.assertGreaterEqual(candidate["end_seconds"], 55.0)
        self.assertIn("Excitement cues in transcript", candidate["reasons"])
        self.assertLessEqual(len(candidates), 5)

    def test_flat_silent_video_has_no_false_highlights(self) -> None:
        candidates = generate_highlights(
            duration_seconds=90,
            energy_by_second=[0.0] * 90,
            scene_cuts=[],
            transcript_segments=[],
        )
        self.assertEqual(candidates, [])

    def test_srt_has_ordered_millisecond_timecodes(self) -> None:
        result = write_srt([
            {"start": 1.25, "end": 2.75, "text": "  Let's go!  "},
            {"start": 61.0, "end": 62.125, "text": "Clean play."},
        ])
        self.assertIn("00:00:01,250 --> 00:00:02,750", result)
        self.assertIn("00:01:01,000 --> 00:01:02,125", result)
        self.assertTrue(result.endswith("\n"))


if __name__ == "__main__":
    unittest.main()

