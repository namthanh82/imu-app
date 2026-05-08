# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys

project_dir = Path(SPECPATH)
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

runtime_data_dir = project_dir / ".imu-web-data"
runtime_data_dir.mkdir(parents=True, exist_ok=True)

datas = [
    (str(project_dir / "static"), "static"),
]

templates_dir = project_dir / "templates"
if templates_dir.exists():
    datas.append((str(templates_dir), "templates"))

lower_body = project_dir / "lower_body.glb"
if lower_body.exists():
    datas.append((str(lower_body), "."))

env_file = project_dir / ".env"
if env_file.exists() and os.environ.get("RETRACK_BUNDLE_ENV", "1").lower() not in {"0", "false", "no"}:
    datas.append((str(env_file), "."))

ai_data_dir = project_dir / "imurtrack_ai" / "data"
if ai_data_dir.exists():
    datas.append((str(ai_data_dir), "imurtrack_ai/data"))

a = Analysis(
    ["app.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=["engineio.async_drivers.threading", "webview.platforms.edgechromium"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="IMU_App",
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
