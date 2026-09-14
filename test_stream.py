import time
import math
from pymavlink import mavutil

print("[*] Connecting to Pixhawk on /dev/ttyACM0 (115200 baud)...")
mav = mavutil.mavlink_connection('/dev/ttyACM0', baud=115200)

print("[*] Waiting for Heartbeat...")
hb = mav.wait_heartbeat(timeout=5)
if hb:
    tgt_sys = getattr(mav, "target_system", 1) or 1
    tgt_comp = getattr(mav, "target_component", 1) or 1
    print(f"[✓] Heartbeat received! System: {tgt_sys}, Component: {tgt_comp}")
else:
    print("[!] No heartbeat received within 5s.")
    tgt_sys = 1
    tgt_comp = 1

# 1. Send GCS Heartbeat to let ArduPilot know a Ground Station is connected
mav.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_GCS,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
    0, 0,
    mavutil.mavlink.MAV_STATE_ACTIVE
)

# 2. Force ArduPilot stream rate parameters (SR0 for USB)
for p, val in [("SR0_EXTRA1", 10.0), ("SR0_EXTRA2", 10.0), ("SR0_RAW_SENS", 10.0), ("SR0_EXT_STAT", 2.0)]:
    try:
        mav.mav.param_set_send(tgt_sys, 1, p.encode('utf-8'), float(val), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    except Exception:
        pass

# 3. Request all data streams at 10 Hz
for comp in (1, 0):
    for s in (0, 1, 2, 3, 4, 6, 10, 11, 12):
        try:
            mav.mav.request_data_stream_send(tgt_sys, comp, s, 10, 1)
        except Exception:
            pass

# 4. Set attitude message interval
try:
    mav.mav.command_long_send(tgt_sys, 1, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 100000, 0, 0, 0, 0, 0)
except Exception:
    pass

print("\n" + "=" * 70)
print("  🚀 LISTENING FOR LIVE SENSOR PACKETS (TILT THE PIXHAWK NOW!)")
print("=" * 70)

last_hb = time.time()
count = 0
while count < 40:
    now = time.time()
    if now - last_hb >= 1.0:
        last_hb = now
        mav.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, mavutil.mavlink.MAV_STATE_ACTIVE)

    msg = mav.recv_match(blocking=True, timeout=1.0)
    if not msg:
        print("[!] Waiting for packets...")
        continue

    mtype = msg.get_type()
    if mtype in ('ATTITUDE', 'AHRS', 'AHRS2', 'AHRS3'):
        r = round(math.degrees(msg.roll), 2)
        p = round(math.degrees(msg.pitch), 2)
        y = round(math.degrees(msg.yaw) % 360, 2)
        print(f">>> [LIVE ATTITUDE] Roll: {r:+6.1f}° | Pitch: {p:+6.1f}° | Yaw: {y:5.1f}°")
        count += 1
    elif mtype in ('RAW_IMU', 'HIGHRES_IMU', 'SCALED_IMU'):
        gz = getattr(msg, 'zacc', 0)
        gx = getattr(msg, 'xgyro', 0)
        print(f">>> [LIVE IMU]      Z-Accel: {gz} | X-Gyro: {gx}")
        count += 1
    elif mtype in ('VFR_HUD', 'SYS_STATUS'):
        print(f"    [{mtype}] {msg.to_dict()}")
        count += 1
