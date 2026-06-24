# backend/app/core/paths.py
from __future__ import annotations

import os
import pathlib

DATA_DIR: pathlib.Path = pathlib.Path(
    os.environ.get(
        "JH_DATA_DIR",
        pathlib.Path.home() / ".local" / "share" / "job-hunter",
    )
)
DATA_DIR.mkdir(parents=True, exist_ok=True)
