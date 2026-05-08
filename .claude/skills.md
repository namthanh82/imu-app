# Skills / Reusable Procedures

## Verify System Setup
1. Confirm the `.env` file is present and properly configured with `SECRET_KEY`, `SERIAL_PORT`, and `OPENAI_API_KEY`.
2. Check `requirements.txt` to ensure all Flask, PySerial, and LangChain dependencies are installed.

## Testing Serial Connection
1. Connect the IMU hardware via USB.
2. Ensure the correct port is set in `.env` (`SERIAL_PORT=COM14`).
3. If necessary, use a basic serial monitor (e.g. PuTTY or Arduino IDE) at `115200` baud to verify raw incoming data:
   `IMU, <id>, <seq>, <w>, <x>, <y>, <z>, <pico_ts>, <master_ts>`
