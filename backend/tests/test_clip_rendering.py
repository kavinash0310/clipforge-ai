from __future__ import annotations

import unittest

from clipforge.clip_rendering import subtitle_files


class ClipRenderingTests(unittest.TestCase):
    def test_clip_subtitles_have_relative_srt_and_safe_ass_text(self) -> None:
        srt, ass = subtitle_files([
            {"start": 0.25, "end": 1.75, "text": "  Let's {go}!  "},
            {"start": 2.0, "end": 2.8, "text": "Clutch play."},
        ])

        self.assertIn("00:00:00,250 --> 00:00:01,750", srt)
        self.assertIn("Let's {go}!", srt)
        self.assertIn("Dialogue: 0,0:00:00.25,0:00:01.75,Default", ass)
        self.assertIn(r"Let's \{go\}!", ass)
        self.assertIn("PlayResX: 1080", ass)
        self.assertIn("PlayResY: 1920", ass)

    def test_blank_subtitle_lines_are_omitted(self) -> None:
        srt, ass = subtitle_files([{"start": 0, "end": 1, "text": "  "}])

        self.assertEqual(srt, "")
        self.assertNotIn("Dialogue:", ass)


if __name__ == "__main__":
    unittest.main()
