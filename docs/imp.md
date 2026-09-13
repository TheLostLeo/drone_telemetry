# ESP32 & Raspberry Pi Drone Telemetry Quick Reference

### 🛠️ Hardware Pinouts

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

#### Raspberry Pi 4B Transmitter Unit
- **NRF24L01+ (via HW-200 Base)**:
  - VCC -> Pin 2 (5V Power)
  - GND -> Pin 20 or Pin 25 (GND)
  - CE -> Pin 15 (GPIO 22)
  - CSN -> Pin 24 (GPIO 8 / SPI0 CE0)
  - SCK -> Pin 23 (GPIO 11 / SPI0 SCLK)
  - MOSI -> Pin 19 (GPIO 10 / SPI0 MOSI)
  - MISO -> Pin 21 (GPIO 9 / SPI0 MISO)
- **Pixhawk Flight Controller**:
  - Option A: USB to Raspberry Pi (`/dev/ttyACM0` at 115200 baud)
  - Option B: TELEM2 UART to Pin 8/10 (`/dev/serial0` at 57600 baud)

### 📡 Radio Profile
- Channel: 90 (2.490 GHz)
- Data Rate: 250 kbps
- PA Level: RF24_PA_MAX (Pi TX), RF24_PA_HIGH (ESP RX)
- CRC: 16-bit
- Auto-ACK: Disabled (Broadcast)

### 🚀 Running the Pi Transmitter

1. Install dependencies:
```bash
pip3 install -r pi/requirements.txt
```
2. Test simulated telemetry broadcast:
```bash
python3 pi/simulate_telemetry_tx.py
```
3. Run live Pixhawk MAVLink stream:
```bash
python3 pi/pixhawk_telemetry_tx.py --port /dev/ttyACM0 --baud 115200
```
