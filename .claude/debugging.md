# Debugging Rules

- If the COM port fails to open, verify it's not locked by Arduino IDE or another serial monitor program.
- If angles look flipped on the 3D model, verify the IMU ID assignments:
  - 1: Thigh
  - 2 & 3: Shank
  - 4: Foot
- If 3D models glitch or freeze, check the `imu_data` WebSocket payload in the browser developer console.
- Check backend Flask logs for OpenAI API errors if the AI clinical report generation fails.
- Test one layer at a time: `Hardware (Serial)` -> `Python (serial_handler.py)` -> `Backend (app.py)` -> `Frontend (dashboard.html)`.
