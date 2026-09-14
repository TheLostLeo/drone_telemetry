# System Architecture & Technical Detail (Grafana + Raspberry Pi)

### 1. Dedicated Grafana Prometheus Exporter Architecture
The telemetry hub running on the Raspberry Pi serves as a dedicated Prometheus metrics exporter (`pi/grafana_exporter.py`).
- **Input Stream**: Connects to Pixhawk 2.4.8 (via `/dev/ttyACM0` for USB testing or `/dev/serial0` for TELEM2 UART @ 115200 baud).
- **Single Serial Owner**: `MAVLinkManager` exclusively manages the serial link, parsing all MAVLink2 packets into thread-safe memory.
- **SBC Telemetry**: `SBCMonitor` queries `/proc` and `/sys` to monitor Raspberry Pi CPU core temperatures, CPU load %, RAM usage, and disk stats.
- **Prometheus Export**: Exposes standard Prometheus text metrics at `http://<pi-ip>:8000/metrics`.

### 2. PC Grafana Visualization Suite
Grafana runs on your PC / laptop and scrapes the Raspberry Pi directly.
The pre-configured dashboard (`pi/grafana_dashboard.json`) organizes all 11 telemetry categories into 4 structured sections:
1. **Flight State & Critical Status**: Arming state, Total Battery Voltage gauge, Altitude AGL, Compass Heading, RC RSSI.
2. **Sensors, Gyro Rates & Attitude**: Real-time 3-Axis Gyroscope rates ($\omega_x, \omega_y, \omega_z$), Euler attitude angles (Roll/Pitch/Yaw), 3-Axis Accelerometer ($A_x, A_y, A_z$), and PID tracking error.
3. **Power, Cells & Motor Outputs**: Individual 6-cell voltage bar gauges with balance delta, and 4-channel motor PWM equalizer bars.
4. **Raspberry Pi SBC Diagnostics**: Real-time Raspberry Pi CPU temperature gauge with thermal warnings, CPU load %, and RAM usage.
