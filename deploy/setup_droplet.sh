#!/usr/bin/env bash
# ==============================================================================
# 1-Click DigitalOcean Droplet Provisioning Script for On-Chain Momentum Scanner
# ==============================================================================
set -e

echo "=== [1/5] Updating packages and installing dependencies ==="
apt-get update && apt-get upgrade -y
apt-get install -y git python3 python3-pip python3-venv sqlite3 curl

INSTALL_DIR="/opt/onchain-momentum-scanner"

if [ ! -d "$INSTALL_DIR" ]; then
    echo "=== [2/5] Creating installation directory at $INSTALL_DIR ==="
    mkdir -p "$INSTALL_DIR"
fi

echo "=== [3/5] Setting up Python virtual environment ==="
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo "=== [4/5] Installing systemd service ==="
cp "$INSTALL_DIR/deploy/onchain-momentum.service" /etc/systemd/system/onchain-momentum.service
systemctl daemon-reload

echo "=== [5/5] Ready! ==="
echo "Next steps:"
echo "1. Edit your .env file: nano $INSTALL_DIR/.env"
echo "2. Start the service: systemctl start onchain-momentum"
echo "3. Enable service on boot: systemctl enable onchain-momentum"
echo "4. Check logs: journalctl -u onchain-momentum -f"
echo "5. Run evaluator anytime: cd $INSTALL_DIR && ./venv/bin/python -m src.evaluator"
