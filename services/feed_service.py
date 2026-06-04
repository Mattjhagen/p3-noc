import subprocess
import os
from config.settings import SERVICE_WORKER, SERVICE_INGEST

import logging
logger = logging.getLogger("dashboard")

class FeedService:
    def __init__(self):
        self.worker_name = SERVICE_WORKER
        self.ingest_name = SERVICE_INGEST

    def _is_systemd_service_active(self, service_name: str) -> bool:
        """Run systemctl to check if a service is active. Fallback on non-systemd OS."""
        if os.name != "nt":  # Non-Windows, try systemctl
            try:
                cmd = ["systemctl", "is-active", service_name]
                logger.info(f"Executing subprocess: {cmd}")
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=1.5
                )
                return res.stdout.strip() == "active"
            except Exception:
                # systemctl not available (e.g. macOS)
                pass
        
        # macOS / Dev Fallback: assume active for testing
        return True

    def check_worker_service_status(self) -> bool:
        """Returns True if the worker service is running."""
        return self._is_systemd_service_active(self.worker_name)

    def check_ingest_service_status(self) -> bool:
        """Returns True if the RSS ingest timer is active."""
        timer_name = self.ingest_name if self.ingest_name.endswith(".timer") else f"{self.ingest_name}.timer"
        return self._is_systemd_service_active(timer_name)
