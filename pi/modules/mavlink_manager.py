#!/usr/bin/env python3
"""
======================================================================================
Module: MAVLink Telemetry Manager & Shared State Hub
File: pi/modules/mavlink_manager.py

Description:
  Singleton MAVLink reader that connects to Pixhawk 2.4.8 on TELEM2 (/dev/serial0)
  or USB (/dev/ttyACM0 @ 115200 baud).
  
  Key Features:
  - Broadcasts 1 Hz Companion Heartbeats to keep ArduPilot active telemetry streaming alive
  - Requests all sensor & attitude streams at 10 Hz
  - Decodes ATTITUDE, AHRS, SYS_STATUS, GLOBAL_POSITION_INT, VFR_HUD, RAW_IMU, SERVO_OUTPUT
  - Thread-safe state store for WebSockets and Radio TX
======================================================================================
"""

import time
import math
import threading
from typing import Dict, Any, List

class MAVLinkManager:
    def __init__(self, port: str = "/dev/serial0", baud: int = 115200, simulate: bool = False):
        self.port = port
        self.baud = baud
        self.simulate = simulate
        self.running = False
        self.thread = None
        self.mav = None
        self._lock = threading.Lock()

        # Telemetry State Store (All 11 Categories)
        self.state: Dict[str, Any] = {
            # 1. Total Battery & Power
            "battery_voltage": 0.0,
            "battery_current": 0.0,
            "battery_remaining": 0,
            
            # 2. Individual Cell Voltages (Cell 1 to 6)
            "cell_voltages": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "cell_delta_mv": 0,
            
            # 3. Altitude & Vertical Dynamics
            "altitude_relative": 0.0,
            "altitude_msl": 0.0,
            "climb_rate": 0.0,
            
            # 4. GPS & Positioning
            "latitude": 0.0,
            "longitude": 0.0,
            "satellites": 0,
            "gps_fix_type": "NO FIX",
            "hdop": 99.9,
            
            # 5. Signal Strength & Telemetry Link
            "rc_rssi": 0,
            "radio_link_quality": 0,
            
            # 6. Heading & Compass
            "heading": 0.0,
            "compass_status": "CALIBRATED",
            
            # 7. Flight Status & Mission State
            "armed": False,
            "flight_mode": "DISCONNECTED",
            "system_status": "STANDBY",
            "mission_state": "STANDBY",
            "mission_progress_percent": 0,
            
            # 8. 3-Axis Gyroscope & Accelerometer Rates
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,
            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 9.81,
            
            # 9. PID Attitude Tracking & Errors
            "attitude_roll": 0.0,
            "attitude_pitch": 0.0,
            "attitude_yaw": 0.0,
            "target_roll": 0.0,
            "target_pitch": 0.0,
            "target_yaw": 0.0,
            "error_roll": 0.0,
            "error_pitch": 0.0,
            
            # 10. Motor Power Outputs (Motors 1 to 4)
            "motor_pwm": [1000, 1000, 1000, 1000],
            "motor_percent": [0, 0, 0, 0],
            
            # Timing & Status
            "last_packet_timestamp": 0.0,
            "connected": False
        }

    def start(self):
        """Starts the MAVLink ingestion thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stops the ingestion loop."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.mav:
            try:
                self.mav.close()
            except Exception:
                pass

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        """Thread-safe copy of latest telemetry."""
        with self._lock:
            return dict(self.state)

    def _run_loop(self):
        if self.simulate:
            self._run_simulation()
        else:
            self._run_live_mavlink()

    def _send_companion_heartbeat(self, mavutil):
        """Sends periodic 1 Hz GCS heartbeat from Pi to Pixhawk to keep streams active."""
        if not self.mav:
            return
        try:
            self.mav.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0, 0,
                mavutil.mavlink.MAV_STATE_ACTIVE
            )
        except Exception:
            pass

    def _request_all_streams(self, mavutil):
        """Requests individual telemetry streams, sets stream params, and modern message intervals."""
        if not self.mav:
            return

        target_sys = getattr(self.mav, "target_system", 1) or 1
        target_comp = 1  # ArduPilot Autopilot primary component is always 1

        try:
            # 1. Set ArduPilot Stream Parameters (SR0=USB, SR1=TELEM1, SR2=TELEM2)
            stream_params = {
                "SR0_EXTRA1": 10.0,   # ATTITUDE @ 10 Hz
                "SR0_EXTRA2": 10.0,   # VFR_HUD @ 10 Hz
                "SR0_EXTRA3": 10.0,   # AHRS / system status @ 10 Hz
                "SR0_RAW_SENS": 10.0, # RAW_IMU / SCALED_IMU @ 10 Hz
                "SR0_POSITION": 5.0,  # GPS & position @ 5 Hz
                "SR0_EXT_STAT": 2.0,  # SYS_STATUS & battery @ 2 Hz
                "SR0_RC_CHAN": 5.0,   # RC_CHANNELS & servos @ 5 Hz

                "SR1_EXTRA1": 10.0,
                "SR1_EXTRA2": 10.0,
                "SR1_EXTRA3": 10.0,
                "SR1_RAW_SENS": 10.0,
                "SR1_POSITION": 5.0,
                "SR1_EXT_STAT": 2.0,
                "SR1_RC_CHAN": 5.0,

                "SR2_EXTRA1": 10.0,
                "SR2_EXTRA2": 10.0,
                "SR2_EXTRA3": 10.0,
                "SR2_RAW_SENS": 10.0,
                "SR2_POSITION": 5.0,
                "SR2_EXT_STAT": 2.0,
                "SR2_RC_CHAN": 5.0,
            }
            for p_name, p_val in stream_params.items():
                try:
                    p_bytes = p_name.encode('utf-8')
                    self.mav.mav.param_set_send(
                        target_sys, target_comp,
                        p_bytes, float(p_val),
                        mavutil.mavlink.MAV_PARAM_TYPE_REAL32
                    )
                except Exception:
                    pass

            # 2. Legacy MAV_DATA_STREAM requests (targeting both Component 1 and Component 0)
            target_comps = [1, 0]
            if getattr(self.mav, "target_component", 0) not in target_comps:
                target_comps.append(self.mav.target_component)

            for comp_id in target_comps:
                for s in [
                    mavutil.mavlink.MAV_DATA_STREAM_ALL,
                    mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                    mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,
                    mavutil.mavlink.MAV_DATA_STREAM_EXTRA3,
                    mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS,
                    mavutil.mavlink.MAV_DATA_STREAM_POSITION,
                    mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS,
                    mavutil.mavlink.MAV_DATA_STREAM_RC_CHANNELS
                ]:
                    self.mav.mav.request_data_stream_send(
                        target_sys, comp_id, s, 10, 1
                    )

            # 3. Modern message intervals (in microseconds)
            intervals = {
                mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE: 100000,            # 10 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_RAW_IMU: 100000,             # 10 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_SCALED_IMU: 100000,          # 10 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT: 200000, # 5 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT: 200000,         # 5 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_VFR_HUD: 200000,             # 5 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_SYS_STATUS: 500000,          # 2 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS: 500000,      # 2 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_SERVO_OUTPUT_RAW: 200000,    # 5 Hz
                mavutil.mavlink.MAVLINK_MSG_ID_NAV_CONTROLLER_OUTPUT: 200000# 5 Hz
            }
            for msg_id, interval_us in intervals.items():
                self.mav.mav.command_long_send(
                    target_sys, target_comp,
                    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                    0,
                    msg_id, interval_us, 0, 0, 0, 0, 0
                )
        except Exception:
            pass

    def _run_live_mavlink(self):
        try:
            from pymavlink import mavutil
        except ImportError:
            print("[!] ERROR: 'pymavlink' is not installed. Run: pip install pymavlink")
            return

        ports_to_try = [self.port, "/dev/ttyACM0", "/dev/serial0", "/dev/ttyAMA0", "/dev/ttyUSB0"]

        while self.running:
            mav_conn = None
            for p in ports_to_try:
                try:
                    mav_conn = mavutil.mavlink_connection(p, baud=self.baud)
                    print(f"[+] Opened serial port '{p}' at {self.baud} baud.")
                    break
                except Exception:
                    continue

            if not mav_conn:
                print(f"[!] Waiting for Pixhawk serial connection ({self.port}). Retrying in 2s...")
                time.sleep(2.0)
                continue

            self.mav = mav_conn

            print("[*] Waiting for MAVLink Heartbeat from Pixhawk...")
            try:
                hb = self.mav.wait_heartbeat(timeout=8)
                if hb:
                    tgt_sys = getattr(self.mav, "target_system", 1) or 1
                    tgt_comp = getattr(self.mav, "target_component", 1) or 1
                    print(f"[✓] Heartbeat received from Pixhawk (System: {tgt_sys}, Component: {tgt_comp})")
                    with self._lock:
                        self.state["connected"] = True
            except Exception:
                pass

            # Activate streams and send companion heartbeat
            self._send_companion_heartbeat(mavutil)
            self._request_all_streams(mavutil)

            last_heartbeat_time = time.time()
            last_stream_request_time = time.time()

            # Live Ingestion Loop
            while self.running:
                try:
                    now = time.time()

                    # 1. Send Companion Heartbeat at 1 Hz (CRITICAL for ArduPilot to stream data!)
                    if now - last_heartbeat_time >= 1.0:
                        last_heartbeat_time = now
                        self._send_companion_heartbeat(mavutil)

                    # 2. Re-request stream keep-alive every 3s
                    if now - last_stream_request_time >= 3.0:
                        last_stream_request_time = now
                        self._request_all_streams(mavutil)

                    # 3. Read incoming packets (drain all pending in buffer)
                    packets_read = 0
                    while packets_read < 50:
                        msg = self.mav.recv_match(blocking=False)
                        if not msg:
                            break
                        packets_read += 1

                        msg_type = msg.get_type()

                        with self._lock:
                            self.state["last_packet_timestamp"] = now
                            self.state["connected"] = True

                            # 1. HEARTBEAT
                            if msg_type == 'HEARTBEAT':
                                self.state["armed"] = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                                try:
                                    mode_map = self.mav.mode_mapping()
                                    inv_map = {v: k for k, v in mode_map.items()}
                                    self.state["flight_mode"] = inv_map.get(msg.custom_mode, f"MODE_{msg.custom_mode}")
                                except Exception:
                                    self.state["flight_mode"] = f"MODE_{msg.custom_mode}"
                                
                                sys_status_map = {
                                    0: "UNINIT", 1: "BOOT", 2: "CALIBRATING", 3: "STANDBY",
                                    4: "ACTIVE", 5: "CRITICAL", 6: "EMERGENCY"
                                }
                                self.state["system_status"] = sys_status_map.get(msg.system_status, "ACTIVE")

                            # 2. SYS_STATUS
                            elif msg_type == 'SYS_STATUS':
                                if msg.voltage_battery > 0:
                                    self.state["battery_voltage"] = round(msg.voltage_battery / 1000.0, 2)
                                if msg.current_battery >= 0:
                                    self.state["battery_current"] = round(msg.current_battery / 100.0, 1)
                                if 0 <= msg.battery_remaining <= 100:
                                    self.state["battery_remaining"] = msg.battery_remaining

                            # 3. BATTERY_STATUS
                            elif msg_type == 'BATTERY_STATUS':
                                if len(msg.voltages) > 0:
                                    valid_cells = []
                                    for v in msg.voltages[:6]:
                                        if v not in (0, 65535):
                                            cell_v = round(v / 1000.0, 3)
                                            valid_cells.append(cell_v)
                                        else:
                                            valid_cells.append(0.0)
                                    self.state["cell_voltages"] = valid_cells
                                    active_cells = [c for c in valid_cells if c > 1.0]
                                    if active_cells:
                                        delta = int((max(active_cells) - min(active_cells)) * 1000)
                                        self.state["cell_delta_mv"] = max(0, delta)
                                if msg.current_battery >= 0:
                                    self.state["battery_current"] = round(msg.current_battery / 100.0, 1)
                                if 0 <= msg.battery_remaining <= 100:
                                    self.state["battery_remaining"] = msg.battery_remaining

                            # 4. GLOBAL_POSITION_INT
                            elif msg_type == 'GLOBAL_POSITION_INT':
                                self.state["latitude"] = round(msg.lat / 1e7, 7)
                                self.state["longitude"] = round(msg.lon / 1e7, 7)
                                self.state["altitude_relative"] = round(msg.relative_alt / 1000.0, 1)
                                self.state["altitude_msl"] = round(msg.alt / 1000.0, 1)
                                if msg.hdg != 65535 and msg.hdg != 0:
                                    self.state["heading"] = round(msg.hdg / 100.0, 1)

                            # 5. GPS_RAW_INT
                            elif msg_type == 'GPS_RAW_INT':
                                self.state["satellites"] = msg.satellites_visible
                                fix_map = {0: "NO FIX", 1: "NO FIX", 2: "2D FIX", 3: "3D FIX", 4: "DGPS", 5: "RTK FLT", 6: "RTK FIX"}
                                self.state["gps_fix_type"] = fix_map.get(msg.fix_type, "NO FIX" if msg.fix_type == 0 else "3D FIX")
                                self.state["hdop"] = round(msg.eph / 100.0, 2)

                            # 6. VFR_HUD
                            elif msg_type == 'VFR_HUD':
                                self.state["climb_rate"] = round(msg.climb, 2)
                                if msg.heading != 0:
                                    self.state["heading"] = round(msg.heading, 1)
                                if hasattr(msg, 'alt') and msg.alt is not None:
                                    self.state["altitude_msl"] = round(msg.alt, 1)
                                    if self.state["altitude_relative"] == 0.0:
                                        self.state["altitude_relative"] = round(msg.alt, 1)

                            # 7. ATTITUDE & AHRS (Euler Angles & Angular Rates)
                            elif msg_type in ('ATTITUDE', 'AHRS', 'AHRS2', 'AHRS3'):
                                self.state["attitude_roll"] = round(math.degrees(msg.roll), 2)
                                self.state["attitude_pitch"] = round(math.degrees(msg.pitch), 2)
                                self.state["attitude_yaw"] = round(math.degrees(msg.yaw) % 360, 2)
                                if hasattr(msg, 'rollspeed'):
                                    self.state["gyro_x"] = round(math.degrees(msg.rollspeed), 2)
                                    self.state["gyro_y"] = round(math.degrees(msg.pitchspeed), 2)
                                    self.state["gyro_z"] = round(math.degrees(msg.yawspeed), 2)
                                if self.state["heading"] == 0:
                                    self.state["heading"] = self.state["attitude_yaw"]
                                self.state["error_roll"] = round(self.state["target_roll"] - self.state["attitude_roll"], 2)
                                self.state["error_pitch"] = round(self.state["target_pitch"] - self.state["attitude_pitch"], 2)

                            # 8. ATTITUDE_TARGET & NAV_CONTROLLER_OUTPUT
                            elif msg_type == 'ATTITUDE_TARGET':
                                try:
                                    q = msg.q
                                    sinr_cosp = 2 * (q[0] * q[1] + q[2] * q[3])
                                    cosr_cosp = 1 - 2 * (q[1] * q[1] + q[2] * q[2])
                                    self.state["target_roll"] = round(math.degrees(math.atan2(sinr_cosp, cosr_cosp)), 2)
                                    sinp = 2 * (q[0] * q[2] - q[3] * q[1])
                                    if abs(sinp) >= 1:
                                        self.state["target_pitch"] = round(math.copysign(90, sinp), 2)
                                    else:
                                        self.state["target_pitch"] = round(math.degrees(math.asin(sinp)), 2)
                                except Exception:
                                    pass
                            elif msg_type == 'NAV_CONTROLLER_OUTPUT':
                                self.state["target_roll"] = round(msg.nav_roll, 2)
                                self.state["target_pitch"] = round(msg.nav_pitch, 2)
                                self.state["target_yaw"] = round(msg.target_bearing, 2)
                                self.state["error_roll"] = round(msg.nav_roll - self.state["attitude_roll"], 2)
                                self.state["error_pitch"] = round(msg.nav_pitch - self.state["attitude_pitch"], 2)

                            # 9. HIGHRES_IMU / RAW_IMU / SCALED_IMU
                            elif msg_type == 'HIGHRES_IMU':
                                self.state["accel_x"] = round(msg.xacc, 2)
                                self.state["accel_y"] = round(msg.yacc, 2)
                                self.state["accel_z"] = round(msg.zacc, 2)
                                self.state["gyro_x"] = round(math.degrees(msg.xgyro), 2)
                                self.state["gyro_y"] = round(math.degrees(msg.ygyro), 2)
                                self.state["gyro_z"] = round(math.degrees(msg.zgyro), 2)
                            elif msg_type in ('RAW_IMU', 'SCALED_IMU', 'SCALED_IMU2', 'SCALED_IMU3'):
                                self.state["accel_x"] = round((msg.xacc / 1000.0) * 9.81, 2)
                                self.state["accel_y"] = round((msg.yacc / 1000.0) * 9.81, 2)
                                self.state["accel_z"] = round((msg.zacc / 1000.0) * 9.81, 2)
                                if hasattr(msg, 'xgyro') and self.state["gyro_x"] == 0:
                                    self.state["gyro_x"] = round(math.degrees(msg.xgyro / 1000.0), 2)
                                    self.state["gyro_y"] = round(math.degrees(msg.ygyro / 1000.0), 2)
                                    self.state["gyro_z"] = round(math.degrees(msg.zgyro / 1000.0), 2)

                            # 10. SERVO_OUTPUT_RAW (Motor PWMs 1-4)
                            elif msg_type == 'SERVO_OUTPUT_RAW':
                                pwms = [msg.servo1_raw, msg.servo2_raw, msg.servo3_raw, msg.servo4_raw]
                                self.state["motor_pwm"] = pwms
                                self.state["motor_percent"] = [
                                    max(0, min(100, int((p - 1000) / 10.0))) for p in pwms
                                ]

                            # 11. RC_CHANNELS
                            elif msg_type == 'RC_CHANNELS':
                                if msg.rssi > 0:
                                    self.state["rc_rssi"] = int((msg.rssi / 255.0) * 100)
                                else:
                                    self.state["rc_rssi"] = 90

                    time.sleep(0.005) # Yield CPU

                except Exception as e:
                    print(f"[!] MAVLink read error: {e}")
                    time.sleep(0.1)
                    break

    def _run_simulation(self):
        """Dynamic simulation loop only used when --simulate flag is explicitly set."""
        print("[+] Starting high-fidelity telemetry simulator (10 Hz)...")
        t = 0.0
        base_lat = 12.971598
        base_lon = 77.594562
        base_voltage = 12.58

        while self.running:
            time.sleep(0.1)
            t += 0.1

            sim_alt = round(max(0.0, 15.0 + 3.0 * math.sin(t * 0.2)), 1)
            sim_lat = round(base_lat + 0.0004 * math.sin(t * 0.1), 7)
            sim_lon = round(base_lon + 0.0004 * math.cos(t * 0.1), 7)
            sim_heading = round((t * 12.0) % 360, 1)

            roll_target = round(3.5 * math.sin(t * 0.8), 2)
            pitch_target = round(2.0 * math.cos(t * 0.5), 2)
            roll_actual = round(roll_target + 0.3 * math.sin(t * 3.0), 2)
            pitch_actual = round(pitch_target + 0.2 * math.cos(t * 3.5), 2)

            gyro_x = round(5.0 * math.cos(t * 1.5), 2)
            gyro_y = round(4.0 * math.sin(t * 1.2), 2)
            gyro_z = round(2.5 * math.sin(t * 0.4), 2)

            accel_x = round(0.4 * math.sin(t * 1.5), 2)
            accel_y = round(0.3 * math.cos(t * 1.2), 2)
            accel_z = round(9.81 + 0.5 * math.sin(t * 2.0), 2)

            sim_voltage = max(10.8, round(base_voltage - (t * 0.002), 2))
            c1 = round((sim_voltage / 3.0) + 0.012, 3)
            c2 = round((sim_voltage / 3.0) - 0.008, 3)
            c3 = round((sim_voltage / 3.0) + 0.002, 3)
            cell_delta = int((max(c1, c2, c3) - min(c1, c2, c3)) * 1000)

            base_pwm = 1580
            m1 = int(base_pwm + 45 * math.sin(t * 2.0))
            m2 = int(base_pwm - 35 * math.sin(t * 2.0))
            m3 = int(base_pwm + 40 * math.cos(t * 2.0))
            m4 = int(base_pwm - 30 * math.cos(t * 2.0))

            with self._lock:
                self.state.update({
                    "battery_voltage": sim_voltage,
                    "battery_current": round(14.5 + 2.5 * math.sin(t * 0.5), 1),
                    "battery_remaining": max(10, int(88 - (t * 0.05))),
                    "cell_voltages": [c1, c2, c3, 0.0, 0.0, 0.0],
                    "cell_delta_mv": cell_delta,
                    "altitude_relative": sim_alt,
                    "altitude_msl": round(sim_alt + 920.0, 1),
                    "climb_rate": round(0.6 * math.cos(t * 0.2), 2),
                    "latitude": sim_lat,
                    "longitude": sim_lon,
                    "satellites": 16,
                    "gps_fix_type": "3D FIX",
                    "hdop": 0.85,
                    "rc_rssi": int(92 + 5 * math.sin(t * 0.1)),
                    "radio_link_quality": 98,
                    "heading": sim_heading,
                    "armed": True,
                    "flight_mode": "GUIDED",
                    "system_status": "ACTIVE",
                    "mission_state": "SEARCHING (LANE 2/5)",
                    "mission_progress_percent": int((t * 2.0) % 100),
                    "gyro_x": gyro_x,
                    "gyro_y": gyro_y,
                    "gyro_z": gyro_z,
                    "accel_x": accel_x,
                    "accel_y": accel_y,
                    "accel_z": accel_z,
                    "attitude_roll": roll_actual,
                    "attitude_pitch": pitch_actual,
                    "attitude_yaw": sim_heading,
                    "target_roll": roll_target,
                    "target_pitch": pitch_target,
                    "target_yaw": sim_heading,
                    "error_roll": round(roll_target - roll_actual, 2),
                    "error_pitch": round(pitch_target - pitch_actual, 2),
                    "motor_pwm": [m1, m2, m3, m4],
                    "motor_percent": [int((m - 1000) / 10.0) for m in [m1, m2, m3, m4]],
                    "last_packet_timestamp": time.time(),
                    "connected": True
                })
