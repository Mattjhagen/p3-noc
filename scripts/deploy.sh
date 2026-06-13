#!/usr/bin/env bash
# ==============================================================================
# P3 NOC - Production Deployment Script
# ==============================================================================
set -euo pipefail

echo "=== Starting P3 NOC Deployment ==="

# 1. Create target directory
echo "Creating /opt/p3-noc..."
mkdir -p /opt/p3-noc

# 2. Copy code files from user workspace
echo "Copying files to /opt/p3-noc..."
cp -a /home/matty/p3-noc/. /opt/p3-noc/

# 3. Ensure permissions
echo "Setting permissions..."
chown -R matty:matty /opt/p3-noc

# 4. Copy launcher to /usr/local/bin
echo "Installing p3noc launcher..."
cp /opt/p3-noc/p3noc /usr/local/bin/p3noc
chmod +x /usr/local/bin/p3noc

# 5. Create systemd services
echo "Installing systemd service files..."

# 5a. BTC Monitor Service
cat <<EOF > /etc/systemd/system/p3-btc-monitor.service
[Unit]
Description=P3 NOC Bitcoin Core Node Monitor Service
After=network.target

[Service]
Type=simple
User=matty
WorkingDirectory=/opt/p3-noc
ExecStart=/opt/p3-noc/.venv/bin/python3 btc_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 5b. Dashboard Service
cat <<EOF > /etc/systemd/system/p3-dashboard.service
[Unit]
Description=P3 NOC Bitcoin Intelligence Dashboard
After=network.target postgresql.service p3-btc-monitor.service
Wants=postgresql.service p3-btc-monitor.service

[Service]
Type=simple
User=matty
WorkingDirectory=/opt/p3-noc
ExecStart=/opt/p3-noc/.venv/bin/python3 dashboard.py --wallboard
StandardInput=tty
StandardOutput=tty
StandardError=journal
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

# Environment setup
Environment=TERM=xterm-256color
Environment=LANG=en_US.UTF-8
Environment=LC_ALL=en_US.UTF-8
EnvironmentFile=-/opt/p3-noc/.env

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 5c. TTY Rotator Service
cat <<EOF > /etc/systemd/system/p3-tty-rotator.service
[Unit]
Description=P3 NOC TTY Console Rotator
After=multi-user.target postgresql.service getty@tty1.service getty@tty2.service p3-dashboard.service
Wants=postgresql.service getty@tty1.service getty@tty2.service p3-dashboard.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/p3-noc
ExecStart=/opt/p3-noc/.venv/bin/python3 services/tty_rotator.py
EnvironmentFile=-/opt/p3-noc/.env

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 6. Reload and start services
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling services..."
systemctl enable p3-btc-monitor.service
systemctl enable p3-dashboard.service
systemctl enable p3-tty-rotator.service

echo "Starting services..."
systemctl restart p3-btc-monitor.service
systemctl restart p3-dashboard.service
systemctl restart p3-tty-rotator.service

echo "=== P3 NOC Deployment Completed Successfully ==="
