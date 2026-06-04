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

    def get_installed_models(self) -> list:
        """Fetch remote installed models from api/tags."""
        try:
            res = requests.get(f"http://{self.ip}:{self.ollama_port}/api/tags", timeout=1.0)
            if res.status_code == 200:
                models = res.json().get("models", [])
                return [m.get("name", m.get("model", "Unknown")) for m in models]
            return []
        except Exception:
            return []

    def get_loaded_models(self) -> list:
        """Fetch remote memory-loaded models from api/ps."""
        try:
            res = requests.get(f"http://{self.ip}:{self.ollama_port}/api/ps", timeout=1.0)
            if res.status_code == 200:
                models = res.json().get("models", [])
                return [m.get("name", m.get("model", "Unknown")) for m in models]
            return []
        except Exception:
            return []

    def perform_full_check(self) -> dict:
        """
        Executes ping, SSH, and Ollama checks.
        Computes overall status: GREEN, YELLOW, RED.
        """
        ping_ok, ping_lat = self.ping_host()
        
        # Fast path if ping fails to avoid long timeouts
        if not ping_ok:
            return {
                "status": "RED",
                "ping_ok": False,
                "ping_latency": 0.0,
                "ssh_ok": False,
                "ollama_port_ok": False,
                "ollama_ok": False,
                "installed_models": [],
                "loaded_models": [],
                "timestamp": time.time()
            }

        ssh_ok = self.verify_ssh()
        ollama_port_ok = self.verify_ollama_port()
        ollama_ok = self.verify_ollama()

        installed_models = []
        loaded_models = []
        if ollama_ok:
            installed_models = self.get_installed_models()
            loaded_models = self.get_loaded_models()

        if not ssh_ok:
            status = "RED"
        elif not ollama_ok:
            status = "YELLOW"
        else:
            status = "GREEN"

        return {
            "status": status,
            "ping_ok": ping_ok,
            "ping_latency": ping_lat,
            "ssh_ok": ssh_ok,
            "ollama_port_ok": ollama_port_ok,
            "ollama_ok": ollama_ok,
            "installed_models": installed_models,
            "loaded_models": loaded_models,
            "timestamp": time.time()
        }
