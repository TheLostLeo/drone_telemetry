# Master Companion Server Architecture & Web Dashboard

### 1. Modular Architecture Overview
The Raspberry Pi 4B runs a unified supervisor script (`pi/main.py`) coordinating three concurrent background modules over a shared MAVLink connection:

```
pi/main.py (Master Supervisor)
├── modules/mavlink_manager.py     (Singleton MAVLink Serial Owner & Mode Controller)
├── modules/sbc_monitor.py         (Pi CPU Temp, Load, RAM Diagnostics)
├── modules/radio_tx_module.py     [MODULE 1] NRF24L01+ 20-byte Compact RF Broadcaster
├── modules/web_dashboard_module.py [MODULE 2] Mission Control Web Dashboard & WebSockets (:8000)
└── modules/grid_search_module.py  [MODULE 3] Autonomous Mission Planner & Grid Generator
```

### 2. Module Responsibilities
- **`mavlink_manager.py`**: Manages exclusive serial access to `/dev/serial0` (TELEM2 @ 115200 baud) or `/dev/ttyACM0` (USB). Decodes 11 categories of flight telemetry, ingests `MISSION_CURRENT` and `MISSION_ITEM_REACHED`, and provides thread-safe mission uploads and flight mode switching (`AUTO`, `LOITER`, `RTL`).
- **`grid_search_module.py` (Module 3)**: Multi-pattern autonomous mission generator (Boustrophedon Grid, Expanding Spiral, Sector Search) with dynamic vertical takeoff (`lat=0, lon=0`), speed control, route preview analytics, and MAVLink compiler.
- **`web_dashboard_module.py` (Module 2)**: Serves the interactive aerospace Mission Control UI over port 8000 with 10 Hz zero-latency WebSockets, Leaflet GPS satellite tracking, interactive map point picking, live route preview, and floating map mission HUD.
- **`radio_tx_module.py` (Module 1)**: Packs telemetry into the 20-byte struct with 8-bit XOR checksum and transmits at 5 Hz over hardware SPI0 to the handheld ESP32 ground unit.
- **`sbc_monitor.py`**: Queries Linux `/proc` and `/sys` to extract CPU core temperature (°C), CPU load %, RAM usage, and disk space.
