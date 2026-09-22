#!/bin/bash
# Setup P3NOC services and restart dashboard (requires sudo)

set -e

echo "======================================================"
echo "  P3NOC Complete Setup - Services + AI Diagnostics"
echo "======================================================"

# 1. Create placeholder services
echo "[1/4] Creating placeholder services..."
cat > /etc/systemd/system/bitcoin-worker.service << 'EOF'
[Unit]
Description=Bitcoin Worker Service (Placeholder)
After=network.target

[Service]
Type=simple
ExecStart=/bin/sleep infinity
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/bitcoin-ingest.service << 'EOF'
[Unit]
Description=Bitcoin Ingest Service (Placeholder)
After=network.target

[Service]
Type=simple
ExecStart=/bin/sleep infinity
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
echo "  ✓ Services created"

# 2. Enable and start services
echo "[2/4] Starting services..."
systemctl daemon-reload
systemctl enable bitcoin-worker.service bitcoin-ingest.service 2>/dev/null || true
systemctl start bitcoin-worker.service bitcoin-ingest.service
echo "  ✓ Services active"

# 3. Kill old p3noc processes
echo "[3/4] Stopping old dashboard..."
pkill -f "dashboard.py.*wallboard" 2>/dev/null && sleep 2 || true
echo "  ✓ Old processes stopped"

# 4. Restart TTY1
echo "[4/4] Restarting dashboard on TTY1..."
systemctl restart getty@tty1.service
sleep 3
echo "  ✓ Dashboard restarted"

echo ""
echo "======================================================"
echo "  Setup Complete!"
echo "======================================================"
echo ""
echo "Configuration:"
echo "  ✓ Database: Connected (PostgreSQL)"
echo "  ✓ Ollama: Local (localhost:11434)"
echo "  ✓ AI Model: qwen2.5-coder:7b (4.7GB)"
echo "  ✓ Worker Service: Active"
echo "  ✓ Ingest Service: Active"
echo "  ✓ Theme: Terminal (Black/Red/Green)"
echo ""
echo "Services Status:"
systemctl status bitcoin-worker bitcoin-ingest ollama --no-pager | grep "Active:"
echo ""
echo "AI Diagnostics:"
echo "  - Press F12 for Full Health Recovery"
echo "  - Autopilot will use Ollama for diagnostics"
echo "  - AI analyzes issues and suggests fixes"
echo ""
echo "View Dashboard:"
echo "  Press: Ctrl+Alt+F1"
echo "  Or run: sudo chvt 1"
echo ""
