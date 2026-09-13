
#!/usr/bin/env python3
"""
======================================================================================
Project: Drone Telemetry Transmitter - Simulation & Template Test (Raspberry Pi 4B)
File: pi/simulate_telemetry_tx.py

Description:
  Generates and broadcasts simulated drone telemetry packets over NRF24L01+ to the
  ESP32 ground receiver. Useful for verifying RF link, OLED UI layout, and 30s timeout
  safeguard without needing a live Pixhawk or drone in the air.

Raspberry Pi 4B Wiring:
  - HW-200 VCC -> Pin 2 (5V Power)
  - GND        -> Pin 20 or Pin 25 (GND)
  - CE         -> Pin 15 (GPIO 22)
  - CSN        -> Pin 24 (GPIO 8 / SPI0 CE0)
  - SCK        -> Pin 23 (GPIO 11 / SPI0 SCLK)
  - MOSI       -> Pin 19 (GPIO 10 / SPI0 MOSI)
  - MISO       -> Pin 21 (GPIO 9  / SPI0 MISO)
======================================================================================
"""

import sys
import time
import math
import struct

# Attempt importing pyrf24
try:
    from pyrf24 import RF24, RF24_PA_MAX, RF24_250KBPS, RF24_CRC_16
except ImportError:
    print("\n[ERROR] 'pyrf24' library not found!")
    print("Please install it on your Raspberry Pi using:")
    print("  sudo apt-get update && sudo apt-get install python3-pip python3-dev -y")
    print("  pip3 install pyrf24\n")
    sys.exit(1)

# ======================================================================================
# CONFIGURATION
# ======================================================================================
CE_PIN = 22       # GPIO 22 (Pin 15)
CSN_PIN = 0       # SPI0 CE0 (Pin 24 / GPIO 8)

RF_CHANNEL = 90   # 2.490 GHz (Matches ESP32 Channel 90)
PIPE_ADDRESSES = [b"1Node", b"2Node"]

PACKET_MAGIC = 0xAA
SEND_INTERVAL = 0.2  # 5 Hz (send every 200 ms)

# Base Coordinates for simulation (Bangalore Aerodrome example)
BASE_LAT = 12.971598
BASE_LON = 77.594562

# ======================================================================================
# 20-BYTE PACKET ENCODER
# ======================================================================================
def create_telemetry_packet(seq: int, bat_v: float, rssi: int, alt_m: float, 
                            lat_deg: float, lon_deg: float, sats: int) -> bytes:
    """
    Packs telemetry values into a 20-byte packed binary struct:
      Byte 0:     0xAA (Magic Header)
      Byte 1:     seq (uint8 0-255)
      Bytes 2-3:  bat_mv (uint16 in millivolts, e.g. 12580 = 12.58V)
      Bytes 4-5:  rssi (int16, e.g. 92%)
      Bytes 6-9:  alt_cm (int32 in centimeters, e.g. 4520 = 45.20m)
      Bytes 10-13: lat_e7 (int32, latitude * 10^7)
      Bytes 14-17: lon_e7 (int32, longitude * 10^7)
      Byte 18:    satellites (uint8)
      Byte 19:    checksum (8-bit XOR over bytes 0..18)
    """
    bat_mv = int(max(0.0, bat_v) * 1000)
    alt_cm = int(alt_m * 100)
    lat_e7 = int(lat_deg * 10000000)
    lon_e7 = int(lon_deg * 10000000)
    
    # Pre-pack payload without checksum (< = Little Endian)
    payload_raw = struct.pack(
        "<BBHhiiiB",
        PACKET_MAGIC,
        seq % 256,
        bat_mv,
        int(rssi),
        alt_cm,
        lat_e7,
        lon_e7,
        int(sats)
    )
    
    # Compute XOR checksum
    checksum = 0
    for byte in payload_raw:
        checksum ^= byte
        
    # Append 1-byte checksum (Total: Exactly 20 Bytes)
    return payload_raw + bytes([checksum])

# ======================================================================================
# MAIN EXECUTION
# ======================================================================================
def main():
    print("=" * 60)
    print("  Raspberry Pi 4B - Drone Telemetry RF Transmitter (Test)  ")
    print("=" * 60)
    
    # 1. Initialize NRF24L01 on SPI0
    print(f"[*] Initializing NRF24L01 (CE=GPIO {CE_PIN}, CSN=SPI0_CE0)...")
    radio = RF24(CE_PIN, CSN_PIN)
    
    if not radio.begin():
        print("[!] FATAL: NRF24L01 hardware not detected.")
        print("    Check SPI is enabled ('sudo raspi-config') and check wiring.")
        sys.exit(1)
        
    radio.setChannel(RF_CHANNEL)
    radio.setDataRate(RF24_250KBPS)      # Long range mode (250 kbps)
    radio.setPALevel(RF24_PA_MAX)        # Maximum transmit power for PA+LNA
    radio.setCRCLength(RF24_CRC_16)      # 16-bit hardware CRC
    radio.setAutoAck(False)              # Broadcast mode (No-ACK)
    
    # ESP32 listens on PIPE_ADDRESSES[1] ("2Node"), so Pi writes to PIPE_ADDRESSES[1]
    radio.openWritingPipe(PIPE_ADDRESSES[1])
    radio.stopListening()
    
    print(f"[+] Radio ready on Channel {RF_CHANNEL} at 250 KBPS.")
    print("[+] Broadcasting simulated flight packets. Press Ctrl+C to stop.\n")
    
    seq = 0
    t_start = time.time()
    
    try:
        while True:
            t = time.time() - t_start
            
            # --- Generate Realistic Drone Flight Telemetry ---
            # 1. Battery: Starts at 12.6V, slowly drops with flight time
            battery_v = max(10.5, 12.58 - (t * 0.005))
            
            # 2. RSSI: 88% to 98% with small natural oscillation
            rssi = int(93 + 4 * math.sin(t * 0.5))
            
            # 3. Altitude: Smooth climb and hover pattern (10m to 65m)
            altitude = 35.0 + 25.0 * math.sin(t * 0.2)
            
            # 4. GPS: Circular flight pattern around base location (radius ~50m)
            lat_offset = (50.0 / 111111.0) * math.cos(t * 0.1)
            lon_offset = (50.0 / (111111.0 * math.cos(math.radians(BASE_LAT)))) * math.sin(t * 0.1)
            latitude = BASE_LAT + lat_offset
            longitude = BASE_LON + lon_offset
            
            # 5. Satellites: 14 to 16 satellites
            satellites = 15 if (int(t) % 10 < 7) else 14
            
            # --- Encode & Transmit Packet ---
            packet = create_telemetry_packet(
                seq=seq,
                bat_v=battery_v,
                rssi=rssi,
                alt_m=altitude,
                lat_deg=latitude,
                lon_deg=longitude,
                sats=satellites
            )
            
            # Send payload via NRF24L01 (No-ACK broadcast)
            radio.write(packet)
            
            # Log output to console
            print(f"[TX #{seq:04d}] BAT: {battery_v:.2f}V | RSSI: {rssi}% | "
                  f"ALT: {altitude:5.1f}m | LAT: {latitude:.6f} | LON: {longitude:.6f} | "
                  f"SATS: {satellites} | ({len(packet)}B)")
            
            seq = (seq + 1) % 256
            time.sleep(SEND_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n[*] Stopping transmission. Telemetry sender halted.")

if __name__ == "__main__":
    main()
