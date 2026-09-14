import time
import math
from pymavlink import mavutil

print("[*] Connecting to Pixhawk on /dev/ttyACM0 (115200 baud)...")
mav = mavutil.mavlink_connection('/dev/ttyACM0', baud=115200)

print("[*] Waiting for Heartbeat...")
hb = mav.wait_heartbeat(timeout=5)
if hb:
    tgt_sys = mav.target_system
    tgt_comp = mav.target_component
    print(f"[✓] Heartbeat received! System: {tgt_sys}, Component: {tgt_comp}, Type: {hb.type}, Autopilot: {hb.autopilot}")
else:
    print("[!] No heartbeat received within 5s.")
    tgt_sys = 1
    tgt_comp = 1

# 1. Send GCS Heartbeat
mav.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_GCS,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
    0, 0,
    mavutil.mavlink.MAV_STATE_ACTIVE
)

# 2. Request Data Streams (Stream ID 0 = ALL, 1=RAW_SENSORS, 2=EXTENDED_STATUS, 3=RC_CHANNELS, 4=RAW_CONTROLLER, 6=POSITION, 10=EXTRA1/ATTITUDE, 11=EXTRA2/VFR_HUD, 12=EXTRA3)
print("[*] Requesting all MAVLink telemetry streams...")
for stream_id in [0, 1, 2, 3, 4, 6, 10, 11, 12]:
    mav.mav.request_data_stream_send(tgt_sys, tgt_comp, stream_id, 10, 1)
    mav.mav.request_data_stream_send(tgt_sys, 0, stream_id, 10, 1)

# 3. Modern SET_MESSAGE_INTERVAL for Attitude (30) and IMU (27) at 10 Hz (100000 us)
for msg_id in [30, 27, 26, 33, 74, 1]:
    mav.mav.command_long_send(
        tgt_sys, 1,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
        0,
        msg_id, 100000, 0, 0, 0, 0, 0
    )

# 4. Request parameter SR0_EXTRA1
mav.mav.param_request_read_send(tgt_sys, 1, b"SR0_EXTRA1", -1)

print("\n" + "=" * 70)
print("  🚀 LISTENING FOR ALL PACKETS FROM PIXHAWK (TILT PIXHAWK NOW!)")
print("=" * 70)

last_hb = time.time()
start_time = time.time()

while time.time() - start_time < 20:
    now = time.time()
    if now - last_hb >= 1.0:
        last_hb = now
        mav.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, mavutil.mavlink.MAV_STATE_ACTIVE)
        # Re-send stream request
        mav.mav.request_data_stream_send(tgt_sys, tgt_comp, 0, 10, 1)

    msg = mav.recv_match(blocking=True, timeout=0.5)
    if not msg:
        continue

    mtype = msg.get_type()
    if mtype == 'BAD_DATA':
        continue

    if mtype in ('ATTITUDE', 'AHRS2', 'AHRS3'):
        if hasattr(msg, 'roll'):
            r = round(math.degrees(msg.roll), 2)
            p = round(math.degrees(msg.pitch), 2)
            y = round(math.degrees(msg.yaw) % 360, 2)
            print(f"🔥 >>> [ATTITUDE] Roll: {r:+6.1f}° | Pitch: {p:+6.1f}° | Yaw: {y:5.1f}°")
    elif mtype in ('RAW_IMU', 'HIGHRES_IMU', 'SCALED_IMU'):
        gz = getattr(msg, 'zacc', 0)
        gx = getattr(msg, 'xgyro', 0)
        print(f"📡 >>> [IMU]      Z-Accel: {gz} | X-Gyro: {gx}")
    elif mtype == 'PARAM_VALUE':
        print(f"⚙️  [PARAM]     {msg.param_id} = {msg.param_value}")
    elif mtype == 'STATUSTEXT':
        print(f"💬 [STATUS]    {msg.text}")
    elif mtype in ('VFR_HUD', 'SYS_STATUS', 'GLOBAL_POSITION_INT'):
        print(f"📊 [{mtype:<12}] {msg.to_dict()}")
    else:
        # Print name of any other message
        print(f"📦 [PACKET]    {mtype}")
