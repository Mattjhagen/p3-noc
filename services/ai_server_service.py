import os
import sys
import time
import socket
import subprocess
import requests
import logging
from config.settings import AI_SERVER_IP, AI_SERVER_HOST, OLLAMA_PORT

logger = logging.getLogger("dashboard")

class AiServerService:
    def __init__(self):
        self.ip = AI_SERVER_IP
        self.host = AI_SERVER_HOST
        self.ollama_port = OLLAMA_PORT
        self.ollama_url = f"http://{self.ip}:{self.ollama_port}/api/tags"

    def ping_host(self) -> (bool, float):
        """
        Pings R510 remote host.
        Returns (is_reachable, latency_ms)
        """
        start = time.time()
        try:
            # -c 1 sends 1 packet.
            # -t 1 (macOS) or -W 1 (Linux) sets timeout to 1 second.
            if sys.platform.startswith("darwin"):
                cmd = ["ping", "-c", "1", "-t", "1", self.ip]
            else:
                cmd = ["ping", "-c", "1", "-W", "1", self.ip]
            
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
            latency = (time.time() - start) * 1000.0
            return (res.returncode == 0), latency
        except Exception as e:
            logger.debug(f"Ping failed for AI Server {self.ip}: {e}")
            return False, 0.0

    def verify_ssh(self) -> bool:
        """
        Checks port 22 connectivity on R510.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((self.ip, 22))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"SSH check failed for AI Server {self.ip}: {e}")
            return False

    def verify_ollama(self) -> bool:
        """
        Pings R510 Ollama api/tags endpoint.
        """
        try:
            res = requests.get(self.ollama_url, timeout=1.5)
            return res.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama endpoint check failed for AI Server {self.ip}: {e}")
            return False

    def verify_ollama_port(self) -> bool:
        """
        Checks TCP port 11434 connectivity on R510.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((self.ip, int(self.ollama_port)))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"Ollama port check failed for AI Server {self.ip}: {e}")
            return False

    def perform_full_check(self) -> dict:
        """
        Executes ping, SSH, and Ollama checks.
        Computes overall status: GREEN, YELLOW, RED.
        """
        ping_ok, ping_lat = self.ping_host()
        ssh_ok = self.verify_ssh()
        ollama_port_ok = self.verify_ollama_port()
        ollama_ok = self.verify_ollama()

        # GREEN: R510 reachable, SSH reachable, Ollama reachable
        # YELLOW: R510 reachable, SSH reachable, Ollama offline
        # RED: R510 unreachable (or SSH unreachable)
        if not ping_ok or not ssh_ok:
            status = "RED"
        elif not ollama_ok:
            status = "YELLOW"
        else:
            status = "GREEN"

        return {
            "status": status,
            "ping_ok": ping_ok,
            "ping_latency": ping_lat if ping_ok else 0.0,
            "ssh_ok": ssh_ok,
            "ollama_port_ok": ollama_port_ok,
            "ollama_ok": ollama_ok,
            "timestamp": time.time()
        }
