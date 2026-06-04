import requests
import logging
import psycopg2
from config.settings import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_HOST_NAME, DATABASE_URL

logger = logging.getLogger("dashboard")

class OllamaService:
    def __init__(self):
        self.url = OLLAMA_URL
        self.model_config = OLLAMA_MODEL
        self.host_config = OLLAMA_HOST_NAME
        self.db_url = DATABASE_URL
        self.local_failure_counter = 0

    def check_ollama_status(self) -> str:
        """Pings the Ollama endpoint and returns 'ONLINE' or 'OFFLINE'."""
        try:
            # Ping the base endpoint or list tags endpoint
            response = requests.get(f"{self.url}/api/tags", timeout=1.5)
            if response.status_code == 200:
                self.local_failure_counter = 0
                return "ONLINE"
            return "OFFLINE"
        except Exception as e:
            logger.warning(f"Ollama server ping failed: {e}")
            return "OFFLINE"

    def get_ollama_stats(self) -> dict:
        """
        Gathers Ollama performance metrics.
        Queries database analysis_versions table for actual metrics when possible.
        """
        stats = {
            "model": self.model_config,
            "server": self.host_config,
            "latency": "0s",
            "status": "OFFLINE",
            "requests": 0,
            "failures": 0,
            "configured_model": self.model_config,
            "loaded_model": "None"
        }

        # Check connection status
        status = self.check_ollama_status()
        stats["status"] = status

        if status == "ONLINE":
            try:
                res = requests.get(f"{self.url}/api/ps", timeout=1.0)
                if res.status_code == 200:
                    models = res.json().get("models", [])
                    if models:
                        loaded = [m.get("name", m.get("model", "Unknown")) for m in models]
                        stats["loaded_model"] = ", ".join(loaded)
                    else:
                        stats["loaded_model"] = "None"
            except Exception:
                stats["loaded_model"] = "None"

        # Query database for runtime stats
        conn = None
        try:
            conn = psycopg2.connect(self.db_url, connect_timeout=2)
            with conn.cursor() as cur:
                # 1. Fetch latest model name and latency from last request
                cur.execute("""
                    SELECT model_name, response_time_ms 
                    FROM analysis_versions 
                    ORDER BY created_at DESC 
                    LIMIT 1;
                """)
                row = cur.fetchone()
                if row:
                    model_name, response_time_ms = row
                    stats["model"] = model_name
                    stats["latency"] = f"{round(response_time_ms / 1000.0)}s"
                else:
                    stats["latency"] = "N/A"

                # 2. Fetch total requests (total analysis versions created)
                cur.execute("SELECT COUNT(*) FROM analysis_versions;")
                stats["requests"] = cur.fetchone()[0]

                # 3. Fetch failures (count of 'ollama_failures' in system_metrics in last 24h)
                cur.execute("""
                    SELECT COALESCE(SUM(metric_value), 0) 
                    FROM system_metrics 
                    WHERE metric_name = 'ollama_failures' 
                      AND recorded_at >= NOW() - INTERVAL '24 hours';
                """)
                stats["failures"] = int(cur.fetchone()[0])
        except Exception as e:
            logger.error(f"Failed to query Ollama stats from database: {e}")
            # Database offline or error, fallback to defaults or static stats
            stats["latency"] = "N/A"
            stats["requests"] = 0
            stats["failures"] = self.local_failure_counter
        finally:
            if conn:
                conn.close()

        # If offline, increment local failure count if it was online before
        if status == "OFFLINE" and stats["failures"] == 0:
            self.local_failure_counter += 1
            stats["failures"] = self.local_failure_counter

        return stats
