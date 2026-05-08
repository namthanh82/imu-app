# Design Rules

- Keep the control architecture simple and explicit.
- Clear separation of roles: 
  - **UI** (`templates/`, `static/`) 
  - **Data Processing & Hardware** (`serial_handler.py`) 
  - **Data Persistence** (`database.py`)
  - **AI Features** (`imurtrack_ai/`)
- Prefer Python for quaternion-to-Euler math and data filtering.
- Do not store secrets in the repository (use `.env`).
- Maintain single responsibility for routes in `app.py`.
