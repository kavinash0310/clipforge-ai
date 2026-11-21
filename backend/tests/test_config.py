from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clipforge.config import get_output_dir


class OutputDirectoryTests(unittest.TestCase):
    def test_configured_output_directory_supports_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_directory = Path(directory) / "Clip Forge"
            with patch.dict(os.environ, {"CLIPFORGE_OUTPUT_DIR": str(output_directory)}):
                self.assertEqual(get_output_dir(Path(directory)), output_directory.resolve())

    def test_default_output_directory_is_inside_data_directory(self) -> None:
        data_directory = Path("C:/ClipForge/data")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CLIPFORGE_OUTPUT_DIR", None)
            self.assertEqual(get_output_dir(data_directory), data_directory / "output")


if __name__ == "__main__":
    unittest.main()
