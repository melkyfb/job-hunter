# backend/backend.spec
# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None
# SPECPATH is the directory containing the .spec file (set by PyInstaller)
HERE = Path(SPECPATH).resolve()  # noqa: F821

a = Analysis(
    ['run.py'],
    pathex=[str(HERE)],
    binaries=[],
    datas=[
        (str(HERE / 'app'), 'app'),
    ],
    hiddenimports=[
        # app.* included via datas — sys._MEIPASS on sys.path at runtime handles import
        # pandas + numpy (used by jobspy)
        'pandas', 'pandas._libs.tslibs.base', 'pandas._libs.tslibs.np_datetime',
        'numpy', 'numpy.core', 'numpy.core._multiarray_umath',
        # uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # FastAPI / pydantic
        'fastapi',
        'pydantic',
        'pydantic_settings',
        # Schedulers
        'apscheduler',
        'apscheduler.schedulers',
        'apscheduler.schedulers.background',
        'apscheduler.executors',
        'apscheduler.executors.pool',
        'apscheduler.jobstores',
        'apscheduler.jobstores.memory',
        'apscheduler.triggers',
        'apscheduler.triggers.interval',
        # PDF / document parsing
        'pdfplumber',
        'pdfminer',
        'pdfminer.high_level',
        'reportlab',
        'reportlab.platypus',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'docx',
        # HTML parsing
        'bs4',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        # HTTP
        'httpx',
        'httpcore',
        # Multipart
        'multipart',
        'python_multipart',
        # jobspy
        'jobspy',
    ],
    excludes=[
        'pytest',
        'tests',
        'tkinter',
        '_tkinter',
        'torch',
        'transformers',
        'scipy',
        'sklearn',
        'matplotlib',
        'tensorboard',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='job-hunter-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # True so uvicorn logs appear during dev; set False for production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
