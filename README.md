# Drone Telemetry Relay

Live telemetry path:

```text
Pixhawk -> MAVLink UART/USB -> Raspberry Pi -> NRF24L01+
        -> ESP32 -> Wi-Fi JSON -> laptop web dashboard
```

## Folder Layout

- `pi/tele/` - Raspberry Pi telemetry relay code. Reads MAVLink from Pixhawk, packages telemetry, and transmits NRF24 frames.
- `esp/` - ESP32 receiver firmware. Receives NRF24 frames, keeps the OLED display updated, and serves `/telemetry.json` over Wi-Fi.
- `web/` - React/Vite laptop dashboard. Polls the ESP32 JSON endpoint.

## Pixhawk to Raspberry Pi Wiring

For Pixhawk TELEM2 to Raspberry Pi UART:

| Pixhawk TELEM2 | Raspberry Pi 4B |
|---|---|
| Pin 2 TX | Pin 10 / GPIO15 RXD0 |
| Pin 3 RX | Pin 8 / GPIO14 TXD0 |
| Pin 6 GND | Pin 9 GND |
| Pin 1 +5V | Do not connect |

ArduPilot parameters:

```text
SERIAL2_PROTOCOL = 2
SERIAL2_BAUD = 115
BRD_SER2_RTSCTS = 0
```

## Raspberry Pi NRF24 Pins

| NRF24L01+ | Raspberry Pi 4B |
|---|---|
| VCC | 5V through HW-200/base regulator, or stable 3.3V regulator |
| GND | GND |
| CE | GPIO25 / physical pin 22 |
| CSN | GPIO8 / SPI0 CE0 / physical pin 24 |
| SCK | GPIO11 / physical pin 23 |
| MOSI | GPIO10 / physical pin 19 |
| MISO | GPIO9 / physical pin 21 |

## ESP32 Pins

NRF24L01+ on ESP32 VSPI:

| NRF24L01+ | ESP32 |
|---|---|
| VCC | VIN/5V through HW-200/base regulator |
| GND | GND |
| CE | GPIO4 |
| CSN | GPIO5 |
| SCK | GPIO18 |
| MOSI | GPIO23 |
| MISO | GPIO19 |

OLED:

| OLED | ESP32 |
|---|---|
| SDA | GPIO21 |
| SCL | GPIO22 |
| VCC | 3.3V or 5V |
| GND | GND |

## Run on Raspberry Pi

Install Python dependencies:

```bash
cd ~/drone_telemetry
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Live Pixhawk over TELEM2 UART:

```bash
python3 pi/tele/main.py --port /dev/serial0 --baud 115200 --radio-rate 5
```

Live Pixhawk over USB:

```bash
python3 pi/tele/main.py --port /dev/ttyACM0 --baud 115200 --radio-rate 5
```

NRF test without Pixhawk:

```bash
python3 pi/tele/main.py --simulate --radio-rate 5
```

`--no-web` is still accepted for old commands, but the Pi no longer hosts the frontend. The web dashboard runs from `web/` and reads ESP32 JSON.

## Flash ESP32

1. Open `esp/esp.ino` in Arduino IDE.
2. Set `WIFI_STA_SSID` and `WIFI_STA_PASSWORD`.
3. Flash the ESP32.
4. Open Serial Monitor at `115200`.
5. Confirm the ESP32 prints its IP address and NRF status.

The ESP32 serves telemetry at:

```text
http://<esp-ip>/telemetry.json
```

Example:

```text
http://10.160.142.17/telemetry.json
```

## Run the Web Dashboard

From the laptop:

```bash
cd web
docker build -t drone-telemetry-dashboard-web .
docker run --rm -p 5173:5173 drone-telemetry-dashboard-web
```

Open:

```text
http://localhost:5173
```

When the dashboard opens, enter the ESP32 IP shown on the OLED, for example:

```text
10.160.142.17
```

The dashboard will poll `http://<esp-ip>/telemetry.json`.

## What to Expect

On the Pi, live Pixhawk mode should show:

```text
[+] Opened serial port '/dev/serial0' at 115200 baud.
[*] Waiting for MAVLink Heartbeat from Pixhawk...
[✓] Heartbeat received from Pixhawk
[✓ LIVE] Mode: STABILIZE | ...
```

If battery shows `USB 5V`, the Pixhawk is not reporting LiPo voltage yet. Connect/configure the power module for real battery voltage.

If satellites stay `0`, the GPS has no fix or GPS data is not available indoors.
