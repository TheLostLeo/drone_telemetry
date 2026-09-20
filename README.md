# 🛸 Drone Telemetry & Mission Control System

A high-performance, real-time drone companion system running on a **Raspberry Pi 4B** connected to a **Pixhawk 2.4.8 (ArduPilot)** flight controller, broadcasting dual telemetry streams to a handheld **ESP32 OLED Ground Unit** and an aerospace-grade **Live Web Dashboard**.

---

## 🏗️ System Architecture

```
                       ┌───────────────────────────────┐
                       │     Pixhawk 2.4.8 Flight      │
                       │          Controller           │
                       │    (ArduPilot 4.x Firmware)   │
                       └───────────────┬───────────────┘
                                       │ MAVLink (115200 baud)
                                       │ USB (/dev/ttyACM0) or TELEM2 (/dev/serial0)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Raspberry Pi 4B Companion Computer                    │
│                                (pi/main.py)                                 │
│                                                                             │
│  ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────┐  │
│  │ Module 1: Radio TX    │ │ Module 2: Web Server  │ │ Module 3: Grid    │  │
│  │ NRF24L01+ SPI (5 Hz)  │ │ Mission Control (10Hz)│ │ Search Autonomy   │  │
│  │ 32-byte frame stream  │ │ Port 8000 WebSockets  │ │ MAVLink Waypoints │  │
│  └───────────┬───────────┘ └───────────┬───────────┘ └───────────────────┘  │
└──────────────┼─────────────────────────┼────────────────────────────────────┘
               │ 2.4 GHz RF              │ HTTP / WebSockets
               ▼                         ▼
┌──────────────────────────────┐ ┌────────────────────────────────────────────┐
│   ESP32 Handheld Receiver    │ │       Any Web Browser / Ground PC          │
│  OLED + ESP Wi-Fi JSON API   │ │         http://<pi-ip>:8000                │
└──────────────────────────────┘ └────────────────────────────────────────────┘
```

---

## ⚡ Quick Start Guide

### 1. Clone & Set Up Virtual Environment on Raspberry Pi
```bash
git clone https://github.com/TheLostLeo/drone_telemetry.git
cd drone_telemetry

# Create and activate python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

### 2. Run the Master Companion Server

#### A. Bench Testing Mode (Pixhawk plugged into Pi via USB):
```bash
python3 pi/main.py --port /dev/ttyACM0 --baud 115200 --web-port 8000
```

#### B. Flight Mode (Pixhawk TELEM2 DF13 connected to Pi GPIO UART):
```bash
python3 pi/main.py --port /dev/serial0 --baud 115200 --web-port 8000
```

#### C. NRF-only bridge mode (frontend runs from the laptop through the ESP32):
```bash
python3 pi/main.py --port /dev/serial0 --baud 115200 --no-web
```

#### D. Simulation Mode (Runs full virtual flight physics without hardware):
```bash
python3 pi/main.py --simulate --web-port 8000
```

---

### 3. Open Mission Control Web Dashboard
Open any browser on your phone, tablet, or laptop connected to the same Wi-Fi network:
```
http://<your-raspberry-pi-ip>:8000
```

For the standalone React dashboard in `web/`, the ESP32 serves the live NRF telemetry snapshot at:
```
http://192.168.4.1/telemetry.json
```

The ESP32 starts an access point named `DroneTelemetryESP32` with password `drone12345`. The dashboard polls that JSON endpoint and falls back to mock telemetry if the ESP32 is not reachable. To point the dashboard at a different ESP address:
```
http://localhost:5173/?telemetryUrl=http://<esp-ip>/telemetry.json
```

---

## 🧪 Sensor Stream Diagnostic Test

To quickly verify that the Pixhawk is streaming raw attitude, 3-axis gyro rates, and barometric altitude over USB:

```bash
python3 test_stream.py
```

**Expected Output:**
```
[*] Connecting to Pixhawk on /dev/ttyACM0 (115200 baud)...
[*] Waiting for Heartbeat...
[✓] Heartbeat received! System: 1, Component: 1

======================================================================
  🚀 LISTENING FOR LIVE SENSOR PACKETS (TILT THE PIXHAWK NOW!)
======================================================================
>>> [LIVE ATTITUDE] Roll:  +14.2° | Pitch:   -3.5° | Yaw: 182.1°
>>> [LIVE IMU]      Z-Accel: 9810 | X-Gyro: +120
>>> [LIVE ATTITUDE] Roll:  +28.6° | Pitch:  +10.1° | Yaw: 184.3°
```

---

## 🔌 Hardware Wiring & Pinouts

### 1. Pixhawk TELEM2 to Raspberry Pi 4B (GPIO UART)
| Pixhawk TELEM2 Pin | Signal | Raspberry Pi 40-Pin Header | Physical Pin |
|---|---|---|---|
| Pin 1 (Red) | VCC 5V | **Do NOT connect** (Pi powered independently) | — |
| Pin 2 (TX) | Pixhawk TX | GPIO 15 (RXD0) | **Pin 10** |
| Pin 3 (RX) | Pixhawk RX | GPIO 14 (TXD0) | **Pin 8** |
| Pin 4 (CTS) | CTS | Not used | — |
| Pin 5 (RTS) | RTS | Not used | — |
| Pin 6 (Black) | GND | Ground | **Pin 9** |

---

### 2. NRF24L01+ Transceiver to Raspberry Pi 4B (SPI0)
| NRF24L01+ Pin | Raspberry Pi Pin | Physical Pin | Function |
|---|---|---|---|
| **VCC** | 3.3V Power | **Pin 1** or **Pin 17** | 3.3V Logic (10-100µF capacitor recommended across VCC/GND) |
| **GND** | Ground | **Pin 6**, **Pin 9**, or **Pin 25** | Ground |
| **CE** | GPIO 25 | **Pin 22** | Chip Enable |
| **CSN** | GPIO 8 / SPI0 CE0 | **Pin 24** | SPI Chip Select |
| **SCK** | GPIO 11 (SCLK) | **Pin 23** | SPI Clock |
| **MOSI** | GPIO 10 (MOSI) | **Pin 19** | SPI Data Out |
| **MISO** | GPIO 9 (MISO) | **Pin 21** | SPI Data In |

---

### 3. ESP32 Handheld Receiver & SH1106 1.3" OLED
Flash firmware in `esp/esp.ino` using Arduino IDE:
* **OLED SDA** $\rightarrow$ ESP32 GPIO 21
* **OLED SCL** $\rightarrow$ ESP32 GPIO 22
* **NRF24 CE** $\rightarrow$ ESP32 GPIO 4
* **NRF24 CSN** $\rightarrow$ ESP32 GPIO 5
* **NRF24 SCK** $\rightarrow$ ESP32 GPIO 18
* **NRF24 MOSI** $\rightarrow$ ESP32 GPIO 23
* **NRF24 MISO** $\rightarrow$ ESP32 GPIO 19

---

## 🤖 Systemd Background Autostart

To configure the companion server to start automatically whenever the Raspberry Pi boots:

```bash
# Enable and start background systemd service
sudo ./setup_autostart.sh

# Check live service status and logs
sudo systemctl status drone-telemetry.service
sudo journalctl -u drone-telemetry.service -f

# Disable autostart
sudo ./disable_autostart.sh
```

---

## ❓ Frequently Asked Questions (FAQ)

#### Q: Why does the battery voltage show `USB 5V` / `0.00V` during bench testing?
> When the Pixhawk is powered only via a USB cable, the 5V bus powers the internal processor and IMU sensors directly. The 6-pin **Power Module** port (connected to the LiPo battery voltage divider ADC) has no battery attached, so ArduPilot correctly reports `0.00V`. Once you plug a 3S/4S/6S LiPo battery into the power module on the drone, live voltage and current readings will appear automatically.

#### Q: How does the PID tracking graph work on the bench?
> In `STABILIZE` mode with RC sticks centered, ArduPilot commands a target level angle of $0.0^\circ$. As you tilt the Pixhawk in your hand, the measured roll/pitch diverges from the target, showing the real-time tracking error that the PID control loop would correct in the air.
