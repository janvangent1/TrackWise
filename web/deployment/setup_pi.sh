#!/bin/bash
# ============================================================
# TrackWise Web — Raspberry Pi Setup Script
# ============================================================
# Run as pi user (not root) from the project directory:
#   chmod +x setup_pi.sh
#   ./setup_pi.sh
#
# This script:
#   1. Updates packages
#   2. Installs Python, nginx
#   3. Creates virtual environment
#   4. Installs Python dependencies
#   5. Configures nginx
#   6. Installs and enables systemd service
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Project directory: $PROJECT_DIR"

# ── 1. System packages ────────────────────────
echo ""
echo "==> Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y python3 python3-pip python3-venv nginx

# ── 2. Virtual environment ────────────────────
echo ""
echo "==> Creating Python virtual environment..."
VENV="$PROJECT_DIR/web/.venv"
python3 -m venv "$VENV"
source "$VENV/bin/activate"

# ── 3. Python dependencies ────────────────────
echo ""
echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$PROJECT_DIR/web/requirements.txt"

# ── 4. Nginx config ───────────────────────────
echo ""
echo "==> Configuring nginx..."

# Replace placeholder path in nginx config
NGINX_CONF="$PROJECT_DIR/web/deployment/nginx.conf"
NGINX_CONF_DEPLOYED="/etc/nginx/sites-available/trackwise"

sudo sed "s|/home/pi/trackwise|$PROJECT_DIR|g" "$NGINX_CONF" \
    | sudo tee "$NGINX_CONF_DEPLOYED" > /dev/null

sudo ln -sf "$NGINX_CONF_DEPLOYED" /etc/nginx/sites-enabled/trackwise
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
echo "nginx configured."

# ── 5. Systemd service ────────────────────────
echo ""
echo "==> Configuring systemd service..."

SERVICE_SRC="$PROJECT_DIR/web/deployment/trackwise.service"
SERVICE_DEST="/etc/systemd/system/trackwise.service"

# Replace placeholder paths with real paths
sudo sed "s|/home/pi/trackwise|$PROJECT_DIR|g; s|User=pi|User=$(whoami)|g" \
    "$SERVICE_SRC" | sudo tee "$SERVICE_DEST" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable trackwise
sudo systemctl start trackwise

echo ""
echo "==> Checking service status..."
sudo systemctl status trackwise --no-pager

echo ""
echo "============================================================"
echo "  TrackWise Web is installed and running!"
echo ""
echo "  Access via:   http://$(hostname -I | awk '{print $1}')"
echo "  Service logs: sudo journalctl -u trackwise -f"
echo "  Nginx logs:   sudo tail -f /var/log/nginx/error.log"
echo "============================================================"
