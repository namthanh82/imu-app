# Current Task

## Active Goal
Maintain and extend the ReTrack IMU-based rehabilitation tracking system.

## Immediate Work
- Update project architecture and setup toward a real desktop application workflow.
- Ensure the app does not stay as a normal browser tab during packaging or runtime.
- Preserve current IMU, database, and AI features while preparing the executable path.
- Document the steps needed to produce a Windows `.exe`.

## Constraints
- Do not introduce hardcoded secrets.
- Do not keep browser-tab-based UX as the final runtime experience.
- Maintain clear modularity between `app.py`, `serial_handler.py`, `database.py`, and `imurtrack_ai/`.

## Success Criteria
- The app launches in a desktop-style window instead of a standard browser tab.
- A repeatable build process exists to generate a Windows `.exe`.
- Live IMU data and 3D model rendering continue working in the desktop runtime.
