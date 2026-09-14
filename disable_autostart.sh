#!/usr/bin/env bash
# ======================================================================================
# Disable & Remove Drone Telemetry Auto-Start Service
# Location: /storage/projects/drone_telemetry/disable_autostart.sh
# ======================================================================================

SERVICE_NAME="drone-telemetry.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

echo "[*] Stopping ${SERVICE_NAME}..."
sudo systemctl stop "${SERVICE_NAME}" 2>/dev/null || true

echo "[*] Disabling ${SERVICE_NAME} from boot..."
sudo systemctl disable "${SERVICE_NAME}" 2>/dev/null || true

if [ -f "${SERVICE_PATH}" ]; then
    echo "[*] Removing ${SERVICE_PATH}..."
    sudo rm -f "${SERVICE_PATH}"
fi

echo "[*] Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "[✓] Auto-start service disabled and removed."
