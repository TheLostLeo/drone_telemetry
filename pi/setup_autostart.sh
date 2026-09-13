#!/usr/bin/env bash
# ======================================================================================
# Setup Script: Install & Enable Drone Telemetry Service on Raspberry Pi Boot
# ======================================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$CURRENT_USER")
SERVICE_NAME="drone-telemetry.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

# Detect Python interpreter (prefer virtualenv if exists, otherwise system python3)
if [ -f "${SCRIPT_DIR}/venv/bin/python3" ]; then
    PYTHON_EXEC="${SCRIPT_DIR}/venv/bin/python3"
elif [ -f "${USER_HOME}/drone_telemetry/pi/venv/bin/python3" ]; then
    PYTHON_EXEC="${USER_HOME}/drone_telemetry/pi/venv/bin/python3"
else
    PYTHON_EXEC="$(which python3)"
fi

echo "=============================================================="
echo "    Drone Telemetry - Auto-Start Setup (systemd service)      "
echo "=============================================================="
echo "[*] User:            ${CURRENT_USER}"
echo "[*] Working Dir:     ${SCRIPT_DIR}"
echo "[*] Python Exec:     ${PYTHON_EXEC}"
echo "[*] Service Target:  ${SERVICE_PATH}"
echo "--------------------------------------------------------------"

# Generate systemd service file with detected dynamic paths
cat << SERVICE_EOF | sudo tee "${SERVICE_PATH}" > /dev/null
[Unit]
Description=Drone Telemetry NRF24 Transmitter Service
After=network.target local-fs.target
Wants=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_EXEC} ${SCRIPT_DIR}/pixhawk_telemetry_tx.py --port /dev/serial0 --baud 115200
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE_EOF

echo "[+] Service file created at ${SERVICE_PATH}."

# Reload systemd, enable and start service
echo "[*] Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "[*] Enabling ${SERVICE_NAME} to start automatically on boot..."
sudo systemctl enable "${SERVICE_NAME}"

echo "[*] Starting ${SERVICE_NAME} now..."
sudo systemctl restart "${SERVICE_NAME}"

echo ""
echo "=============================================================="
echo "    ✓ Auto-Start Setup Completed Successfully!                "
echo "=============================================================="
echo "Useful Commands:"
echo "  • Check Live Status:    sudo systemctl status ${SERVICE_NAME}"
echo "  • View Real-Time Logs:  journalctl -u ${SERVICE_NAME} -f"
echo "  • Stop Service:         sudo systemctl stop ${SERVICE_NAME}"
echo "  • Restart Service:      sudo systemctl restart ${SERVICE_NAME}"
echo "=============================================================="
