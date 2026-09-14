#!/usr/bin/env python3
"""
======================================================================================
Module 3: Automated Boustrophedon Grid Search Mission Controller
File: pi/modules/grid_search_module.py

Description:
  Generates alternating serpentine (lawnmower) survey grid waypoints based on
  a center GPS coordinate and search radius. Uploads the mission directly to
  Pixhawk 2.4.8 over MAVLink and commands autonomous execution.
======================================================================================
"""

import math
import time
import threading

EARTH_RADIUS = 6378137.0 # meters

class GridSearchModule:
    def __init__(self, mav_manager):
        self.mav_manager = mav_manager
        self.active_mission = False
        self.mission_status = {
            "state": "IDLE",
            "center_lat": 0.0,
            "center_lon": 0.0,
            "radius_m": 0.0,
            "altitude_m": 0.0,
            "spacing_m": 0.0,
            "waypoint_count": 0,
            "current_wp_index": 0,
            "progress_percent": 0
        }
        self._lock = threading.Lock()

    def generate_grid_waypoints(self, center_lat: float, center_lon: float,
                                radius_m: float = 50.0, altitude_m: float = 15.0,
                                spacing_m: float = 10.0) -> list:
        """
        Calculates serpentine (lawnmower) grid waypoints centered at (center_lat, center_lon)
        covering a bounding box of size (2*radius) x (2*radius).
        """
        waypoints = []
        num_lanes = int((2 * radius_m) / spacing_m) + 1

        for i in range(num_lanes):
            dx = -radius_m + (i * spacing_m)
            # Alternate sweep directions (South->North vs North->South)
            y_points = [-radius_m, radius_m] if (i % 2 == 0) else [radius_m, -radius_m]

            for dy in y_points:
                dlat = (dy / EARTH_RADIUS) * (180.0 / math.pi)
                dlon = (dx / (EARTH_RADIUS * math.cos(math.radians(center_lat)))) * (180.0 / math.pi)
                wp_lat = center_lat + dlat
                wp_lon = center_lon + dlon
                waypoints.append((wp_lat, wp_lon, altitude_m))

        return waypoints

    def upload_mission_to_pixhawk(self, waypoints: list, takeoff_alt: float = 15.0) -> bool:
        """Uploads waypoints to Pixhawk using MAVLink Mission Protocol."""
        mav = getattr(self.mav_manager, "mav", None)
        if not mav:
            print("[*] Module 3 (Grid Search): Running in simulation mode (Mission simulated).")
            return True

        try:
            from pymavlink import mavutil
            # 1. Clear existing mission
            mav.mav.mission_clear_all_send(mav.target_system, mav.target_component)
            mav.recv_match(type='MISSION_ACK', blocking=True, timeout=3.0)

            # 2. Announce mission item count (Takeoff + WPs + RTL)
            total_items = len(waypoints) + 2
            mav.mav.mission_count_send(mav.target_system, mav.target_component, total_items)

            seq = 0
            while seq < total_items:
                msg = mav.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST'], blocking=True, timeout=3.0)
                if not msg:
                    return False
                req_seq = msg.seq

                if req_seq == 0:
                    # Item 0: Takeoff
                    mav.mav.mission_item_int_send(
                        mav.target_system, mav.target_component,
                        0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                        0, 1, 0, 0, 0, 0,
                        int(waypoints[0][0] * 1e7), int(waypoints[0][1] * 1e7), takeoff_alt
                    )
                elif req_seq <= len(waypoints):
                    # Waypoints 1..N
                    wp = waypoints[req_seq - 1]
                    mav.mav.mission_item_int_send(
                        mav.target_system, mav.target_component,
                        req_seq, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                        0, 1, 0, 2.0, 0, 0,
                        int(wp[0] * 1e7), int(wp[1] * 1e7), wp[2]
                    )
                elif req_seq == total_items - 1:
                    # Final Item: RTL
                    mav.mav.mission_item_int_send(
                        mav.target_system, mav.target_component,
                        req_seq, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                        mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                        0, 1, 0, 0, 0, 0,
                        0, 0, 0
                    )
                seq = req_seq + 1

            ack = mav.recv_match(type='MISSION_ACK', blocking=True, timeout=3.0)
            return ack and ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED

        except Exception as e:
            print(f"[!] Mission upload failed: {e}")
            return False

    def trigger_grid_search(self, lat: float = None, lon: float = None,
                            radius_m: float = 50.0, altitude_m: float = 15.0,
                            spacing_m: float = 10.0, auto_arm: bool = False) -> dict:
        """Triggers grid search from specified point or current drone GPS."""
        snap = self.mav_manager.get_telemetry_snapshot()
        center_lat = lat if lat is not None else snap.get("latitude", 12.971598)
        center_lon = lon if lon is not None else snap.get("longitude", 77.594562)

        if center_lat == 0.0 or center_lon == 0.0:
            center_lat, center_lon = 12.971598, 77.594562

        waypoints = self.generate_grid_waypoints(center_lat, center_lon, radius_m, altitude_m, spacing_m)
        success = self.upload_mission_to_pixhawk(waypoints, altitude_m)

        with self._lock:
            self.mission_status.update({
                "state": "SEARCHING" if success else "FAILED",
                "center_lat": center_lat,
                "center_lon": center_lon,
                "radius_m": radius_m,
                "altitude_m": altitude_m,
                "spacing_m": spacing_m,
                "waypoint_count": len(waypoints),
                "current_wp_index": 1,
                "progress_percent": 0
            })

        return {
            "status": "success" if success else "error",
            "waypoints_generated": len(waypoints),
            "center": [center_lat, center_lon],
            "radius_m": radius_m,
            "altitude_m": altitude_m,
            "spacing_m": spacing_m
        }

    def get_status(self) -> dict:
        with self._lock:
            return dict(self.mission_status)

if __name__ == "__main__":
    from mavlink_manager import MAVLinkManager
    mgr = MAVLinkManager(simulate=True)
    mgr.start()
    grid = GridSearchModule(mgr)
    res = grid.trigger_grid_search(radius_m=30, spacing_m=8)
    print("Grid search result:", res)
    mgr.stop()
