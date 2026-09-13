#!/usr/bin/env python3
"""
======================================================================================
Pure Python spidev + GPIO NRF24L01+ Transmitter (Zero C-extension compilation issues)
Compatible with Raspberry Pi 4B (Raspberry Pi OS Bullseye / Bookworm 32-bit & 64-bit)
======================================================================================
"""

import time
import math
import struct
import sys

# 1. Try importing spidev
try:
    import spidev
except ImportError:
    print("[ERROR] 'spidev' is not installed.")
    print("Install it with: sudo apt install python3-spidev -y  OR  pip install spidev")
    sys.exit(1)

# 2. Try importing GPIO backend (gpiozero or RPi.GPIO or gpiod)
ce_pin_controller = None

try:
    from gpiozero import DigitalOutputDevice
    ce_dev = DigitalOutputDevice(22, active_high=True, initial_value=False)
    def set_ce(state: bool):
        if state:
            ce_dev.on()
        else:
            ce_dev.off()
    ce_pin_controller = "gpiozero"
except Exception:
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(22, GPIO.OUT, initial=GPIO.LOW)
        def set_ce(state: bool):
            GPIO.output(22, GPIO.HIGH if state else GPIO.LOW)
        ce_pin_controller = "RPi.GPIO"
    except Exception as e:
        print(f"[!] Warning: Neither gpiozero nor RPi.GPIO available: {e}")
        print("    Install with: sudo apt install python3-gpiozero python3-rpi.gpio -y")
        sys.exit(1)

# ======================================================================================
# NRF24L01 REGISTER DEFINITIONS
# ======================================================================================
R_REGISTER         = 0x00
W_REGISTER         = 0x20
R_RX_PAYLOAD       = 0x61
W_TX_PAYLOAD       = 0xA0
FLUSH_TX           = 0xE1
FLUSH_RX           = 0xE2
NOP                = 0xFF

REG_CONFIG         = 0x00
REG_EN_AA          = 0x01
REG_EN_RXADDR      = 0x02
REG_SETUP_AW       = 0x03
REG_SETUP_RETR     = 0x04
REG_RF_CH          = 0x05
REG_RF_SETUP       = 0x06
REG_STATUS         = 0x07
REG_TX_ADDR        = 0x10
REG_RX_ADDR_P0     = 0x0A
REG_FEATURE        = 0x1D
REG_DYNPD          = 0x1C

PACKET_MAGIC = 0xAA
RF_CHANNEL = 90
TX_ADDRESS = b"2Node"  # Matches ESP32 listening pipe ("2Node")
BASE_LAT = 12.971598
BASE_LON = 77.594562

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
        
        # Test SPI communication by reading SETUP_AW
        aw = self.read_reg(REG_SETUP_AW)
        print(f"[*] SPI Communication Test: SETUP_AW = 0x{aw:02X}")
        
        if aw not in (0x01, 0x02, 0x03):
            print("[!] WARNING: SPI read returned unexpected value (0x00 or 0xFF).")
            return False

        # Reset & flush FIFOs
        self.spi.xfer2([FLUSH_TX])
        self.spi.xfer2([FLUSH_RX])
        self.write_reg(REG_STATUS, 0x70)

        # 1. 5-byte address width
        self.write_reg(REG_SETUP_AW, 0x03)
        # 2. Disable Auto-ACK (Broadcast mode)
        self.write_reg(REG_EN_AA, 0x00)
        # 3. Disable Retransmits
        self.write_reg(REG_SETUP_RETR, 0x00)
        # 4. Set Channel (90 = 2.490 GHz)
        self.write_reg(REG_RF_CH, RF_CHANNEL)
        # 5. Set 250 kbps Data Rate + Maximum Power (PA_MAX)
        self.write_reg(REG_RF_SETUP, 0x26)
        # 6. Set Dynamic Payloads
        self.write_reg(REG_FEATURE, 0x04) # EN_DPL = 1
        self.write_reg(REG_DYNPD, 0x01)   # Enable DPL on Pipe 0
        # 7. Set TX Address & Pipe 0 Address
        self.write_reg(REG_TX_ADDR, TX_ADDRESS)
        self.write_reg(REG_RX_ADDR_P0, TX_ADDRESS)
        # 8. Enable CRC (16-bit) and Power Up in TX mode
        self.write_reg(REG_CONFIG, 0x0E)
        
        time.sleep(0.01) # Power-up delay
        return True

    def transmit_packet(self, payload: bytes) -> bool:
        # Flush TX FIFO
        self.spi.xfer2([FLUSH_TX])
        self.write_reg(REG_STATUS, 0x70)
        
        # Load TX Payload (32-byte standard buffer padded with zeros)
        full_payload = payload + bytes(32 - len(payload)) if len(payload) < 32 else payload[:32]
        self.spi.xfer2([W_TX_PAYLOAD] + list(full_payload))
        
        # Pulse CE high for 20 microseconds to trigger TX burst
        set_ce(True)
        time.sleep(0.00002) # 20 us pulse
        set_ce(False)
        
        # Wait for transmission to complete (~1.2ms for 32 bytes at 250kbps)
        time.sleep(0.002)
        
        status = self.read_reg(REG_STATUS)
        tx_ok = (status & 0x20) != 0 # TX_DS flag
        self.write_reg(REG_STATUS, 0x70) # Clear flags
        return tx_ok

# ======================================================================================
# PACKET ENCODER
# ======================================================================================
def create_telemetry_packet(seq: int, bat_v: float, rssi: int, alt_m: float, 
                            lat_deg: float, lon_deg: float, sats: int) -> bytes:
    bat_mv = int(max(0.0, bat_v) * 1000)
    alt_cm = int(alt_m * 100)
    lat_e7 = int(lat_deg * 10000000)
    lon_e7 = int(lon_deg * 10000000)
    
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
    
    checksum = 0
    for byte in payload_raw:
        checksum ^= byte
        
    return payload_raw + bytes([checksum])

# ======================================================================================
# MAIN LOOP
# ======================================================================================
def main():
    print("=" * 65)
    print("  Raspberry Pi 4B - Pure spidev NRF24L01+ Transmitter  ")
    print(f"  Using CE Pin Backend: {ce_pin_controller} (GPIO 22 / Pin 15)")
    print("=" * 65)
    
    nrf = SimpleNRF24(bus=0, device=0, speed=2000000)
    
    if not nrf.init_radio():
        print("\n[!] Radio initialization check failed.")
        sys.exit(1)
        
    print(f"[+] NRF24L01+ configured on Channel {RF_CHANNEL} (250 KBPS, PA_MAX)!")
    print(f"[+] Target address: {TX_ADDRESS.decode()} (matches ESP32 receiver)")
    print("[+] Broadcasting simulated telemetry stream at 5 Hz. Press Ctrl+C to exit.\n")
    
    seq = 0
    t_start = time.time()
    
    try:
        while True:
            t = time.time() - t_start
            
            # Simulated Telemetry Data
            battery_v = max(10.5, 12.58 - (t * 0.005))
            rssi = int(93 + 4 * math.sin(t * 0.5))
            altitude = 35.0 + 25.0 * math.sin(t * 0.2)
            
            lat_offset = (50.0 / 111111.0) * math.cos(t * 0.1)
            lon_offset = (50.0 / (111111.0 * math.cos(math.radians(BASE_LAT)))) * math.sin(t * 0.1)
            latitude = BASE_LAT + lat_offset
            longitude = BASE_LON + lon_offset
            
            satellites = 15 if (int(t) % 10 < 7) else 14
            
            packet = create_telemetry_packet(
                seq=seq,
                bat_v=battery_v,
                rssi=rssi,
                alt_m=altitude,
                lat_deg=latitude,
                lon_deg=longitude,
                sats=satellites
            )
            
            # Transmit & check TX_DS status
            tx_sent = nrf.transmit_packet(packet)
            status_indicator = "✓ TX OK" if tx_sent else "~ SENT"
            
            print(f"[TX #{seq:04d} | {status_indicator}] BAT: {battery_v:.2f}V | RSSI: {rssi}% | "
                  f"ALT: {altitude:5.1f}m | LAT: {latitude:.6f} | LON: {longitude:.6f} | "
                  f"SATS: {satellites}")
            
            seq = (seq + 1) % 256
            time.sleep(0.2) # 5 Hz
            
    except KeyboardInterrupt:
        print("\n[*] Transmitter stopped.")

if __name__ == "__main__":
    main()
