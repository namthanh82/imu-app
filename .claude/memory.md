# Memory

- **Current Project Goal:** Convert ReTrack from a browser-first Flask system into a Windows desktop application that can be packaged as a `.exe`.
- **Preferred Runtime:** The app must open as a native desktop window, not remain a normal browser tab.
- **Allowed Transition Strategy:** Existing Flask routes/templates may be reused temporarily only when wrapped inside a desktop app shell during migration.
- **Long-Term Direction:** Prefer moving away from browser-tab usage while preserving IMU, EMG, patient, record, and AI analysis features.
- **Hardware Integration:** Read IMU and EMG data via serial port.
- **Control Flow Goal:** `Serial` -> `Python Backend` -> `Desktop App UI`.
- Do not store secrets here. Use `.env` file instead.

## Change Notes Template
When code changes, add a short note to `change-log.md` in this format:

- **Date/Context:**
- **File(s):**
- **What changed:**
- **Why it changed:**
- **Follow-up:**
