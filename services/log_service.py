import subprocess
import os
import random
from datetime import datetime, timedelta

class LogService:
    def __init__(self, service_name="bitcoin-worker"):
        self.service_name = service_name
        self.mock_logs = []
        self.last_mock_time = datetime.now() - timedelta(minutes=10)
        self._initialize_mock_logs()

    def _initialize_mock_logs(self):
        """Pre-populate with some initial mock logs."""
        curr_time = self.last_mock_time
        actions = [
            ("INFO", "[main] Starting P3 Command Center Worker Daemon..."),
            ("INFO", "[database] Connecting to PostgreSQL at localhost:5432..."),
            ("INFO", "[database] Connection established successfully."),
            ("INFO", "[ollama] Connecting to Ollama server at 192.168.1.47:11434..."),
            ("INFO", "[ollama] Ollama model 'qwen2.5:8b' confirmed online."),
            ("INFO", "[main] Ingest worker listening to RSS feeds: Coindesk, Blockworks, Bitcoin Magazine."),
            ("INFO", "[main] Processing queue started, checking for pending jobs..."),
            ("INFO", "[main] Processing article 10: 'BlackRock ETF inflows continue'"),
            ("INFO", "[ollama] Sending prompt to Ollama model qwen2.5:8b..."),
            ("INFO", "[ollama] Response received in 188.4s. Tokens: 412."),
            ("INFO", "[database] Saved analysis output for article 10."),
            ("INFO", "[main] Queue item 10 completed."),
            ("INFO", "[main] Processing article 11: 'Miner capitulation increases'"),
            ("INFO", "[ollama] Sending prompt to Ollama model qwen2.5:8b..."),
            ("WARNING", "[ollama] Ollama timeout on attempt 1. Connection dropped."),
            ("INFO", "[main] Retrying article 11 in 5 seconds..."),
            ("INFO", "[ollama] Sending prompt to Ollama model qwen2.5:8b (attempt 2)..."),
            ("INFO", "[ollama] Response received in 231.2s. Tokens: 388."),
            ("INFO", "[database] Saved analysis output for article 11."),
            ("INFO", "[main] Queue item 11 completed."),
            ("INFO", "[main] Processing article 12: 'Exchange insolvency concerns emerge'"),
            ("INFO", "[ollama] Sending prompt to Ollama model qwen2.5:8b..."),
            ("CRITICAL", "[ollama] Ollama connection refused at 192.168.1.47:11434! R510 offline?"),
            ("WARNING", "[main] Circuit Breaker: 1 consecutive Ollama failure detected."),
            ("INFO", "[main] Retrying article 12 in 10 seconds..."),
        ]
        
        for level, msg in actions:
            # Shift time forward slightly
            curr_time += timedelta(seconds=random.randint(15, 60))
            self.mock_logs.append(self._format_log_line(curr_time, level, msg))
            
        self.last_mock_time = curr_time

    def _format_log_line(self, timestamp: datetime, level: str, message: str) -> str:
        return f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} {level:<8} {message}"

    def _generate_new_mock_logs(self):
        """Generate some random logs to simulate real-time activity."""
        now = datetime.now()
        seconds_passed = (now - self.last_mock_time).total_seconds()
        
        # Only add new logs if at least 5 seconds have passed
        if seconds_passed < 5:
            return
            
        num_new = random.randint(0, 2)
        level_choices = ["INFO", "INFO", "INFO", "INFO", "WARNING", "INFO", "INFO", "ERROR"]
        messages = {
            "INFO": [
                "[main] Heartbeat check: Worker processing thread active.",
                "[database] Database vacuum completed successfully.",
                "[main] RSS Feed poll complete. 0 new articles found.",
                "[main] Processing queue check: no pending articles.",
                "[ollama] Cached hit for article. Skipping LLM query.",
                "[database] Connection pool refreshed."
            ],
            "WARNING": [
                "[ollama] Latency spike detected: request took 245 seconds.",
                "[ingest] Feed Cointelegraph failed to respond within timeout. Retrying...",
                "[main] Worker retry count incremented for article 14."
            ],
            "ERROR": [
                "[database] Connection dropped by server. Attempting reconnect...",
                "[ollama] Timeout waiting for Ollama response (limit 120s)."
            ]
        }
        
        curr_time = self.last_mock_time
        for _ in range(num_new):
            curr_time += timedelta(seconds=random.randint(2, int(seconds_passed) // (num_new + 1) + 2))
            # Keep timestamp capped at now
            if curr_time > now:
                curr_time = now
            level = random.choice(level_choices)
            msg = random.choice(messages[level])
            self.mock_logs.append(self._format_log_line(curr_time, level, msg))
            
        self.last_mock_time = now
        
        # Keep logs under 500 lines to save memory
        if len(self.mock_logs) > 500:
            self.mock_logs = self.mock_logs[-500:]

    def fetch_worker_logs(self, lines=100) -> list:
        """
        Fetch the latest N lines of worker logs.
        Attempts to use journalctl, falls back to mock logs.
        """
        import logging
        logger = logging.getLogger("dashboard")
        # Attempt to run journalctl if on Linux
        if os.name != "nt":  # Not Windows, let's try running systemctl
            try:
                # Check if journalctl is available by testing it
                cmd = ["journalctl", "-u", self.service_name, "-n", str(lines), "--no-pager"]
                logger.info(f"Executing subprocess: {cmd}")
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if res.returncode == 0:
                    lines_list = res.stdout.strip().split("\n")
                    # Filter out empty lines
                    return [l for l in lines_list if l.strip()]
            except Exception:
                # journalctl not available or errored out (e.g. macOS)
                pass
                
        # Fallback to simulated logs
        self._generate_new_mock_logs()
        return self.mock_logs[-lines:]
