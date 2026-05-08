#  ReTrack — IMU-Based Rehabilitation Tracking System

**ReTrack** is a smart wearable device system that monitors and evaluates patient rehabilitation progress. It uses motion sensors (IMU) and physiological sensors (EMG) to record data during exercise sessions, helping doctors and rehabilitation specialists objectively assess patient improvement.

> Developed by **BIOTRACKERS** team — Hanoi University of Science and Technology (HUST)

---

##  Project Context & Memory

This project uses the `.claude/` directory as its central "brain" for AI agents and developers. For detailed project context, debugging rules, and workflow, please refer to the markdown files in that folder:

- `.claude/memory.md` — Core architectural rules and goals
- `.claude/design.md` — Design principles and separation of concerns
- `.claude/workflow.md` — Standard workflow for running and testing
- `.claude/skills.md` — Reusable procedures and setup checks
- `.claude/debugging.md` — Debugging guidelines
- `.claude/change-log.md` — Project history and major updates

---

##  Features

| Feature | Description |
|---|---|
| **Real-time IMU tracking** | 3D joint angle measurement (hip, knee, ankle, shoulder, elbow, hand, trunk) using quaternion math |
| **3D body visualization** | Live 3D model animation driven by IMU sensor data |
| **EMG monitoring** | Real-time muscle activity recording and display |
| **Patient management** | Add, edit, delete patient profiles with medical codes |
| **Session recording** | Start/stop measurement sessions with CSV export |
| **Clinical charts** | ROM (Range of Motion) analysis with min/max/range per joint |
| **AI analysis** | GPT-powered clinical report generation from measurement data |
| **AI chatbot** | RAG-based chatbot with project knowledge (powered by LangChain + OpenAI) |
| **VAS & FMA scoring** | Pain scale recording and Fugl-Meyer Assessment per exercise |

---

##  Architecture

```
ReTrack/
├── app.py              # Flask server + routes + SocketIO
├── serial_handler.py   # IMU serial comm, quaternion math, angle computation
├── database.py         # Patient/record/VAS data persistence (JSON-based)
├── imurtrack_ai/       # AI chatbot module (LangChain + FAISS + OpenAI)
│   ├── chatbot.py
│   └── data/           # PDF knowledge base for RAG
├── templates/          # Jinja2 HTML pages
├── static/             # Images, 3D models, videos
└── .env                # Secrets (not committed — see .env.example)
```

---

##  Getting Started

### Prerequisites
- **Python 3.10+**
- **IMU hardware** connected via USB serial

### Installation

```bash
git clone https://github.com/namthanh82/imu-web-min.git
cd imu-web-min
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Configuration
```bash
cp .env.example .env
# Edit .env with your specific settings (OPENAI_API_KEY, SERIAL_PORT)
```

### Run as a desktop app
```bash
python app.py
```
The app starts as a desktop window using `pywebview`/Windows WebView2 instead of opening a normal browser tab.
The desktop runtime serves Flask + Socket.IO on `127.0.0.1:5000` and points the WebView window to `http://127.0.0.1:5000`.

### Build a Windows `.exe`
```bash
pip install -r requirements.txt
pyinstaller --noconfirm --clean ReTrack.spec
```
The generated executable will be placed in the `dist/` folder.

### Build release installers
Release installers are built by GitHub Actions on each target operating system:

- Windows: `ReTrack-Windows-Setup.exe`
- Linux: `ReTrack-Linux.deb`
- macOS: `ReTrack-macOS.dmg`

To create a release, push a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

You can also run the workflow manually from GitHub Actions using **Build desktop releases**. The workflow is defined in `.github/workflows/release.yml`.

### Notes for packaging
- `pywebview` wraps the local Flask server into a desktop-style Windows WebView2 window.
- Static frontend libraries are bundled under `static/vendor/`; templates do not load CDN assets at runtime.
- Local builds can bundle `.env` when that file exists. Public CI release builds set `RETRACK_BUNDLE_ENV=0`, so secrets such as `OPENAI_API_KEY` are not included in downloadable artifacts.
- AI features require the user to configure `OPENAI_API_KEY`. Non-AI features and bundled static frontend assets work offline after installation.
- The app uses `resource_path()` so bundled assets can be resolved correctly when packaged with PyInstaller.
- Linux users may need GTK/WebKit runtime packages installed by the package manager, such as `libgtk-3-0` and `libwebkit2gtk-4.1-0`.
- macOS downloads are unsigned by default unless a signing certificate is added to the release workflow. Users may need to allow the app from macOS Privacy & Security settings.
- If you need a console window for debugging, set `console=True` in `ReTrack.spec`.

---

##  Team

**BIOTRACKERS** — Hanoi University of Science and Technology (Đại học Bách Khoa Hà Nội)
- Phan Quốc Chiến, Nguyễn Nam Thành, Chu Đắc Vinh Quang, Đặng Quỳnh Dương, Bùi Thị Khánh Linh

## License
See [LICENSE](./LICENSE) for details.
