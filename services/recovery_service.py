import sys
import subprocess
import requests
import psycopg2
import logging
from config.settings import OLLAMA_URL, DATABASE_URL, SERVICE_WORKER, SERVICE_INGEST, OLLAMA_REMOTE

logger = logging.getLogger("dashboard")

class RecoveryService:
    def __init__(self, db_service=None):
        self.db_service = db_service
        self.ollama_url = OLLAMA_URL
        self.db_url = DATABASE_URL

    def restart_worker(self) -> bool:
        """Restart systemd worker service. Simulates on non-Linux."""
        if sys.platform.startswith("linux"):
            try:
                cmd = ["sudo", "-n", "systemctl", "restart", SERVICE_WORKER]
                logger.info(f"Executing subprocess: {cmd}")
                subprocess.run(cmd, check=True)
                logger.info("systemctl: restarted bitcoin-worker")
                return True
            except Exception as e:
                logger.error(f"Failed to restart worker: {e}")
                return False
        else:
            logger.info("SIMULATION: restarted bitcoin-worker service")
            return True

    def restart_ingest(self) -> bool:
        """Restart systemd RSS ingest timer. Simulates on non-Linux."""
        timer_name = SERVICE_INGEST if SERVICE_INGEST.endswith(".timer") else f"{SERVICE_INGEST}.timer"
        if sys.platform.startswith("linux"):
            try:
                # User specified restarting the timer unit
                cmd = ["sudo", "-n", "systemctl", "restart", timer_name]
                logger.info(f"Executing subprocess: {cmd}")
                subprocess.run(cmd, check=True)
                logger.info(f"systemctl: restarted {timer_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to restart RSS ingest timer: {e}")
                return False
        else:
            logger.info(f"SIMULATION: restarted {timer_name}")
            return True

    def restart_ollama(self) -> bool:
        """Restart systemd ollama service and verify endpoint. Simulates on non-Linux."""
        if OLLAMA_REMOTE:
            logger.warning("Recovery: Cannot restart Ollama because it is remote.")
            return False
        if sys.platform.startswith("linux"):
            try:
                cmd = ["sudo", "-n", "systemctl", "restart", "ollama"]
                logger.info(f"Executing subprocess: {cmd}")
                subprocess.run(cmd, check=True)
                logger.info("systemctl: restarted ollama service")
            except Exception as e:
                logger.error(f"Failed to restart ollama service: {e}")
                return False
        else:
            logger.info("SIMULATION: restarted ollama service")

        # Verify service health
        try:
            res = requests.get(f"{self.ollama_url}/api/tags", timeout=5.0)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check after restart failed: {e}")
            return False

    def warm_model(self, model_name: str) -> bool:
        """
        Preload active model into RAM.
        POST /api/generate with ping prompt.
        """
        try:
            url = f"{self.ollama_url}/api/generate"
            payload = {
                "model": model_name,
                "prompt": "ping",
                "stream": False
            }
            # Short timeout since it's just a warm-up ping
            res = requests.post(url, json=payload, timeout=15.0)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Model warmup failed: {e}")
            return False

    def requeue_failed(self) -> bool:
        """Requeue failed queue items in database."""
        conn = None
        try:
            conn = psycopg2.connect(self.db_url, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE processing_queue
                    SET status = 'pending',
                        retry_count = 0,
                        last_error = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status IN ('failed', 'dead_letter');
                """)
                conn.commit()
            logger.info("Database: Requeued failed jobs.")
            return True
        except Exception as e:
            logger.error(f"Failed to requeue failed jobs: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def clear_stuck_processing(self) -> bool:
        """Mark stuck processing jobs (>15 mins) as failed."""
        conn = None
        try:
            conn = psycopg2.connect(self.db_url, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE processing_queue
                    SET status = 'failed',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'processing'
                      AND updated_at < NOW() - INTERVAL '15 minutes';
                """)
                conn.commit()
            logger.info("Database: Cleared stuck processing items.")
            return True
        except Exception as e:
            logger.error(f"Failed to clear stuck processing items: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def execute_health_recovery(self, model_name: str) -> list:
        """
        Execute full operational recovery checklist:
        1. Check PostgreSQL
        2. Check Ollama API (restart if unreachable)
        3. Restart bitcoin-worker
        4. Verify RSS ingest timer
        5. Clear stuck jobs
        6. Requeue failed jobs
        7. Run model warmup
        
        Returns: list of (step_name, success_bool)
        """
        steps = []
        
        # 1. Check PostgreSQL
        db_ok = False
        try:
            conn = psycopg2.connect(self.db_url, connect_timeout=3)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            db_ok = True
            conn.close()
        except Exception:
            pass
        steps.append(("Database", db_ok))

        # 2. Check Ollama API
        ollama_ok = False
        try:
            res = requests.get(f"{self.ollama_url}/api/tags", timeout=3.0)
            ollama_ok = res.status_code == 200
        except Exception:
            pass
        
        # 3. Restart Ollama if unreachable
        if not ollama_ok:
            if OLLAMA_REMOTE:
                logger.warning("Recovery: Remote Ollama is offline. Skipping systemctl restart.")
            else:
                logger.warning("Recovery: Ollama unreachable. Restarting Ollama...")
                ollama_ok = self.restart_ollama()
        steps.append(("Ollama", ollama_ok))

        # 4. Restart bitcoin-worker
        worker_ok = self.restart_worker()
        steps.append(("Worker", worker_ok))

        # 5. Verify RSS ingest timer (restarts timer)
        ingest_ok = self.restart_ingest()
        steps.append(("RSS Feed", ingest_ok))

        # 6. Clear stuck jobs
        clear_ok = self.clear_stuck_processing()
        steps.append(("Queue Cleanup", clear_ok))

        # 7. Requeue failed jobs
        requeue_ok = self.requeue_failed()
        steps.append(("Requeue Failed", requeue_ok))

        # 8. Run model warmup
        warmup_ok = self.warm_model(model_name)
        steps.append(("Model Warmup", warmup_ok))

        return steps
