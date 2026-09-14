# End-to-End Master Companion Pipeline

```mermaid
sequenceDiagram
    autonumber
    participant Pixhawk as Pixhawk 2.4.8 (Autopilot)
    participant MAV_MGR as MAVLinkManager (pi/modules/)
    participant Radio_Mod as Module 1: RadioTX (NRF24 SPI)
    participant Web_Mod as Module 2: Web Dashboard (:8000)
    participant Grid_Mod as Module 3: Autonomous Mission Planner
    participant ESP as ESP32 Ground Unit (OLED)
    participant Browser as PC / Mobile Browser

    Pixhawk->>MAV_MGR: MAVLink2 Packets @ 115200 (TELEM2 / USB)
    Note over MAV_MGR: Decodes Battery, Altitude, GPS, Gyro, Accel, PID, Motors, Mission Progress

    par Module 1: Radio RF Broadcast (5 Hz)
        MAV_MGR->>Radio_Mod: Fetches Telemetry Snapshot
        Radio_Mod->>ESP: Broadcasts 20-byte struct over NRF24L01+ (Channel 90)
        ESP->>ESP: Renders 3-Level Display on 1.3" SH1106 OLED
    and Module 2: Real-Time WebSockets (10 Hz)
        Web_Mod-->>Browser: JSON Frame (/ws/telemetry)
        Note over Browser: Updates Leaflet GPS Map, Live Waypoints, Gyro Rates, Cell Stack, Motors
    and Module 3: Autonomous Search Mission Lifecycle
        Browser->>Web_Mod: POST /api/mission/preview (Point, Radius, Pattern)
        Web_Mod->>Grid_Mod: Computes Waypoints & Preview Route
        Grid_Mod-->>Browser: Returns Waypoint Geometry & Flight Duration
        Browser->>Web_Mod: POST /api/mission/upload
        Grid_Mod->>MAV_MGR: Uploads MAVLink Mission (Dynamic Takeoff lat=0, lon=0 + WPs + RTL)
        MAV_MGR->>Pixhawk: Programs Waypoints into Pixhawk Memory
        Browser->>Web_Mod: POST /api/mission/start
        MAV_MGR->>Pixhawk: Commands AUTO Flight Mode (Drone Takes Off Vertically)
    end
```
