import logging
import os
import pathlib
import sys
import argparse # Adicione esta importação

if hasattr(sys, '_MEIPASS') and sys._MEIPASS not in sys.path:
    sys.path.insert(0, sys._MEIPASS)

import uvicorn

if __name__ == "__main__":
    # 1. Configura o parser para aceitar o argumento --port
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000, help="Porta para rodar o backend")
    args = parser.parse_args()

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

    from app.main import app as fastapi_app
    
    # 2. Usa a porta recebida via argumento
    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=args.port, # <--- Dinâmico agora!
        log_level="info",
        log_config=None,
    )