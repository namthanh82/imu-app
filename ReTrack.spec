# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os
import sys


sys.setrecursionlimit(sys.getrecursionlimit() * 5)


project_dir = Path(SPECPATH)

platform_hiddenimports = ["webview"]
if sys.platform.startswith("win"):
    platform_hiddenimports.extend([
        "clr_loader",
        "pythonnet",
        "webview.platforms.edgechromium",
    ])
elif sys.platform == "darwin":
    platform_hiddenimports.append("webview.platforms.cocoa")
else:
    platform_hiddenimports.append("webview.platforms.gtk")

datas = [
    (str(project_dir / "templates"), "templates"),
    (str(project_dir / "static"), "static"),
    (str(project_dir / "imurtrack_ai" / "data"), "imurtrack_ai/data"),
]

env_file = project_dir / ".env"
if env_file.exists() and os.environ.get("RETRACK_BUNDLE_ENV", "1") not in {"0", "false", "False"}:
    datas.append((str(env_file), "."))


a = Analysis(
    ["app.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "backports.tarfile",
        "engineio.async_drivers.threading",
        "serial.tools.list_ports",
        "tkinter",
        "tkinter.filedialog",
    ] + platform_hiddenimports,
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
