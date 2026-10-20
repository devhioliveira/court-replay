#!/bin/bash
# Installation script for Court Replay Agent on Linux
set -e

INSTALL_DIR="/opt/court-replay"
SERVICE_NAME="court-replay-agent"
USER_NAME="courtreplay"

echo "=== Court Replay Agent Installer ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Install system dependencies
echo "[1/6] Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-venv python3-pip ffmpeg

# Create user
echo "[2/6] Creating service user..."
if ! id "$USER_NAME" &>/dev/null; then
  useradd -r -s /bin/false -d "$INSTALL_DIR" "$USER_NAME"
fi
# Needed to read the mouse (/dev/input/event*) for the middle-button trigger.
usermod -aG input "$USER_NAME"

# Create directories
echo "[3/6] Setting up directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p /etc/court-replay
mkdir -p /var/log/court-replay
mkdir -p "$INSTALL_DIR/storage" "$INSTALL_DIR/logs"

# Copy files
echo "[4/6] Copying application files..."
cp -r agent/ server/ requirements.txt "$INSTALL_DIR/"
cp example-config.json "$INSTALL_DIR/config.json"
cp .env.example /etc/court-replay/env

# Set permissions
chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR"
chmod 600 /etc/court-replay/env

# Create virtual environment
echo "[5/6] Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# Install systemd service
echo "[6/6] Installing systemd service..."
cp scripts/court-replay-agent.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit /etc/court-replay/env with your configuration"
echo "  2. Edit $INSTALL_DIR/config.json with your settings"
echo "  3. Start the service: sudo systemctl start $SERVICE_NAME"
echo "  4. Check status: sudo systemctl status $SERVICE_NAME"
echo "  5. View logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "Default login: admin / admin123"
echo "IMPORTANT: Change the default password immediately!"
