# System Architecture & Technical Detail

### 1. Hardware Architecture
The handheld ground receiver unit is composed of an **ESP-WROOM-32** connected to a **1.3" JMD1.3A SH1106 OLED** (I2C) and an **NRF24L01+ PA+LNA** (VSPI) supported by an **HW-200 3.3V adapter base**.

#### Power Routing Rationale
The NRF24L01+ PA+LNA module draws ~115mA current peaks during active transmit/receive windows. Powering the HW-200 adapter directly from the ESP32's `VIN` (5V pin) utilizes the onboard AMS1117 regulator and bypass capacitors to provide clean, ripple-free 3.3V power, completely eliminating ESP32 brownouts and RF resets.

### 2. Symmetrical 20-Byte Packet Protocol
Unlike legacy CSV text strings which exceed the 32-byte RF24 payload limit (~42 bytes) and lead to string corruption or buffer overflows, this system employs a 20-byte packed binary struct:
- `uint8_t magic` (0xAA)
- `uint8_t seq` (0-255)
- `uint16_t bat_mv` (millivolts)
- `int16_t rssi` (% / dBm)
- `int32_t alt_cm` (centimeters)
- `int32_t lat_e7` (degrees * 10^7)
- `int32_t lon_e7` (degrees * 10^7)
- `uint8_t satellites`
- `uint8_t checksum` (8-bit XOR)

### 3. Display Logic & Loss of Signal (LOS) Guard
The OLED is refreshed at 20 FPS (every 50ms) without blocking the NRF24 FIFO read loop.
If no packets are decoded for $\ge 30,000\text{ ms}$, the display transitions into a dedicated `! NO CONNECTION !` warning screen with dynamic elapsed loss tracking (`Lost: Xs ago`). Telemetry immediately recovers upon packet reception.
