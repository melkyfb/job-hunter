# backend/run.py — PyInstaller entry point
import logging
import os
import pathlib
import sys

# PyInstaller extracts datas to sys._MEIPASS; add it so `import app` resolves.
# (sys._MEIPASS is already sys.path[0] in frozen mode, but be explicit.)
if hasattr(sys, '_MEIPASS') and sys._MEIPASS not in sys.path:
    sys.path.insert(0, sys._MEIPASS)

import uvicorn

if __name__ == "__main__":
    data_dir = pathlib.Path(
        os.environ.get("JH_DATA_DIR", pathlib.Path.home() / ".local" / "share" / "job-hunter")
    )
    data_dir.mkdir(parents=True, exist_ok=True)

    log_file = data_dir / "backend.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Import directly — uvicorn's string-based importer bypasses
    # PyInstaller's frozen importer, causing ModuleNotFoundError.
    from app.main import app as fastapi_app  # noqa: PLC0415
    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        log_config=None,
    )
