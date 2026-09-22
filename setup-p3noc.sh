#!/bin/bash
# P3NOC Setup Script - Run with sudo

set -e

echo "======================================================"
echo "  P3 NOC Dashboard - System Setup"
echo "======================================================"

# 1. Create p3noc command
echo "[1/4] Installing p3noc command..."
cat > /usr/local/bin/p3noc << 'EOF'
#!/bin/bash
cd /home/matt/P3_Official/P3-NOC-Web
exec .venv/bin/python dashboard.py --wallboard
EOF
chmod +x /usr/local/bin/p3noc
echo "  ✓ p3noc command installed to /usr/local/bin/p3noc"

# 2. Configure auto-login for TTY1
echo "[2/4] Configuring auto-login on TTY1..."
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin matt --noclear %I $TERM
EOF
echo "  ✓ Auto-login configured for user 'matt' on TTY1"

# 3. Create systemd service for dashboard
echo "[3/4] Installing systemd service..."
cat > /etc/systemd/system/p3noc.service << 'EOF'
[Unit]
Description=P3 NOC Bitcoin Intelligence Dashboard
After=getty@tty1.service
Wants=getty@tty1.service

[Service]
Type=simple
User=matt
WorkingDirectory=/home/matt/P3_Official/P3-NOC-Web
ExecStartPre=/bin/sleep 5
ExecStart=/usr/local/bin/p3noc
StandardInput=tty
StandardOutput=tty
StandardError=journal
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

Environment=TERM=xterm-256color
Environment=LANG=en_US.UTF-8
Environment=LC_ALL=en_US.UTF-8

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
echo "  ✓ Systemd service created at /etc/systemd/system/p3noc.service"

# 4. Enable and start services
echo "[4/4] Enabling services..."
systemctl daemon-reload
systemctl enable p3noc.service
echo "  ✓ p3noc.service enabled for auto-start on boot"

echo ""
echo "======================================================"
echo "  Setup Complete!"
echo "======================================================"
echo ""
echo "Commands:"
echo "  p3noc                           - Run dashboard manually"
echo "  sudo systemctl start p3noc      - Start dashboard service now"
echo "  sudo systemctl stop p3noc       - Stop dashboard service"
echo "  sudo systemctl status p3noc     - Check dashboard status"
echo ""
echo "On next reboot:"
echo "  → TTY1 will auto-login as 'matt'"
echo "  → P3NOC dashboard will auto-start on TTY1"
echo "  → Press Ctrl+Alt+F1 to view the dashboard"
echo ""
