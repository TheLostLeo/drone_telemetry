# System Architecture & Technical Detail

### 1. Companion Computer Telemetry Hub Architecture
The drone air unit combines a **Pixhawk 2.4.8** flight controller with a **Raspberry Pi 4B** acting as the onboard companion computer.
- **Physical Link**: 3-wire UART connection (TX on Pin 10, RX on Pin 8, Ground on Pin 9) connected to Pixhawk's TELEM2 DF13 6-pin socket.
- **Protocol**: MAVLink2 at 115200 baud.
- **Single Serial Port Ownership**: `MAVLinkManager` acts as the exclusive thread-safe reader on `/dev/serial0`, preventing byte collisions and parsing all flight telemetry into structured state.

### 2. Live Telemetry Metrics (11 Categories)
The telemetry hub captures and streams:
1. **Total Battery Voltage & Power**: Voltage (V), Current (A), Remaining (%).
2. **Individual Cell Voltages**: Cell 1 to 6 voltages in Volts and balance delta ($\Delta V$).
3. **Altitude Dynamics**: Relative altitude AGL (m), MSL (m), and climb rate (m/s).
4. **GPS Positioning**: Latitude, Longitude, Satellites count, Fix type (3D/DGPS/RTK), HDOP, and live Leaflet map tracking.
5. **Signal Strength**: RC link RSSI (%) and radio telemetry quality.
6. **Heading & Compass**: 360° heading and compass calibration status.
7. **Flight & Mission Status**: Armed / Disarmed state, Flight Mode (GUIDED, AUTO, LOITER, RTL, STABILIZE), and Mission Substates.
8. **3-Axis Gyroscope Rates**: Real-time angular rates ($\omega_x, \omega_y, \omega_z$ in deg/s) and accelerometer ($A_x, A_y, A_z$ in g).
9. **PID Attitude Tracking**: Target vs Measured Pitch and Roll, with real-time error tracking.
10. **Motor Equalizer**: Power output for Motors 1, 2, 3, 4 (PWM $\mu\text{s}$ and thrust %).
11. **SBC Health**: Raspberry Pi CPU Core Temperature (°C), CPU Load (%), RAM Usage, and Storage.

### 3. Dual Ground Visualization Layers
- **Interactive Web Dashboard (`pi/web/`)**: Served directly from the Pi over WebSockets at `http://<pi-ip>:8000` with 10 Hz zero-latency streaming, Chart.js graphs, and Leaflet satellite maps.
- **Grafana Integration (`pi/grafana_dashboard.json`)**: Pre-configured 11-panel dashboard export querying the `/metrics` endpoint.
- **Handheld Ground Receiver (`esp/esp.ino`)**: Handheld ESP32 + SH1106 OLED receiver unit reading 20-byte packed packets over NRF24L01+ 2.4 GHz RF.
