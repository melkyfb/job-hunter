# backend/run.py — PyInstaller entry point
import logging
import os
import pathlib

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

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        log_config=None,  # use our basicConfig above
    )
