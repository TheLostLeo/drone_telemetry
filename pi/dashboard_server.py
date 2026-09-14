#!/usr/bin/env python3
"""
======================================================================================
Project: Drone Telemetry Web Dashboard & Grafana Telemetry Server
File: pi/dashboard_server.py

Description:
  High-performance telemetry hub running on the Raspberry Pi:
  - Ingests 11 categories of live telemetry from Pixhawk 2.4.8 (TELEM2 @ 115200 baud)
  - Ingests SBC health (CPU temp, RAM, load) via sbc_monitor.py
  - Serves real-time WebSocket stream (/ws/telemetry) at 10 Hz
  - Serves REST API (/api/telemetry)
  - Serves Prometheus/Grafana metrics endpoint (/metrics)
  - Serves the interactive aerospace Mission Control Web UI (HTML/CSS/JS)
  
  Zero mandatory external dependencies - runs on standard Python 3.
======================================================================================
"""

import os
import sys
import time
import json
import base64
import hashlib
import struct
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
connected_websockets = []
ws_lock = threading.Lock()

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
        
        "# HELP drone_battery_remaining Battery remaining percentage",
        "# TYPE drone_battery_remaining gauge",
        f"drone_battery_remaining {t.get('battery_remaining', 0)}",
        
        "# HELP drone_altitude_relative Relative altitude above takeoff in meters",
        "# TYPE drone_altitude_relative gauge",
        f"drone_altitude_relative {t.get('altitude_relative', 0.0)}",
        
        "# HELP drone_climb_rate Vertical climb speed in m/s",
        "# TYPE drone_climb_rate gauge",
        f"drone_climb_rate {t.get('climb_rate', 0.0)}",
        
        "# HELP drone_heading Compass heading in degrees (0-360)",
        "# TYPE drone_heading gauge",
        f"drone_heading {t.get('heading', 0.0)}",
        
        "# HELP drone_rssi_percent RC radio link signal strength percentage",
        "# TYPE drone_rssi_percent gauge",
        f"drone_rssi_percent {t.get('rc_rssi', 0)}",
        
        "# HELP drone_armed Vehicle arming state (1=armed, 0=disarmed)",
        "# TYPE drone_armed gauge",
        f"drone_armed {1 if t.get('armed', False) else 0}",
        
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
        "# HELP sbc_cpu_temp_celsius Raspberry Pi CPU Temperature in Celsius",
        "# TYPE sbc_cpu_temp_celsius gauge",
        f"sbc_cpu_temp_celsius {sbc.get('cpu_temp_c', 0.0)}",
        
        "# HELP sbc_cpu_load_percent Raspberry Pi CPU utilization percentage",
        "# TYPE sbc_cpu_load_percent gauge",
        f"sbc_cpu_load_percent {sbc.get('cpu_load_percent', 0.0)}",
        
        "# HELP sbc_ram_used_bytes RAM memory consumed in bytes",
        "# TYPE sbc_ram_used_bytes gauge",
        f"sbc_ram_used_bytes {sbc.get('ram_used_mb', 0) * 1024 * 1024}"
    ])
    
    return "\n".join(lines) + "\n"

# ======================================================================================
# RFC 6455 WEBSOCKET FRAME ENCODING
# ======================================================================================
def encode_ws_frame(message: str) -> bytes:
    """Encodes a text string into an unmasked RFC 6455 WebSocket frame."""
    data = message.encode('utf-8')
    length = len(data)
    frame = bytearray([0x81]) # Final frame | Text opcode

    if length <= 125:
        frame.append(length)
    elif length <= 65535:
        frame.append(126)
        frame.extend(struct.pack("!H", length))
    else:
        frame.append(127)
        frame.extend(struct.pack("!Q", length))

    frame.extend(data)
    return bytes(frame)

# ======================================================================================
# HTTP & WEBSOCKET REQUEST HANDLER
# ======================================================================================
class TelemetryHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress verbose HTTP logging
        pass

    def do_GET(self):
        # 1. WebSocket Upgrade Handshake
        if self.headers.get("Upgrade", "").lower() == "websocket":
            self.handle_websocket()
            return

        # 2. REST API /api/telemetry
        if self.path == "/api/telemetry":
            payload = json.dumps(get_full_telemetry())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload.encode("utf-8"))
            return

        # 3. Prometheus / Grafana Metrics /metrics
        if self.path == "/metrics":
            prom_text = format_prometheus_metrics(get_full_telemetry())
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.end_headers()
            self.wfile.write(prom_text.encode("utf-8"))
            return

        # 4. Static Files Routing (index.html, app.js, style.css)
        clean_path = self.path.split("?")[0]
        if clean_path in ("/", "/index.html"):
            target_file = os.path.join(SCRIPT_DIR, "web", "index.html")
            content_type = "text/html; charset=utf-8"
        elif clean_path == "/style.css":
            target_file = os.path.join(SCRIPT_DIR, "web", "style.css")
            content_type = "text/css"
        elif clean_path == "/app.js":
            target_file = os.path.join(SCRIPT_DIR, "web", "app.js")
            content_type = "application/javascript"
        else:
            self.send_error(404, "File Not Found")
            return

        if os.path.exists(target_file):
            with open(target_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "Static file not found")

    def handle_websocket(self):
        """Performs RFC 6455 handshake and enters streaming loop."""
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "Missing Sec-WebSocket-Key")
            return

        # Calculate accept key
        guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept = base64.b64encode(hashlib.sha1((key + guid).encode("utf-8")).digest()).decode("utf-8")

        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        sock = self.request
        with ws_lock:
            connected_websockets.append(sock)

        try:
            while True:
                # Keep socket alive (broadcaster thread sends frames)
                data = sock.recv(1024)
                if not data:
                    break
        except Exception:
            pass
        finally:
            with ws_lock:
                if sock in connected_websockets:
                    connected_websockets.remove(sock)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def websocket_broadcaster_thread():
    """Broadcasts 10 Hz telemetry frames to all connected WebSockets."""
    while True:
        time.sleep(0.1) # 10 Hz
        with ws_lock:
            if not connected_websockets:
                continue
            snapshot = get_full_telemetry()
            frame = encode_ws_frame(json.dumps(snapshot))
            dead_sockets = []
            for sock in connected_websockets:
                try:
                    sock.sendall(frame)
                except Exception:
                    dead_sockets.append(sock)
            for d in dead_sockets:
                if d in connected_websockets:
                    connected_websockets.remove(d)

# ======================================================================================
# MAIN ENTRYPOINT
# ======================================================================================
def main():
    global mav_manager, sbc_monitor

    parser = argparse.ArgumentParser(description="Drone Telemetry Web & Grafana Server")
    parser.add_argument("--port", default="/dev/serial0", help="Pixhawk TELEM2 serial port (default: /dev/serial0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--web-port", type=int, default=8000, help="Web Dashboard HTTP Port (default: 8000)")
    parser.add_argument("--simulate", action="store_true", help="Run simulated flight telemetry")
    args = parser.parse_args()

    print("=" * 72)
    print("      DRONE TELEMETRY WEB DASHBOARD & GRAFANA SERVER (115200 BAUD)      ")
    print("=" * 72)

    # 1. Initialize SBC Monitor
    sbc_monitor = SBCMonitor()
    print("[+] SBC Health Monitor initialized.")

    # 2. Initialize MAVLink Ingestion
    mav_manager = MAVLinkManager(port=args.port, baud=args.baud, simulate=args.simulate)
    mav_manager.start()
    print(f"[+] MAVLink Manager started ({'SIMULATION' if args.simulate else args.port}).")

    # 3. Start WebSocket Broadcaster Thread
    b_thread = threading.Thread(target=websocket_broadcaster_thread, daemon=True)
    b_thread.start()

    # 4. Start HTTP & WebSocket Server
    server_address = ("0.0.0.0", args.web_port)
    httpd = ThreadedHTTPServer(server_address, TelemetryHTTPHandler)
    
    print("\n" + "=" * 72)
    print(f"  🚀 Web Dashboard Running:   http://localhost:{args.web_port}")
    print(f"  📊 Grafana /metrics Export: http://localhost:{args.web_port}/metrics")
    print(f"  📡 WebSocket Feed:          ws://localhost:{args.web_port}/ws/telemetry")
    print("=" * 72 + "\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
        if mav_manager:
            mav_manager.stop()
        httpd.shutdown()
        print("[✓] Server stopped cleanly.")

if __name__ == "__main__":
    main()
