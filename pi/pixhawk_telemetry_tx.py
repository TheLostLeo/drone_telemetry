#!/usr/bin/env python3
"""
======================================================================================
Project: Drone Telemetry Transmitter - Live Pixhawk MAVLink (Raspberry Pi 4B)
File: pi/pixhawk_telemetry_tx.py

Description:
  Connects to a Pixhawk Flight Controller over MAVLink (USB or UART), parses live
  flight data (Battery, RSSI, Altitude, GPS Coordinates, Satellites), packs the data
  into an optimized 20-byte struct, and broadcasts it over NRF24L01+ to the ESP32
  ground receiver.

Dependencies:
  pip3 install pyrf24 pymavlink pyserial
======================================================================================
"""

import sys
import time
import struct
import argparse
from typing import Optional

try:
    from pyrf24 import RF24, RF24_PA_MAX, RF24_250KBPS, RF24_CRC_16
except ImportError:
    print("[ERROR] 'pyrf24' library is not installed. Install with: pip3 install pyrf24")
    sys.exit(1)

try:
    from pymavlink import mavutil
except ImportError:
    print("[ERROR] 'pymavlink' library is not installed. Install with: pip3 install pymavlink")
    sys.exit(1)

# ======================================================================================
# CONFIGURATION
# ======================================================================================
CE_PIN = 22       # GPIO 22 (Pin 15)
CSN_PIN = 0       # SPI0 CE0 (Pin 24 / GPIO 8)

RF_CHANNEL = 90   # 2.490 GHz (Matches ESP32 Channel 90)
PIPE_ADDRESS = b"2Node"

PACKET_MAGIC = 0xAA
DEFAULT_MAVLINK_PORT = "/dev/ttyACM0"  # USB Serial (or "/dev/serial0" for UART)
DEFAULT_BAUDRATE = 115200

# ======================================================================================
# TELEMETRY PACKET ENCODER
# ======================================================================================
def pack_telemetry(seq: int, bat_mv: int, rssi: int, alt_cm: int, 
                   lat_e7: int, lon_e7: int, sats: int) -> bytes:
    """
    Directly packs native MAVLink integers into the 20-byte struct without float drift:
      <BBHhiiiBB
    """
    bat_mv_clamped = max(0, min(65535, bat_mv))
    rssi_clamped = max(-32768, min(32767, rssi))
    sats_clamped = max(0, min(255, sats))
    
    payload = struct.pack(
        "<BBHhiiiB",
        PACKET_MAGIC,
        seq % 256,
        bat_mv_clamped,
        rssi_clamped,
        alt_cm,
        lat_e7,
        lon_e7,
        sats_clamped
    )
    
    # 8-bit XOR Checksum
    checksum = 0
    for byte in payload:
        checksum ^= byte
        
    return payload + bytes([checksum])

# ======================================================================================
# MAIN EXECUTION
# ======================================================================================
def main():
    parser = argparse.ArgumentParser(description="Pixhawk MAVLink to NRF24 Telemetry Transmitter")
    parser.add_argument("--port", default=DEFAULT_MAVLINK_PORT, help="MAVLink serial port (e.g. /dev/ttyACM0, /dev/serial0)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUDRATE, help="Baud rate (default: 115200 for USB, 57600 for UART)")
    parser.add_argument("--rate", type=float, default=5.0, help="Transmission rate in Hz (default: 5 Hz)")
    args = parser.parse_args()

    print("=" * 65)
    print("  Raspberry Pi 4B - Pixhawk MAVLink -> NRF24 Telemetry Bridge  ")
    print("=" * 65)

    # 1. Initialize NRF24L01 Radio
    print(f"[*] Initializing NRF24L01 on SPI0 (CE=GPIO {CE_PIN}, CSN=SPI0_CE0)...")
    radio = RF24(CE_PIN, CSN_PIN)
    if not radio.begin():
        print("[!] FATAL: NRF24L01 not detected. Ensure SPI is enabled and check connections.")
        sys.exit(1)

    radio.setChannel(RF_CHANNEL)
    radio.setDataRate(RF24_250KBPS)
    radio.setPALevel(RF24_PA_MAX)
    radio.setCRCLength(RF24_CRC_16)
    radio.setAutoAck(False)
    radio.openWritingPipe(PIPE_ADDRESS)
    radio.stopListening()
    print(f"[+] Radio configured on Channel {RF_CHANNEL} (250 KBPS, PA_MAX).")

    # 2. Connect to Pixhawk MAVLink
    print(f"[*] Connecting to Pixhawk on {args.port} at {args.baud} baud...")
    try:
        mav = mavutil.mavlink_connection(args.port, baud=args.baud)
        mav.wait_heartbeat(timeout=10)
        print(f"[+] MAVLink Heartbeat detected! (System ID: {mav.target_system}, Component ID: {mav.target_component})")
    except Exception as e:
        print(f"[!] Warning: Could not detect MAVLink heartbeat: {e}")
        print("    Continuing with live polling...")

    # Shared telemetry states
    cur_bat_mv = 0
    cur_rssi = 0
    cur_alt_cm = 0
    cur_lat_e7 = 0
    cur_lon_e7 = 0
    cur_sats = 0
    seq = 0

    send_interval = 1.0 / args.rate
    last_send_time = 0

    print(f"[+] Telemetry streaming active at {args.rate} Hz. Press Ctrl+C to exit.\n")

    try:
        while True:
            # Non-blocking MAVLink message reading
            msg = mav.recv_match(blocking=False)
            if msg:
                msg_type = msg.get_type()
                
                # 1. Battery Status & Voltage
                if msg_type == 'SYS_STATUS':
                    cur_bat_mv = msg.voltage_battery  # in mV
                elif msg_type == 'BATTERY_STATUS':
                    if len(msg.voltages) > 0 and msg.voltages[0] != 65535:
                        cur_bat_mv = msg.voltages[0]
                
                # 2. FlySky / RC RSSI
                elif msg_type == 'RC_CHANNELS':
                    # Scale RSSI (0-255) to percentage (0-100%) if > 0
                    if msg.rssi > 0:
                        cur_rssi = int((msg.rssi / 255.0) * 100)
                    else:
                        cur_rssi = 0
                
                # 3. GPS Coordinates & Relative Altitude
                elif msg_type == 'GLOBAL_POSITION_INT':
                    cur_lat_e7 = msg.lat
                    cur_lon_e7 = msg.lon
                    # relative_alt is in millimeters, convert to cm
                    cur_alt_cm = int(msg.relative_alt / 10)
                
                # 4. GPS Fix & Satellites Visible
                elif msg_type == 'GPS_RAW_INT':
                    cur_sats = msg.satellites_visible

            # Timed Telemetry Broadcast
            now = time.time()
            if now - last_send_time >= send_interval:
                last_send_time = now

                packet = pack_telemetry(
                    seq=seq,
                    bat_mv=cur_bat_mv,
                    rssi=cur_rssi,
                    alt_cm=cur_alt_cm,
                    lat_e7=cur_lat_e7,
                    lon_e7=cur_lon_e7,
                    sats=cur_sats
                )

                radio.write(packet)

                # Pretty print metrics
                bat_v = cur_bat_mv / 1000.0
                alt_m = cur_alt_cm / 100.0
                lat_deg = cur_lat_e7 / 1e7
                lon_deg = cur_lon_e7 / 1e7

                print(f"[TX #{seq:04d}] BAT: {bat_v:5.2f}V | RSSI: {cur_rssi:3d}% | "
                      f"ALT: {alt_m:5.1f}m | LAT: {lat_deg:10.6f} | LON: {lon_deg:10.6f} | SATS: {cur_sats:2d}")

                seq = (seq + 1) % 256

            time.sleep(0.005)  # Small yield to prevent CPU starvation

    except KeyboardInterrupt:
        print("\n[*] Telemetry broadcast stopped.")

if __name__ == "__main__":
    main()
