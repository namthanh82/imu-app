# ReTrack

ReTrack is an IMU-based rehabilitation tracking desktop app. It records exercise sessions, shows realtime charts and 3D motion, manages patient data, and can optionally use local/AI analysis features.

## Run From Source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The app starts a local Flask/Socket.IO server and opens the UI on the configured port.

## AI Features

AI features are optional. Install them only when needed:

```bash
pip install -r requirements-ai.txt
```

Configure model/vector-store paths in `.env`. Do not commit `.env` to GitHub.

## Build Locally

```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean ReTrack.spec
```

The Windows executable is generated under `dist/`.

## Downloadable Releases

The GitHub Actions workflow in `.github/workflows/release.yml` builds downloadable installers/artifacts on each operating system:

- Windows: `ReTrack-Windows-Setup.exe`
- Linux: `ReTrack-Linux.tar.gz`
- macOS: `ReTrack-macOS.dmg`

To publish a release, push a tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

You can also run the workflow manually from the GitHub Actions tab.

## Packaging Notes

- PyInstaller cannot cross-compile. Windows, Linux, and macOS builds must run on their own OS runners.
- Public release builds use `RETRACK_BUNDLE_ENV=0`, so `.env` secrets are not bundled.
- Linux users may need GTK/WebKit runtime libraries for `pywebview`.
- macOS artifacts are unsigned unless a signing certificate is added later.
