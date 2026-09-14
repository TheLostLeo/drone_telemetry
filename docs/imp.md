# Drone Telemetry Grafana Exporter Quick Reference

### 🛠️ Hardware Pinouts

#### Pixhawk 2.4.8 (TELEM2 DF13 6-Pin) to Raspberry Pi 4B GPIO
- **Pin 1 (VCC +5V)**: ❌ **DO NOT CONNECT** *(Pi is powered independently)*
- **Pin 2 (TX Out)**: ➡️ **Pi Pin 10 (GPIO 15 / RXD0)**
- **Pin 3 (RX In)**: ⬅️ **Pi Pin 8 (GPIO 14 / TXD0)**
- **Pin 4 (CTS)**: ❌ **Unused** *(Flow control disabled)*
- **Pin 5 (RTS)**: ❌ **Unused** *(Flow control disabled)*
- **Pin 6 (GND)**: ➡️ **Pi Pin 9 (Ground)**

#### Testing via USB Port
- Connect Pixhawk Micro-USB to Raspberry Pi USB port (`/dev/ttyACM0`).

---

### ⚙️ Pixhawk Parameters (ArduPilot)
- `SERIAL2_PROTOCOL`: `2` (MAVLink2)
- `SERIAL2_BAUD`: `115` (115200 baud)
- `BRD_SER2_RTSCTS`: `0` (Disabled)
- `SR2_RAW_SENS`: `2` (2 Hz)
- `SR2_EXT_STAT`: `2` (2 Hz)
- `SR2_POSITION`: `5` (5 Hz)
- `SR2_EXTRA1`: `5` (5 Hz)

---

### 🚀 Running the Grafana Telemetry Exporter on Raspberry Pi

1. **Launch Prometheus Exporter on Pi**:
   ```bash
   # For USB connection (/dev/ttyACM0 @ 115200)
   python3 pi/grafana_exporter.py --port /dev/ttyACM0 --baud 115200 --metrics-port 8000

   # For GPIO TELEM2 connection (/dev/serial0 @ 115200)
   python3 pi/grafana_exporter.py --port /dev/serial0 --baud 115200 --metrics-port 8000

   # Simulation test mode
   python3 pi/grafana_exporter.py --simulate --metrics-port 8000
   ```

2. **Endpoints Provided by Pi**:
   - Prometheus Metrics: `http://<pi-ip>:8000/metrics`
   - JSON Snapshot: `http://<pi-ip>:8000/api/telemetry`

---

### 📊 Setting up Grafana on Your PC

1. **Configure Prometheus Data Source in Grafana**:
   - In Grafana (e.g. `http://localhost:3000` on your PC), go to **Connections -> Data Sources -> Add Data Source -> Prometheus**.
   - Set Prometheus Server URL to: `http://<your-pi-ip-address>:8000` (or `http://pi.local:8000`).
   - Click **Save & Test**.

2. **Import Dashboard**:
   - In Grafana, click **Dashboards -> New -> Import**.
   - Upload or paste the contents of `pi/grafana_dashboard.json`.
   - Select your Prometheus data source and click **Import**.

3. **All 11 Live Panels Ready**:
   - Arming state & flight mode
   - Total battery voltage (V), current (A), remaining (%)
   - 6-Cell individual voltages (V) & balance delta ($\Delta V$)
   - Relative altitude (AGL), MSL & climb rate (m/s)
   - 360° Compass heading
   - RC signal strength (RSSI %)
   - 3-Axis Gyroscope rates ($\omega_x, \omega_y, \omega_z$ in deg/s)
   - 3-Axis Accelerometer ($A_x, A_y, A_z$ in g)
   - Euler attitude (Roll / Pitch / Yaw) & PID tracking errors
   - 4-Channel motor outputs (PWM $\mu\text{s}$ & %)
   - Raspberry Pi SBC diagnostics (CPU temperature, CPU load, RAM %)

---

### 🔄 Auto-Start on Pi Boot
```bash
./setup_autostart.sh
sudo systemctl status drone-telemetry.service
```
