#!/usr/bin/env python3
"""
======================================================================================
Project: Drone Telemetry Grafana Prometheus Exporter
File: pi/grafana_exporter.py

Description:
  High-performance Prometheus metrics exporter running on Raspberry Pi:
  - Ingests all 11 categories of live telemetry from Pixhawk 2.4.8 (TELEM2 @ 115200)
  - Ingests Raspberry Pi SBC health (CPU temp, load, RAM, disk, uptime)
  - Exposes standardized Prometheus /metrics endpoint on port 8000 for PC Grafana
  
  Zero external dependencies - runs on standard Python 3.
======================================================================================
"""

import os
import sys
import time
import argparse
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Add modules path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from modules.sbc_monitor import SBCMonitor
from modules.mavlink_manager import MAVLinkManager

# Global managers
mav_manager = None
sbc_monitor = None

def get_full_telemetry():
    """Merges MAVLink flight telemetry with Raspberry Pi SBC metrics."""
    data = mav_manager.get_telemetry_snapshot() if mav_manager else {}
    data["sbc"] = sbc_monitor.get_metrics_snapshot() if sbc_monitor else {}
    return data

def format_prometheus_metrics(t: dict) -> str:
    """Formats telemetry for Prometheus / Grafana scraping at /metrics."""
    sbc = t.get("sbc", {})
    lines = [
        "# HELP drone_battery_voltage Total battery voltage in Volts",
        "# TYPE drone_battery_voltage gauge",
        f"drone_battery_voltage {t.get('battery_voltage', 0.0)}",
        
        "# HELP drone_battery_current Battery current draw in Amperes",
        "# TYPE drone_battery_current gauge",
        f"drone_battery_current {t.get('battery_current', 0.0)}",
        
        "# HELP drone_battery_remaining Battery remaining percentage (0-100)",
        "# TYPE drone_battery_remaining gauge",
        f"drone_battery_remaining {t.get('battery_remaining', 0)}",
        
        "# HELP drone_cell_delta_mv Difference between maximum and minimum cell in millivolts",
        "# TYPE drone_cell_delta_mv gauge",
        f"drone_cell_delta_mv {t.get('cell_delta_mv', 0)}",

        "# HELP drone_altitude_relative Relative altitude above takeoff in meters (AGL)",
        "# TYPE drone_altitude_relative gauge",
        f"drone_altitude_relative {t.get('altitude_relative', 0.0)}",

        "# HELP drone_altitude_msl Altitude above mean sea level in meters",
        "# TYPE drone_altitude_msl gauge",
        f"drone_altitude_msl {t.get('altitude_msl', 0.0)}",
        
        "# HELP drone_climb_rate Vertical climb speed in m/s",
        "# TYPE drone_climb_rate gauge",
        f"drone_climb_rate {t.get('climb_rate', 0.0)}",
        
        "# HELP drone_latitude GPS Latitude in degrees",
        "# TYPE drone_latitude gauge",
        f"drone_latitude {t.get('latitude', 0.0)}",

        "# HELP drone_longitude GPS Longitude in degrees",
        "# TYPE drone_longitude gauge",
        f"drone_longitude {t.get('longitude', 0.0)}",

        "# HELP drone_satellites Visible GPS satellite count",
        "# TYPE drone_satellites gauge",
        f"drone_satellites {t.get('satellites', 0)}",

        "# HELP drone_hdop GPS Horizontal Dilution of Precision",
        "# TYPE drone_hdop gauge",
        f"drone_hdop {t.get('hdop', 99.9)}",

        "# HELP drone_heading Compass heading in degrees (0-360)",
        "# TYPE drone_heading gauge",
        f"drone_heading {t.get('heading', 0.0)}",
        
        "# HELP drone_rssi_percent RC radio link signal strength percentage (0-100)",
        "# TYPE drone_rssi_percent gauge",
        f"drone_rssi_percent {t.get('rc_rssi', 0)}",
        
        "# HELP drone_armed Vehicle arming state (1=armed, 0=disarmed)",
        "# TYPE drone_armed gauge",
        f"drone_armed {1 if t.get('armed', False) else 0}",

        "# HELP drone_flight_mode Flight mode indicator (1 for active mode)",
        "# TYPE drone_flight_mode gauge",
        f'drone_flight_mode{{mode="{t.get("flight_mode", "UNKNOWN")}"}} 1',
        
        "# HELP drone_gyro_rates_degs 3-Axis Gyroscope angular rate in deg/s",
        "# TYPE drone_gyro_rates_degs gauge",
        f'drone_gyro_rates_degs{{axis="x"}} {t.get("gyro_x", 0.0)}',
        f'drone_gyro_rates_degs{{axis="y"}} {t.get("gyro_y", 0.0)}',
        f'drone_gyro_rates_degs{{axis="z"}} {t.get("gyro_z", 0.0)}',
        
        "# HELP drone_accel_g 3-Axis Accelerometer in g",
        "# TYPE drone_accel_g gauge",
        f'drone_accel_g{{axis="x"}} {t.get("accel_x", 0.0)}',
        f'drone_accel_g{{axis="y"}} {t.get("accel_y", 0.0)}',
        f'drone_accel_g{{axis="z"}} {t.get("accel_z", 1.0)}',
        
        "# HELP drone_attitude_deg Euler angles in degrees",
        "# TYPE drone_attitude_deg gauge",
        f'drone_attitude_deg{{type="roll"}} {t.get("attitude_roll", 0.0)}',
        f'drone_attitude_deg{{type="pitch"}} {t.get("attitude_pitch", 0.0)}',
        f'drone_attitude_deg{{type="yaw"}} {t.get("attitude_yaw", 0.0)}',

        "# HELP drone_attitude_target_deg Target Euler angles in degrees",
        "# TYPE drone_attitude_target_deg gauge",
        f'drone_attitude_target_deg{{type="roll"}} {t.get("target_roll", 0.0)}',
        f'drone_attitude_target_deg{{type="pitch"}} {t.get("target_pitch", 0.0)}',

        "# HELP drone_attitude_error_deg Attitude tracking error in degrees",
        "# TYPE drone_attitude_error_deg gauge",
        f'drone_attitude_error_deg{{type="roll"}} {t.get("error_roll", 0.0)}',
        f'drone_attitude_error_deg{{type="pitch"}} {t.get("error_pitch", 0.0)}',
        
        "# HELP drone_cell_voltage Individual LIPO cell voltage in Volts",
        "# TYPE drone_cell_voltage gauge"
    ]
    
    cells = t.get("cell_voltages", [])
    for idx, cv in enumerate(cells[:6], 1):
        if cv > 0.5:
            lines.append(f'drone_cell_voltage{{cell="{idx}"}} {cv}')
            
    lines.extend([
        "# HELP drone_motor_pwm Motor PWM pulse width in microseconds",
        "# TYPE drone_motor_pwm gauge"
    ])
    for idx, pwm in enumerate(t.get("motor_pwm", [1000, 1000, 1000, 1000]), 1):
        lines.append(f'drone_motor_pwm{{motor="{idx}"}} {pwm}')

    lines.extend([
        "# HELP drone_motor_percent Motor power output percentage (0-100)",
        "# TYPE drone_motor_percent gauge"
    ])
    for idx, pct in enumerate(t.get("motor_percent", [0, 0, 0, 0]), 1):
        lines.append(f'drone_motor_percent{{motor="{idx}"}} {pct}')
        
    lines.extend([
        "# HELP sbc_cpu_temp_celsius Raspberry Pi CPU Temperature in Celsius",
        "# TYPE sbc_cpu_temp_celsius gauge",
        f"sbc_cpu_temp_celsius {sbc.get('cpu_temp_c', 0.0)}",
        
        "# HELP sbc_cpu_load_percent Raspberry Pi CPU utilization percentage",
        "# TYPE sbc_cpu_load_percent gauge",
        f"sbc_cpu_load_percent {sbc.get('cpu_load_percent', 0.0)}",
        
        "# HELP sbc_ram_used_bytes RAM memory consumed in bytes",
        "# TYPE sbc_ram_used_bytes gauge",
        f"sbc_ram_used_bytes {sbc.get('ram_used_mb', 0) * 1024 * 1024}",

        "# HELP sbc_ram_total_bytes Total RAM memory in bytes",
        "# TYPE sbc_ram_total_bytes gauge",
        f"sbc_ram_total_bytes {sbc.get('ram_total_mb', 0) * 1024 * 1024}",

        "# HELP sbc_ram_percent RAM utilization percentage",
        "# TYPE sbc_ram_percent gauge",
        f"sbc_ram_percent {sbc.get('ram_percent', 0.0)}",

        "# HELP sbc_disk_percent Storage disk utilization percentage",
        "# TYPE sbc_disk_percent gauge",
        f"sbc_disk_percent {sbc.get('disk_percent', 0.0)}",

        "# HELP sbc_uptime_seconds Operating system uptime in seconds",
        "# TYPE sbc_uptime_seconds gauge",
        f"sbc_uptime_seconds {sbc.get('uptime_seconds', 0)}"
    ])
    
    return "\n".join(lines) + "\n"

# ======================================================================================
# HTTP REQUEST HANDLER
# ======================================================================================
class MetricsHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Clean silent logs

    def do_GET(self):
        clean_path = self.path.split("?")[0]

        # 1. Prometheus Metrics Endpoint
        if clean_path in ("/metrics", "/"):
            prom_text = format_prometheus_metrics(get_full_telemetry())
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(prom_text.encode("utf-8"))
            return

        # 2. JSON API Endpoint
        if clean_path == "/api/telemetry":
            import json
            payload = json.dumps(get_full_telemetry())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))
            return

        self.send_error(404, "Not Found. Available endpoints: /metrics, /api/telemetry")

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# ======================================================================================
# MAIN ENTRYPOINT
# ======================================================================================
def main():
    global mav_manager, sbc_monitor

    parser = argparse.ArgumentParser(description="Drone Telemetry Grafana Prometheus Exporter")
    parser.add_argument("--port", default="/dev/serial0", help="Pixhawk serial port (default: /dev/serial0 or /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--metrics-port", type=int, default=8000, help="Prometheus Exporter Port (default: 8000)")
    parser.add_argument("--simulate", action="store_true", help="Run simulated telemetry")
    args = parser.parse_args()

    print("=" * 72)
    print("      DRONE TELEMETRY GRAFANA PROMETHEUS EXPORTER (115200 BAUD)      ")
    print("=" * 72)

    # 1. Initialize SBC Monitor
    sbc_monitor = SBCMonitor()
    print("[+] SBC Health Monitor initialized.")

    # 2. Initialize MAVLink Ingestion
    mav_manager = MAVLinkManager(port=args.port, baud=args.baud, simulate=args.simulate)
    mav_manager.start()
    print(f"[+] MAVLink Manager started ({'SIMULATION' if args.simulate else args.port} @ {args.baud} baud).")

    # 3. Start HTTP Metrics Server
    server_address = ("0.0.0.0", args.metrics_port)
    httpd = ThreadedHTTPServer(server_address, MetricsHTTPHandler)
    
    print("\n" + "=" * 72)
    print(f"  📊 Prometheus Exporter URL:  http://0.0.0.0:{args.metrics_port}/metrics")
    print(f"  📡 JSON Snapshot API:        http://0.0.0.0:{args.metrics_port}/api/telemetry")
    print(f"  🎯 Point PC Grafana To:      http://<pi-ip-address>:{args.metrics_port}/metrics")
    print("=" * 72 + "\n")
    print("[+] Exporter is running. Press Ctrl+C to stop.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down exporter...")
        if mav_manager:
            mav_manager.stop()
        httpd.shutdown()
        print("[✓] Exporter stopped cleanly.")

if __name__ == "__main__":
    main()
