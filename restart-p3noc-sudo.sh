#!/bin/bash
# Restart P3NOC (requires sudo)

echo "======================================================"
echo "  Restarting P3NOC Dashboard"
echo "======================================================"

# 1. Kill existing dashboard processes
echo "[1/2] Stopping old p3noc processes..."
pkill -f "dashboard.py.*wallboard" 2>/dev/null && echo "  ✓ Killed old processes" || echo "  ℹ No old processes running"
sleep 2

# 2. Restart TTY1 to trigger auto-login and p3noc
echo "[2/2] Restarting TTY1..."
systemctl restart getty@tty1.service
sleep 3

echo ""
echo "======================================================"
echo "  P3NOC Restarted!"
echo "======================================================"
echo ""
echo "Configuration:"
echo "  Theme: Terminal (Black/Red/Green)"
echo "  Database: postgresql://p3user@localhost:5432/p3lending"
echo "  Ollama: http://192.168.1.47:11434"
echo ""
echo "View dashboard:"
echo "  Press: Ctrl+Alt+F1"
echo "  Or run: sudo chvt 1"
echo ""
echo "Keyboard shortcuts:"
echo "  F2  - Cycle themes"
echo "  F5  - Refresh data"
echo "  q   - Quit"
echo ""
