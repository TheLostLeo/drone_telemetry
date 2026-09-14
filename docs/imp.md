# Drone Mission Control Quick Reference

### 🛠️ Hardware Pinouts

#### Pixhawk 2.4.8 (TELEM2 DF13 6-Pin) to Raspberry Pi 4B GPIO
- **Pin 1 (VCC +5V)**: ❌ **DO NOT CONNECT** *(Pi is powered independently)*
- **Pin 2 (TX Out)**: ➡️ **Pi Pin 10 (GPIO 15 / RXD0)**
- **Pin 3 (RX In)**: ⬅️ **Pi Pin 8 (GPIO 14 / TXD0)**
- **Pin 4 (CTS)**: ❌ **Unused** *(Flow control disabled)*
- **Pin 5 (RTS)**: ❌ **Unused** *(Flow control disabled)*
- **Pin 6 (GND)**: ➡️ **Pi Pin 9 (Ground)**

#### Raspberry Pi 4B NRF24L01+ Transmitter (Module 1)
- VCC -> Pin 2 (5V Power to HW-200 Base)
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

### 🚀 Running the Master Server (`pi/main.py`)

1. **Manual Launch**:
   ```bash
   # Live Pixhawk over TELEM2 GPIO UART (/dev/serial0 @ 115200)
   python3 pi/main.py --port /dev/serial0 --baud 115200 --web-port 8000

   # Live Pixhawk over USB (/dev/ttyACM0 @ 115200)
   python3 pi/main.py --port /dev/ttyACM0 --baud 115200 --web-port 8000

   # Simulation Test Mode (No hardware needed)
   python3 pi/main.py --simulate --web-port 8000
   ```

2. **Access Mission Control Web Dashboard**:
   Open browser on any PC / Phone / Tablet:
   ```
   http://<pi-ip-address>:8000
   ```
   *(or `http://pi.local:8000`)*

3. **Auto-Start on Boot via Systemd**:
   ```bash
   ./setup_autostart.sh
   sudo systemctl status drone-telemetry.service
   journalctl -u drone-telemetry.service -f
   ./disable_autostart.sh
   ```
