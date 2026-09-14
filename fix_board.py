import time
from pymavlink import mavutil

print("[*] Connecting to Pixhawk on /dev/ttyACM0 (115200 baud)...")
mav = mavutil.mavlink_connection('/dev/ttyACM0', baud=115200)

print("[*] Waiting for Heartbeat...")
hb = mav.wait_heartbeat(timeout=8)
if hb:
    tgt_sys = mav.target_system
    tgt_comp = 1
    print(f"[✓] Heartbeat received! System: {tgt_sys}, Component: {tgt_comp}")
else:
    print("[!] No heartbeat received.")
    tgt_sys = 1
    tgt_comp = 1

# Send GCS Heartbeat
mav.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_GCS,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
    0, 0,
    mavutil.mavlink.MAV_STATE_ACTIVE
)

# 1. Read current BRD_TYPE
print("[*] Requesting current BRD_TYPE parameter...")
mav.mav.param_request_read_send(tgt_sys, tgt_comp, b"BRD_TYPE", -1)

# Wait a moment for response
time.sleep(1.0)
while True:
    msg = mav.recv_match(type='PARAM_VALUE', blocking=False)
    if not msg:
        break
    if msg.param_id == 'BRD_TYPE':
        print(f"[!] Current BRD_TYPE is: {msg.param_value} (Auto=0, Pixhawk 1/2.4.8=2)")

# 2. Force BRD_TYPE = 2 (Pixhawk 1 / FMUv2 / Pixhawk 2.4.8)
print("[*] Setting BRD_TYPE = 2 (Forcing Pixhawk 2.4.8 board type)...")
mav.mav.param_set_send(
    tgt_sys, tgt_comp,
    b"BRD_TYPE",
    2.0,
    mavutil.mavlink.MAV_PARAM_TYPE_REAL32
)

time.sleep(1.0)

# 3. Reboot Pixhawk to apply hardware configuration
print("[*] Sending reboot command to apply BRD_TYPE change...")
mav.mav.command_long_send(
    tgt_sys, tgt_comp,
    mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
    0,
    1, 0, 0, 0, 0, 0, 0 # Param1 = 1 (Reboot autopilot)
)

print("[*] Waiting 5 seconds for Pixhawk to reboot with BRD_TYPE=2...")
time.sleep(5.0)

print("[*] Listening for boot messages...")
start = time.time()
while time.time() - start < 15:
    msg = mav.recv_match(blocking=True, timeout=1.0)
    if not msg:
        continue
    mtype = msg.get_type()
    if mtype == 'STATUSTEXT':
        print(f"💬 [STATUS] {msg.text}")
    elif mtype == 'PARAM_VALUE' and msg.param_id == 'BRD_TYPE':
        print(f"⚙️  [PARAM]  BRD_TYPE is now: {msg.param_value}")
    elif mtype in ('ATTITUDE', 'AHRS'):
        print(f"🔥 [SUCCESS] Attitude packet received! Roll={msg.roll:.2f}")
