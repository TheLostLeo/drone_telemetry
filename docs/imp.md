# Drone Telemetry & Mission Control Quick Reference

### 🛠️ Hardware Pinouts

#### Pixhawk 2.4.8 (TELEM2 DF13 6-Pin) to Raspberry Pi 4B GPIO
- **Pin 1 (VCC +5V)**: ❌ **DO NOT CONNECT** *(Pi is powered by separate BEC/UBEC)*
- **Pin 2 (TX Out)**: ➡️ **Pi Pin 10 (GPIO 15 / RXD0)**
- **Pin 3 (RX In)**: ⬅️ **Pi Pin 8 (GPIO 14 / TXD0)**
- **Pin 4 (CTS)**: ❌ **Unused** *(Flow control disabled)*
- **Pin 5 (RTS)**: ❌ **Unused** *(Flow control disabled)*
- **Pin 6 (GND)**: ➡️ **Pi Pin 9 (Ground)**

#### ESP32 Receiver Unit
- **NRF24L01+ (via HW-200 Base)**:
  - VCC -> ESP32 VIN (5V)
  - GND -> GND
  - CE -> GPIO 4
  - CSN -> GPIO 5
  - SCK -> GPIO 18 (VSPI SCK)
  - MOSI -> GPIO 23 (VSPI MOSI)
  - MISO -> GPIO 19 (VSPI MISO)
- **1.3" OLED (JMD1.3A SH1106)**:
  - VCC -> 3.3V / 5V
  - GND -> GND
  - SCL -> GPIO 22
  - SDA -> GPIO 21

#### Raspberry Pi 4B Transmitter Unit (NRF24L01+)
- **NRF24L01+ (via HW-200 Base)**:
  - VCC -> Pin 2 (5V Power)
  - GND -> Pin 20 or Pin 25 (GND)
  - CE -> Pin 15 (GPIO 22)
  - CSN -> Pin 24 (GPIO 8 / SPI0 CE0)
  - SCK -> Pin 23 (GPIO 11 / SPI0 SCLK)
  - MOSI -> Pin 19 (GPIO 10 / SPI0 MOSI)
  - MISO -> Pin 21 (GPIO 9 / SPI0 MISO)

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

### 🚀 Running the Web Dashboard & Telemetry Server

1. **Launch Dashboard Server**:
   ```bash
   # Live Pixhawk connection (default: /dev/serial0 @ 115200)
   python3 pi/dashboard_server.py --port /dev/serial0 --baud 115200 --web-port 8000

   # Or in Simulation Mode for testing without hardware
   python3 pi/dashboard_server.py --simulate --web-port 8000
   ```

2. **Access Interfaces**:
   - **Mission Control Web UI**: `http://<pi-ip>:8000`
   - **Prometheus / Grafana Metrics**: `http://<pi-ip>:8000/metrics`
   - **Live WebSocket Feed**: `ws://<pi-ip>:8000/ws/telemetry`
   - **JSON Snapshot API**: `http://<pi-ip>:8000/api/telemetry`

3. **Importing into Grafana**:
   - Import `pi/grafana_dashboard.json` into your Grafana instance pointing to Prometheus scraping `http://<pi-ip>:8000/metrics`.

4. **Testing TELEM2 Link**:
   ```bash
   python3 pi/test_mavlink_telem2.py --port /dev/serial0 --baud 115200
   ```

---

### 🔄 Auto-Start on Boot (Systemd Service)

From the project root directory:
```bash
# Install dependencies
pip install -r requirements.txt

# Enable and start autostart service on boot
./setup_autostart.sh

# Check live service status
sudo systemctl status drone-telemetry.service

# View real-time journal logs
journalctl -u drone-telemetry.service -f

# Disable autostart
./disable_autostart.sh
```
