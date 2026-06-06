import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# App paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Database configurations
# Default postgres URL pointing to local/remote docker or server
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://researcher:secure_password_change_me@localhost:5432/bitcoin_research"
)

# Ollama Endpoint configurations
OLLAMA_REMOTE = os.getenv("OLLAMA_REMOTE", "true").lower() == "true"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "192.168.1.47")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
OLLAMA_HOST_NAME = os.getenv("OLLAMA_HOST_NAME", "r510")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:8b")
OLLAMA_CONTEXT_LIMIT = int(os.getenv("OLLAMA_CONTEXT_LIMIT", "40960"))

# AI Server Monitoring configurations
AI_SERVER_HOST = os.getenv("AI_SERVER_HOST", "r510")
AI_SERVER_IP = os.getenv("AI_SERVER_IP", "192.168.1.47")

# T310 connection configurations for R510 Remote Control
T310_HOST = os.getenv("T310_HOST", "p3noc")
T310_IP = os.getenv("T310_IP", "192.168.1.158")
T310_USER = os.getenv("T310_USER", "matt")

# Systemd services to monitor
SERVICE_WORKER = os.getenv("SERVICE_WORKER", "bitcoin-worker")
SERVICE_INGEST = os.getenv("SERVICE_INGEST", "bitcoin-ingest")

# Refresh rates (in seconds)
REFRESH_RATES = {
    "logs": int(os.getenv("REFRESH_LOGS", "5")),
    "db": int(os.getenv("REFRESH_DB", "10")),
    "status": int(os.getenv("REFRESH_STATUS", "5")),
    "ticker_update": float(os.getenv("REFRESH_TICKER", "0.1")), # Ticker redraw frequency
    "ticker_fetch": int(os.getenv("FETCH_TICKER", "60")), # How often to fetch BTC price
}

# Bitcoin Monitor Service configurations
BTC_MONITOR_URL = os.getenv("BTC_MONITOR_URL", "http://localhost:8000")
BTC_CLI_PATH = os.getenv("BTC_CLI_PATH", "bitcoin-cli")

