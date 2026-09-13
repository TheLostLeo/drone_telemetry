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
- **Pixhawk Flight Controller (TELEM2 UART @ 115200 baud)**:
  - Pixhawk TX (Pin 2) -> Pi Pin 10 (GPIO 15 / RXD)
  - Pixhawk RX (Pin 3) -> Pi Pin 8 (GPIO 14 / TXD)
  - Pixhawk GND (Pin 6) -> Pi Pin 9 (Ground)

### 📡 Radio Profile
- Channel: 90 (2.490 GHz)
- Data Rate: 250 kbps
- PA Level: RF24_PA_MAX (Pi TX), RF24_PA_HIGH (ESP RX)
- CRC: 16-bit
- Auto-ACK: Disabled (Broadcast)

### 🚀 Running on Boot (Auto-Start)

To set up the script to run automatically on Raspberry Pi boot:
```bash
./setup_autostart.sh
```

- View live telemetry logs: `journalctl -u drone-telemetry.service -f`
- Check service status: `sudo systemctl status drone-telemetry.service`
- Disable autostart: `./disable_autostart.sh`
