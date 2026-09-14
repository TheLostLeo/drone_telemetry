# Quick Reference & Setup

### Tech Stack
- Raspberry Pi 4B (Linux / Python 3)
- Pixhawk 2.4.8 (ArduPilot / MAVLink2)
- Leaflet.js (CartoDB DarkMatter Tiles)
- Chart.js (Rolling Multi-Series Telemetry)
- Autonomous Mission Planner (Boustrophedon Grid, Expanding Spiral, Sector SAR)
- ESP32 + NRF24L01+ PA+LNA + 1.3 SH1106 OLED

### Key Endpoints / Connections
- HTTP Web UI: http://<pi-ip>:8000
- WebSocket Telemetry: ws://<pi-ip>:8000/ws/telemetry (10 Hz)
- Mission Preview API: POST /api/mission/preview
- Mission Upload API: POST /api/mission/upload
- Mission Execution APIs: POST /api/mission/start, /api/mission/pause, /api/mission/abort, /api/mission/clear
- Telemetry Snapshot: GET /api/telemetry

### Basic Setup Info
1. python3 pi/main.py --port /dev/serial0 --baud 115200 --web-port 8000
2. Or in Simulation mode: python3 pi/main.py --simulate --web-port 8000
