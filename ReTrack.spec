# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys


project_dir = Path(SPECPATH)
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

datas = [
    (str(project_dir / "static"), "static"),
]

templates_dir = project_dir / "templates"
if templates_dir.exists():
    datas.append((str(templates_dir), "templates"))

ai_data_dir = project_dir / "imurtrack_ai" / "data"
if ai_data_dir.exists():
    datas.append((str(ai_data_dir), "imurtrack_ai/data"))

env_file = project_dir / ".env"
if env_file.exists() and os.environ.get("RETRACK_BUNDLE_ENV", "1").lower() not in {"0", "false", "no"}:
    datas.append((str(env_file), "."))

a = Analysis(
    ["app.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "engineio.async_drivers.threading",
        "serial.tools.list_ports",
        "webgiaodien",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "pandas",
        "pytest",
        "scipy",
        "sklearn",
        "tensorflow",
        "torch",
        "torchaudio",
        "torchvision",
        "transformers",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ReTrack",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="ReTrack.app",
        icon=None,
        bundle_identifier="vn.biotrackers.retrack",
    )
