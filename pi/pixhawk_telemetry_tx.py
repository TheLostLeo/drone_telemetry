#!/usr/bin/env python3
"""
======================================================================================
Project: Drone Telemetry Transmitter - Live Pixhawk MAVLink (Raspberry Pi 4B)
File: pi/pixhawk_telemetry_tx.py

Description:
  Reads live flight telemetry from Pixhawk via MAVLink at 115200 baud (USB or UART),
  packs the data into an optimized 20-byte struct with XOR checksum, and broadcasts
  it over NRF24L01+ to the ESP32 ground receiver.

Hardware Connections:
  1. NRF24L01+ Transceiver (via HW-200 Base):
     - VCC  -> Pin 2 (5V Power)
     - GND  -> Pin 20 or Pin 25 (GND)
     - CE   -> Pin 15 (GPIO 22)
     - CSN  -> Pin 24 (GPIO 8 / SPI0 CE0)
     - SCK  -> Pin 23 (GPIO 11 / SPI0 SCLK)
     - MOSI -> Pin 19 (GPIO 10 / SPI0 MOSI)
     - MISO -> Pin 21 (GPIO 9  / SPI0 MISO)

  2. Pixhawk Flight Controller:
     - Option A (USB): Standard Micro-USB / USB-C to Pi USB Port (/dev/ttyACM0)
     - Option B (UART TELEM2):
       * Pixhawk TX (Pin 2) -> Pi Pin 10 (GPIO 15 / RXD)
       * Pixhawk RX (Pin 3) -> Pi Pin 8  (GPIO 14 / TXD)
       * Pixhawk GND (Pin 6) -> Pi Pin 9  (Ground)

Baud Rate: 115200
======================================================================================
"""

import sys
import time
import struct
import argparse

# 1. SPI & GPIO Imports
try:
    import spidev
except ImportError:
    print("[ERROR] 'spidev' is not installed. Run: sudo apt install python3-spidev -y")
    sys.exit(1)

try:
    from gpiozero import DigitalOutputDevice
    ce_dev = DigitalOutputDevice(22, active_high=True, initial_value=False)
    def set_ce(state: bool):
        if state:
            ce_dev.on()
        else:
            ce_dev.off()
except Exception:
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(22, GPIO.OUT, initial=GPIO.LOW)
        def set_ce(state: bool):
            GPIO.output(22, GPIO.HIGH if state else GPIO.LOW)
    except Exception as e:
        print(f"[ERROR] GPIO library error: {e}")
        sys.exit(1)

# 2. MAVLink Import
try:
    from pymavlink import mavutil
except ImportError:
    print("[ERROR] 'pymavlink' is not installed. Run: pip install pymavlink")
    sys.exit(1)

# ======================================================================================
# NRF24L01 REGISTER DEFINITIONS
# ======================================================================================
R_REGISTER         = 0x00
W_REGISTER         = 0x20
W_TX_PAYLOAD       = 0xA0
FLUSH_TX           = 0xE1
FLUSH_RX           = 0xE2

REG_CONFIG         = 0x00
REG_EN_AA          = 0x01
REG_SETUP_AW       = 0x03
REG_SETUP_RETR     = 0x04
REG_RF_CH          = 0x05
REG_RF_SETUP       = 0x06
REG_STATUS         = 0x07
REG_TX_ADDR        = 0x10
REG_RX_ADDR_P0     = 0x0A
REG_FEATURE        = 0x1D
REG_DYNPD          = 0x1C

PACKET_MAGIC       = 0xAA
RF_CHANNEL         = 90
TX_ADDRESS         = b"2Node"  # Matches ESP32 receiver

class SimpleNRF24:
    def __init__(self, bus=0, device=0, speed=2000000):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = speed
        self.spi.mode = 0

    def read_reg(self, reg):
        resp = self.spi.xfer2([R_REGISTER | (reg & 0x1F), 0x00])
        return resp[1]

    def write_reg(self, reg, val):
        if isinstance(val, (bytes, bytearray, list)):
            self.spi.xfer2([W_REGISTER | (reg & 0x1F)] + list(val))
        else:
            self.spi.xfer2([W_REGISTER | (reg & 0x1F), val])

    def init_radio(self):
        set_ce(False)
        time.sleep(0.05)
        
        aw = self.read_reg(REG_SETUP_AW)
        if aw not in (0x01, 0x02, 0x03):
            print(f"[!] Warning: SPI test returned 0x{aw:02X}. Check radio wiring.")
            return False

        # Reset FIFOs and flags
        self.spi.xfer2([FLUSH_TX])
        self.spi.xfer2([FLUSH_RX])
        self.write_reg(REG_STATUS, 0x70)

        # Configure NRF24
        self.write_reg(REG_SETUP_AW, 0x03)       # 5-byte address width
        self.write_reg(REG_EN_AA, 0x00)          # No Auto-ACK (broadcast)
        self.write_reg(REG_SETUP_RETR, 0x00)     # No retries
        self.write_reg(REG_RF_CH, RF_CHANNEL)    # Channel 90
        self.write_reg(REG_RF_SETUP, 0x26)       # 250 kbps, PA_MAX
        self.write_reg(REG_FEATURE, 0x04)        # Enable Dynamic Payload
        self.write_reg(REG_DYNPD, 0x01)          # Pipe 0 DPL
        self.write_reg(REG_TX_ADDR, TX_ADDRESS)
        self.write_reg(REG_RX_ADDR_P0, TX_ADDRESS)
        self.write_reg(REG_CONFIG, 0x0E)         # PWR_UP=1, CRC=16bit, TX mode
        
        time.sleep(0.01)
        return True

    def transmit_packet(self, payload: bytes) -> bool:
        self.spi.xfer2([FLUSH_TX])
        self.write_reg(REG_STATUS, 0x70)
        
        full_payload = payload + bytes(32 - len(payload)) if len(payload) < 32 else payload[:32]
        self.spi.xfer2([W_TX_PAYLOAD] + list(full_payload))
        
        # Pulse CE high for TX burst
        set_ce(True)
        time.sleep(0.00002) # 20 us
        set_ce(False)
        
        time.sleep(0.002)
        status = self.read_reg(REG_STATUS)
        tx_ok = (status & 0x20) != 0
        self.write_reg(REG_STATUS, 0x70)
        return tx_ok

# ======================================================================================
# 20-BYTE STRUCT PACKER
# ======================================================================================
def pack_telemetry(seq: int, bat_mv: int, rssi: int, alt_cm: int, 
                   lat_e7: int, lon_e7: int, sats: int) -> bytes:
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
    parser = argparse.ArgumentParser(description="Pixhawk MAVLink to NRF24 Telemetry Transmitter (115200 Baud)")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0 for USB, or /dev/serial0 for UART)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--rate", type=float, default=5.0, help="Transmission rate in Hz (default: 5.0 Hz)")
    args = parser.parse_args()

    print("=" * 68)
    print("   Raspberry Pi 4B - Pixhawk MAVLink Telemetry Bridge (115200 Baud)   ")
    print("=" * 68)

    # 1. Initialize NRF24 Radio
    nrf = SimpleNRF24(bus=0, device=0, speed=2000000)
    if not nrf.init_radio():
        print("[!] Radio initialization failed. Check wiring and SPI.")
        sys.exit(1)
    print(f"[+] NRF24L01+ initialized on Channel {RF_CHANNEL} (250 KBPS, PA_MAX).")

    # 2. Connect to Pixhawk MAVLink at 115200 Baud
    print(f"[*] Connecting to Pixhawk on '{args.port}' at {args.baud} baud...")
    mav = None
    
    # Auto-fallback search if port doesn't exist
    ports_to_try = [args.port, "/dev/ttyACM0", "/dev/ttyUSB0", "/dev/serial0"]
    for p in ports_to_try:
        try:
            mav = mavutil.mavlink_connection(p, baud=args.baud)
            print(f"[+] Opened serial port: {p}")
            break
        except Exception:
            continue
            
    if not mav:
        print(f"[!] ERROR: Could not open serial port {args.port}. Check USB connection.")
        sys.exit(1)

    print("[*] Waiting for MAVLink Heartbeat from Pixhawk...")
    try:
        mav.wait_heartbeat(timeout=8)
        print(f"[✓] Heartbeat received! (System: {mav.target_system}, Component: {mav.target_component})")
    except Exception:
        print("[!] Note: Heartbeat not detected yet. Continuing with live message polling...")

    # Request MAVLink telemetry data streams at desired rate
    try:
        mav.mav.request_data_stream_send(
            mav.target_system, mav.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL, int(args.rate), 1
        )
    except Exception:
        pass

    # Telemetry State Variables
    cur_bat_mv = 0
    cur_rssi = 0
    cur_alt_cm = 0
    cur_lat_e7 = 0
    cur_lon_e7 = 0
    cur_sats = 0
    seq = 0

    send_interval = 1.0 / args.rate
    last_send_time = 0

    print(f"[+] Streaming live telemetry over NRF24 at {args.rate} Hz. Press Ctrl+C to stop.\n")

    try:
        while True:
            # Drain and decode incoming MAVLink packets
            while True:
                msg = mav.recv_match(blocking=False)
                if not msg:
                    break
                
                msg_type = msg.get_type()
                
                # 1. Battery Voltage
                if msg_type == 'SYS_STATUS':
                    if msg.voltage_battery > 0:
                        cur_bat_mv = msg.voltage_battery
                elif msg_type == 'BATTERY_STATUS':
                    if len(msg.voltages) > 0 and msg.voltages[0] not in (0, 65535):
                        cur_bat_mv = msg.voltages[0]
                
                # 2. RC / FlySky RSSI
                elif msg_type == 'RC_CHANNELS':
                    if msg.rssi > 0:
                        cur_rssi = int((msg.rssi / 255.0) * 100)
                
                # 3. GPS Position & Relative Altitude
                elif msg_type == 'GLOBAL_POSITION_INT':
                    cur_lat_e7 = msg.lat
                    cur_lon_e7 = msg.lon
                    cur_alt_cm = int(msg.relative_alt / 10) # mm -> cm
                
                # 4. GPS Fix & Satellite Count
                elif msg_type == 'GPS_RAW_INT':
                    cur_sats = msg.satellites_visible

            # Periodic Broadcast Loop
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

                tx_ok = nrf.transmit_packet(packet)
                status_txt = "✓ TX OK" if tx_ok else "~ SENT"

                # Formatted engineering units
                bat_v = cur_bat_mv / 1000.0
                alt_m = cur_alt_cm / 100.0
                lat_deg = cur_lat_e7 / 1e7
                lon_deg = cur_lon_e7 / 1e7

                print(f"[TX #{seq:04d} | {status_txt}] BAT: {bat_v:5.2f}V | RSSI: {cur_rssi:3d}% | "
                      f"ALT: {alt_m:5.1f}m | LAT: {lat_deg:10.6f} | LON: {lon_deg:10.6f} | SATS: {cur_sats:2d}")

                seq = (seq + 1) % 256

            time.sleep(0.005) # Yield CPU

    except KeyboardInterrupt:
        print("\n[*] Telemetry broadcast stopped.")

if __name__ == "__main__":
    main()
