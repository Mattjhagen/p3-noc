#!/usr/bin/env bash
# ==============================================================================
# P3 Operations Center - Provisioning & Deployment Script
# Designed for Ubuntu / Debian Server running on Dell T310
# ==============================================================================

set -euo pipefail

# Style formats
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0;41m' # No Color
RESET='\033[0m'

echo -e "${CYAN}=====================================================${RESET}"
echo -e "${CYAN}    P3 OPERATIONS CENTER - WEB INFRASTRUCTURE        ${RESET}"
echo -e "${CYAN}              PROVISIONING SYSTEM                    ${RESET}"
echo -e "${CYAN}=====================================================${RESET}"

# 1. System Requirements Validation
echo -e "\n${CYAN}[1/4] Auditing system requirements...${RESET}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed on this system.${RESET}"
    echo -e "Please install Docker first: https://docs.docker.com/engine/install/"
    exit 1
fi
echo -e "  - Docker: ${GREEN}OK${RESET}"

if ! docker compose version &> /dev/null; then
    echo -e "${RED}ERROR: Docker Compose is not installed or too old.${RESET}"
    echo -e "Please install docker-compose-plugin."
    exit 1
fi
echo -e "  - Docker Compose: ${GREEN}OK${RESET}"

# 2. Config Files Generation
echo -e "\n${CYAN}[2/4] Initializing configuration parameters...${RESET}"
if [ ! -f .env ]; then
    echo "Creating default environment file (.env)..."
    cat <<EOF > .env
DATABASE_URL=postgresql://researcher:secure_password_change_me@postgres:5432/bitcoin_research
SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || echo "p3-operations-center-super-secure-secret-key-change-me")
OLLAMA_HOST=192.168.1.47
OLLAMA_PORT=11434
AI_SERVER_IP=192.168.1.47
EOF
    echo -e "  - .env generation: ${GREEN}CREATED${RESET}"
else
    echo -e "  - .env configuration: ${YELLOW}ALREADY EXISTS (skipped)${RESET}"
fi

# 3. Provisioning Docker Stack
echo -e "\n${CYAN}[3/4] Spinning up multi-container docker services...${RESET}"
echo "Building and starting containers in background..."
docker compose up --build -d

echo -e "  - Container services: ${GREEN}UP AND RUNNING${RESET}"

# 4. Systemd service registration
echo -e "\n${CYAN}[4/4] Configuring systemd auto-boot on T310...${RESET}"
SERVICE_PATH="/etc/systemd/system/p3-noc-web.service"
WORK_DIR=$(pwd)

cat <<EOF > p3-noc-web.service
[Unit]
Description=P3 Infrastructure NOC Operations Center Web Stack
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=${WORK_DIR}
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo -e "Created systemd service file template: ${GREEN}p3-noc-web.service${RESET}"
echo -e "To register the auto-boot service, run the following commands:"
echo -e "  ${YELLOW}sudo cp p3-noc-web.service ${SERVICE_PATH}${RESET}"
echo -e "  ${YELLOW}sudo systemctl daemon-reload${RESET}"
echo -e "  ${YELLOW}sudo systemctl enable p3-noc-web.service${RESET}"
echo -e "  ${YELLOW}sudo systemctl start p3-noc-web.service${RESET}"

echo -e "\n${GREEN}=====================================================${RESET}"
echo -e "${GREEN}      DEPLOYMENT PROVISIONING COMPLETED               ${RESET}"
echo -e "${GREEN}      Operations center reachable on:                 ${RESET}"
echo -e "${GREEN}      LOCAL: http://localhost:8080                    ${RESET}"
echo -e "${GREEN}      REMOTE: Access via Tailscale IP on port 8080    ${RESET}"
echo -e "${GREEN}=====================================================${RESET}"
