import math
import os
import sys
import unittest
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "pi"))

from modules.mavlink_manager import MAVLinkManager


class FakeMavlink:
    MAV_MODE_FLAG_SAFETY_ARMED = 128


class FakeMavutil:
    mavlink = FakeMavlink()


class FakeMav:
    def mode_mapping(self):
        return {"STABILIZE": 0, "AUTO": 3}


class Msg(SimpleNamespace):
    def __init__(self, msg_type, **kwargs):
        super().__init__(**kwargs)
        self._msg_type = msg_type

    def get_type(self):
        return self._msg_type


class MAVLinkManagerDecodeTest(unittest.TestCase):
    def setUp(self):
        self.manager = MAVLinkManager()
        self.manager.mav = FakeMav()

    def handle(self, msg):
        self.manager._handle_mavlink_message(msg, FakeMavutil(), now=123.0)
        return self.manager.get_telemetry_snapshot()

    def test_heartbeat_sets_connection_mode_and_arm_state(self):
        state = self.handle(Msg("HEARTBEAT", base_mode=128, custom_mode=3, system_status=4))

        self.assertTrue(state["connected"])
        self.assertTrue(state["armed"])
        self.assertEqual(state["flight_mode"], "AUTO")
        self.assertEqual(state["system_status"], "ACTIVE")
        self.assertEqual(state["last_heartbeat_timestamp"], 123.0)

    def test_power_position_gps_and_heading_decode(self):
        self.handle(Msg("SYS_STATUS", voltage_battery=12580, current_battery=1640, battery_remaining=76))
        self.handle(Msg("BATTERY_STATUS", voltages=[4190, 4184, 4202, 0, 65535, 65535], current_battery=1650, battery_remaining=75))
        self.handle(Msg("GLOBAL_POSITION_INT", lat=129715980, lon=775945620, relative_alt=4260, alt=938400, hdg=0))
        state = self.handle(Msg("GPS_RAW_INT", satellites_visible=14, fix_type=3, eph=86))

        self.assertEqual(state["battery_voltage"], 12.58)
        self.assertEqual(state["battery_current"], 16.5)
        self.assertEqual(state["battery_remaining"], 75)
        self.assertEqual(state["cell_voltages"][:4], [4.19, 4.184, 4.202, 0.0])
        self.assertEqual(state["cell_delta_mv"], 18)
        self.assertEqual(state["latitude"], 12.971598)
        self.assertEqual(state["longitude"], 77.594562)
        self.assertEqual(state["altitude_relative"], 4.26)
        self.assertEqual(state["altitude_msl"], 938.4)
        self.assertEqual(state["heading"], 0.0)
        self.assertEqual(state["gps_fix_type"], "3D FIX")
        self.assertEqual(state["hdop"], 0.86)

    def test_attitude_target_navigation_and_signal_decode(self):
        self.handle(Msg("ATTITUDE", roll=math.radians(3), pitch=math.radians(-2), yaw=math.radians(350), rollspeed=0.1, pitchspeed=-0.2, yawspeed=0.3))
        self.handle(Msg("NAV_CONTROLLER_OUTPUT", nav_roll=1.5, nav_pitch=-1.0, target_bearing=10, wp_dist=42))
        self.handle(Msg("RC_CHANNELS", rssi=127))
        state = self.handle(Msg("RADIO_STATUS", rssi=200, remrssi=180))

        self.assertEqual(state["attitude_roll"], 3.0)
        self.assertEqual(state["attitude_pitch"], -2.0)
        self.assertEqual(state["attitude_yaw"], 350.0)
        self.assertEqual(state["target_yaw"], 10.0)
        self.assertEqual(state["error_roll"], -1.5)
        self.assertEqual(state["error_pitch"], 1.0)
        self.assertEqual(state["error_yaw"], 20.0)
        self.assertEqual(state["dist_to_target_wp_m"], 42.0)
        self.assertEqual(state["rc_rssi"], 50)
        self.assertEqual(state["radio_link_quality"], 78)


if __name__ == "__main__":
    unittest.main()
