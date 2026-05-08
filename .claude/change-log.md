# Change Log

This file records important project changes over time.

## Entries

### 2026-05-07 — Desktop Executable Workflow
- **Files:** `app.py`, `requirements.txt`, `README.md`, `templates/dashboard.html`, `templates/login.html`, `templates/calibration.html`, `templates/desktop_keepalive.html`, `.claude/current-task.md`, `.claude/memory.md`
- **Change:** Added a FlaskUI desktop launcher, PyInstaller build instructions, packaging dependencies, and a shared desktop keep-alive include for key templates.
- **Reason:** To move ReTrack away from normal browser-tab runtime and toward a Windows `.exe` workflow while preserving existing IMU, database, AI, and template features.
- **Result / Follow-up:** The project can launch as a desktop-style window and has a repeatable `.exe` build command. Long-term follow-up is a deeper native UI rewrite if Flask/templates must be removed completely.

### 2026-05-03 — Repository Cleanup & Restructuring
- **Files:** `old_backup/`, `.gitignore`, `README.md`, `app.py`, `.claude/*`
- **Change:** Cleaned up 81+ throwaway scripts, hardened security by moving secrets to `.env`, added `.gitignore`, structured the project into a clean Git repo, and rewrote `.claude` docs for ReTrack context.
- **Reason:** To organize the codebase into a maintainable state, prepare it for version control, and provide clear AI memory.
- **Result / Follow-up:** Repository is clean and modular. Next step is normal feature development.
