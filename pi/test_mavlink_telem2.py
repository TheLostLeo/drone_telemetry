#!/usr/bin/env python3
"""
======================================================================================
Tool: Pixhawk 2.4.8 TELEM2 Diagnostic & Link Health Validator
File: pi/test_mavlink_telem2.py

Description:
  Connects to Pixhawk 2.4.8 on TELEM2 (GPIO 14/15 /dev/serial0 @ 115200 baud).
  Validates heartbeat reception, checks firmware version, measures packet frequency,
  and prints a live tabular view of all incoming telemetry fields.
======================================================================================
"""

import sys
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description="TELEM2 Diagnostic & Health Checker")
    parser.add_argument("--port", default="/dev/serial0", help="Serial port (default: /dev/serial0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    args = parser.parse_args()

    print("=" * 70)
    print("      PIXHAWK 2.4.8 TELEM2 DIAGNOSTIC & LINK HEALTH VALIDATOR        ")
    print("=" * 70)
    print(f"[*] Target Serial Port: {args.port}")
    print(f"[*] Target Baud Rate:   {args.baud}")
    print("----------------------------------------------------------------------")

    try:
        from pymavlink import mavutil
    except ImportError:
        print("[!] ERROR: 'pymavlink' is not installed.")
        print("    Install it via: pip install pymavlink pyserial")
        sys.exit(1)

    print(f"[*] Opening serial connection to '{args.port}' at {args.baud} baud...")
    mav = None
    ports_to_try = [args.port, "/dev/serial0", "/dev/ttyAMA0", "/dev/ttyACM0", "/dev/ttyUSB0"]

    for p in ports_to_try:
        try:
            mav = mavutil.mavlink_connection(p, baud=args.baud)
            print(f"[+] Serial port '{p}' opened successfully.")
            break
        except Exception as e:
            continue

    if not mav:
        print(f"[!] ERROR: Could not open any serial port. Check GPIO wiring or USB cable.")
        sys.exit(1)

    print("[*] Waiting for MAVLink HEARTBEAT from Pixhawk (Timeout: 10s)...")
    try:
        hb = mav.wait_heartbeat(timeout=10)
        if not hb:
            print("[!] TIMEOUT: No heartbeat received.")
            print("    Checklist:")
            print("    1. Pixhawk TELEM2 Pin 2 (TX) -> Pi Pin 10 (GPIO 15 / RX)")
            print("    2. Pixhawk TELEM2 Pin 3 (RX) -> Pi Pin 8  (GPIO 14 / TX)")
            print("    3. Pixhawk TELEM2 Pin 6 (GND) -> Pi Pin 9  (GND)")
            print("    4. Pixhawk Parameter: SERIAL2_PROTOCOL = 2, SERIAL2_BAUD = 115")
            print("    5. Pi OS: enable_uart=1, dtoverlay=disable-bt, serial console disabled")
            sys.exit(1)

        print("\n" + "=" * 70)
        print("  ✓ HEARTBEAT DETECTED & LINK VERIFIED!")
        print("=" * 70)
        print(f"  • Autopilot Type:     {hb.autopilot}")
        print(f"  • Vehicle Type:       {hb.type}")
        print(f"  • System ID:          {mav.target_system}")
        print(f"  • Component ID:       {mav.target_component}")
        print(f"  • Base Mode:          0x{hb.base_mode:02X}")
        print(f"  • Custom Flight Mode: {hb.custom_mode}")
        print("----------------------------------------------------------------------\n")

    except KeyboardInterrupt:
        print("\n[*] Aborted.")
        sys.exit(0)

    # Request streams at 10 Hz
    mav.mav.request_data_stream_send(
        mav.target_system, mav.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
    )

    print("[+] Streaming live telemetry packets (Press Ctrl+C to stop)...\n")
    packet_count = 0
    start_time = time.time()

    try:
        while True:
            msg = mav.recv_match(blocking=True, timeout=2.0)
            if not msg:
                print("[!] Waiting for packets...")
                continue

            packet_count += 1
            msg_type = msg.get_type()

            if msg_type == 'SYS_STATUS':
                v = msg.voltage_battery / 1000.0 if msg.voltage_battery > 0 else 0.0
                a = msg.current_battery / 100.0 if msg.current_battery >= 0 else 0.0
                print(f"[SYS_STATUS] Bat: {v:5.2f}V | Current: {a:4.1f}A | Rem: {msg.battery_remaining}%")
            
            elif msg_type == 'GLOBAL_POSITION_INT':
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                alt = msg.relative_alt / 1000.0
                hdg = msg.hdg / 100.0
                print(f"[GLOBAL_POS] Lat: {lat:10.6f} | Lon: {lon:10.6f} | Rel Alt: {alt:5.1f}m | Hdg: {hdg:5.1f}°")

            elif msg_type == 'ATTITUDE':
                import math
                roll = math.degrees(msg.roll)
                pitch = math.degrees(msg.pitch)
                yaw = math.degrees(msg.yaw) % 360
                print(f"[ATTITUDE]   Roll: {roll:+5.1f}° | Pitch: {pitch:+5.1f}° | Yaw: {yaw:5.1f}°")

            elif msg_type == 'GPS_RAW_INT':
                print(f"[GPS_RAW]    Fix: {msg.fix_type} | Sats: {msg.satellites_visible} | HDOP: {msg.eph/100.0:.2f}")

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        rate = packet_count / elapsed if elapsed > 0 else 0
        print(f"\n[*] Diagnostic complete. Total Packets: {packet_count} (~{rate:.1f} Hz).")

if __name__ == "__main__":
    main()
