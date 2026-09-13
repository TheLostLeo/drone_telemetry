#!/usr/bin/env python3
"""
Diagnostic tool to test NRF24L01+ hardware connection on Raspberry Pi.
"""
import sys
import time

try:
    from pyrf24 import RF24, RF24_PA_MAX, RF24_250KBPS, RF24_CRC_16
except ImportError:
    print("[ERROR] pyrf24 not installed. Run: pip install pyrf24")
    sys.exit(1)

print("=" * 60)
print("  NRF24L01+ Hardware Diagnostic (Raspberry Pi 4B)  ")
print("=" * 60)

# Try default SPI0 CE0 (Pin 24) with CE on GPIO 22 (Pin 15)
# In pyrf24: RF24(ce_pin, csn_pin, spi_speed)
# csn_pin = 0 corresponds to /dev/spidev0.0
# csn_pin = 1 corresponds to /dev/spidev0.1

for ce in [22, 25]:
    for csn in [0, 1]:
        print(f"\n[*] Testing configuration: CE=GPIO{ce}, CSN=/dev/spidev0.{csn}...")
        try:
            radio = RF24(ce, csn)
            if radio.begin():
                print(f"[SUCCESS] NRF24L01 initialized with CE={ce}, CSN={csn}!")
                print("[*] Checking if chip is responding to SPI register reads:")
                if radio.is_chip_connected():
                    print("[✓] CHIP IS CONNECTED AND HEALTHY!")
                    radio.print_pretty_details()
                    sys.exit(0)
                else:
                    print("[!] radio.begin() passed, but is_chip_connected() returned FALSE.")
                    print("    This usually means MISO (Pin 21) or MOSI (Pin 19) is loose or unseated.")
            else:
                print(f"[-] radio.begin() returned False for CE={ce}, CSN={csn}")
        except Exception as e:
            print(f"[-] Exception during init: {e}")

print("\n" + "=" * 60)
print("Troubleshooting Checklist:")
print("1. HW-200 Power LED: Is the LED on the black adapter base ON?")
print("2. Wiring Verification:")
print("   - VCC  -> Pin 2 (5V)")
print("   - GND  -> Pin 20 or Pin 25")
print("   - CE   -> Pin 15 (GPIO 22)")
print("   - CSN  -> Pin 24 (GPIO 8 / CE0)")
print("   - SCK  -> Pin 23 (GPIO 11 / SCLK)")
print("   - MOSI -> Pin 19 (GPIO 10 / MOSI)")
print("   - MISO -> Pin 21 (GPIO 9 / MISO)")
print("3. Ensure the 8-pin NRF24 module is pushed FIRMLY all the way into the HW-200 socket.")
print("4. Permissions: Try running with sudo: 'sudo $(which python3) simulate_telemetry_tx.py'")
print("=" * 60)
