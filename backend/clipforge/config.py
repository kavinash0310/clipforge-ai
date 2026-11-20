from __future__ import annotations

import os
from pathlib import Path


def get_data_dir() -> Path:
    configured = os.environ.get("CLIPFORGE_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ClipForgeAI"

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "clipforge-ai"

    return Path.home() / ".local" / "share" / "clipforge-ai"


DATA_DIR = get_data_dir()
DATABASE_PATH = DATA_DIR / "clipforge.db"
OUTPUT_DIR = DATA_DIR / "output"

