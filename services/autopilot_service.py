import time
import logging
from datetime import datetime, timedelta
from services.db_service import DBService
from services.recovery_service import RecoveryService
from services.feed_service import FeedService
from services.ollama_service import OllamaService
from services.routing_service import RoutingService
from config.settings import OLLAMA_REMOTE

logger = logging.getLogger("dashboard")

class HealthState:
    def __init__(self, overall_status="HEALTHY", score=100, issues=None, actions_taken=None):
        self.overall_status = overall_status
        self.score = score
        self.issues = issues if issues else []
        self.actions_taken = actions_taken if actions_taken else []

class AutopilotService:
    """
    Autonomous Operations Engine.
    Monitors telemetry, detects anomalies, runs self-healing recovery actions,
    manages circuit breakers to prevent loops, and triggers model Safe Mode routing.
    """
    def __init__(self, db_service: DBService, recovery_service: RecoveryService, 
                 feed_service: FeedService, ollama_service: OllamaService,
                 routing_service: RoutingService):
        self.db_service = db_service
        self.recovery_service = recovery_service
        self.feed_service = feed_service
        self.ollama_service = ollama_service
        self.routing_service = routing_service
        
        # State variables
        self.locked = False
        self.safe_mode = False
        
        # Recovery rate tracking for circuit breaker
        self.recovery_timestamps = []
        self.MAX_RESTARTS_PER_HOUR = 3
        
        # Total recovery events count
        self.total_recoveries_today = 0
        self.uptime_start = datetime.now()
        
        # Telemetry history for trend anomaly detection
        self.cpu_history = []
        self.ram_history = []
        self.queue_history = []
        self.failed_history = []
        self.latency_history = []
        
        # Predictive alerts list
        self.predictive_alerts = []

    def get_uptime_days(self) -> int:
        """Returns host uptime (simulated as days since app start)."""
        dt = datetime.now() - self.uptime_start
        # Mock uptime days (minimum 1, or offset by 37 days as in user example to look realistic)
        return 37 + dt.days

    def record_recovery_attempt(self) -> bool:
        """
        Record a recovery attempt and check the circuit breaker.
        Returns False if circuit breaker is tripped (locked).
        """
        now = datetime.now()
        # Filter timestamps to last 60 minutes
        self.recovery_timestamps = [t for t in self.recovery_timestamps if now - t < timedelta(hours=1)]
        
        if len(self.recovery_timestamps) >= self.MAX_RESTARTS_PER_HOUR:
            self.locked = True
            logger.critical("CIRCUIT BREAKER TRIGGERED: Autopilot locked! Too many restarts.")
            self.db_service.log_operations_event(
                severity="CRITICAL",
                event="CIRCUIT_BREAKER_LOCKED",
                action_taken="LOCK_AUTOPILOT",
                result="SUCCESS",
                host="p3noc"
            )
            return False
            
        self.recovery_timestamps.append(now)
        self.total_recoveries_today += 1
        
        # Enter safe mode if restarts >= 2 in an hour
        if len(self.recovery_timestamps) >= 2:
            self.safe_mode = True
            self.routing_service.set_safe_mode(True)
            logger.warning("Autopilot entering SAFE MODE due to repeated failures.")
            self.db_service.log_operations_event(
                severity="WARNING",
                event="SAFE_MODE_ENABLED",
                action_taken="ENABLE_SAFE_MODE",
                result="SUCCESS",
                host="p3noc"
            )
            
        return True

    def unlock_autopilot(self):
        """Operator action: unlocks the autopilot state."""
        self.locked = False
        self.safe_mode = False
        self.routing_service.set_safe_mode(False)
        self.recovery_timestamps = []
        logger.info("Autopilot unlocked manually by operator.")
        self.db_service.log_operations_event(
            severity="INFO",
            event="AUTOPILOT_UNLOCKED",
            action_taken="UNLOCK_AUTOPILOT",
            result="SUCCESS",
            host="p3noc"
        )

    def push_history(self, history_list: list, value: float, max_len=5):
        """Append value to history window and keep length capped."""
        history_list.append(value)
        if len(history_list) > max_len:
            history_list.pop(0)

    def check_is_increasing(self, history_list: list) -> bool:
        """Verify if history values are strictly increasing (trend detection)."""
        if len(history_list) < 4:
            return False
        return all(history_list[i] < history_list[i+1] for i in range(len(history_list) - 1))

    def evaluate_predictive_alerts(self, telemetry: dict):
        """Run trend-based anomaly detection rules."""
        self.predictive_alerts = []
        
        # Push stats to history
        self.push_history(self.cpu_history, telemetry.get("cpu", 0.0))
        self.push_history(self.ram_history, telemetry.get("ram", 0.0))
        self.push_history(self.queue_history, telemetry.get("queue_remaining", 0))
        self.push_history(self.failed_history, telemetry.get("failed_queue", 0))
        self.push_history(self.latency_history, telemetry.get("avg_latency", 0.0))
        
        # Check trends
        if self.check_is_increasing(self.cpu_history) and self.cpu_history[-1] > 70.0:
            self.predictive_alerts.append("RESOURCE PRESSURE: CPU RISING STEEP")
        if self.check_is_increasing(self.ram_history) and self.ram_history[-1] > 80.0:
            self.predictive_alerts.append("RESOURCE PRESSURE: RAM RISING STEEP")
        if self.check_is_increasing(self.queue_history) and self.queue_history[-1] > 15:
            self.predictive_alerts.append("QUEUE JAM: INCOMING BACKLOG RISING")
        if self.check_is_increasing(self.failed_history) and self.failed_history[-1] > 10:
            self.predictive_alerts.append("INCIDENT TREND: FAILS ACCUMULATING")
        if self.check_is_increasing(self.latency_history) and self.latency_history[-1] > 120.0:
            self.predictive_alerts.append("LATENCY DEGRADING: OLLAMA SLOWING")

    def execute_autopilot_cycle(self, telemetry: dict) -> HealthState:
        """
        Execute automated recovery checks.
        Called every 60 seconds in the background.
        """
        issues = []
        actions = []
        
        # If locked, skip automated recovery actions
        if self.locked:
            return HealthState("LOCKED", 10, ["AUTOPILOT LOCKED - MANUAL REVIEW REQUIRED"], [])

        # Evaluate trend alerts
        self.evaluate_predictive_alerts(telemetry)
        
        # Calculate base health score (start at 100, deduct for issues)
        score = 100
        
        # Subsystem Checks
        db_ok = telemetry.get("db_online", True)
        worker_ok = telemetry.get("worker_online", True)
        ingest_ok = telemetry.get("ingest_online", True)
        ollama_ok = telemetry.get("ollama_online", True)
        failed_count = telemetry.get("failed_queue", 0)
        processing_count = telemetry.get("processing_queue", 0)
        oldest_age = telemetry.get("oldest_processing_age_mins", 0)
        ollama_fails = telemetry.get("ollama_failures", 0)
        ai_server_state = telemetry.get("ai_server_status", "GREEN")
        
        # Hardware checks
        disk_percent = telemetry.get("disk_percent", 0.0)
        fs_readonly = telemetry.get("fs_readonly", False)
        ipmi_fault = telemetry.get("ipmi_fault", False)
        raid_failure = telemetry.get("raid_failure", False)
        
        if not db_ok:
            score -= 30
            issues.append("PostgreSQL Connection Offline")
        if ai_server_state == "RED":
            score -= 25
            issues.append("AI Server (R510) Offline/Unreachable")
        if not worker_ok:
            score -= 15
            issues.append("Worker service Stopped")
        if not ingest_ok:
            score -= 10
            issues.append("Ingest Timer Inactive")
        if not ollama_ok:
            score -= 20
            issues.append("Ollama Endpoint Offline")
        if failed_count > 10:
            score -= min(15, failed_count // 2)
            issues.append(f"Failed Queue buildup: {failed_count} items")
        if processing_count > 5 and oldest_age > 15:
            score -= 10
            issues.append(f"Queue Jam: processing job age > {oldest_age}m")
            
        # Hardware fault deductions
        if disk_percent > 95.0:
            score -= 20
            issues.append(f"Disk usage > 95% ({disk_percent:.1f}%)")
        if fs_readonly:
            score -= 40
            issues.append("Filesystem mounted Read-Only")
        if ipmi_fault:
            score -= 25
            issues.append("Critical Hardware Fault via IPMI")
        if raid_failure:
            score -= 30
            issues.append("RAID Controller/Battery Failure")

        # --- Self-Healing Rules Engine ---
        # Rule 1: Ollama Offline / Timeout Spike
        if ollama_fails >= 3 or not ollama_ok:
            if OLLAMA_REMOTE:
                issues.append("REMOTE OLLAMA OFFLINE")
                # Do not attempt local restart
            else:
                issues.append("Ollama Failure Detected")
                if self.record_recovery_attempt():
                    logger.warning("Autopilot: Restarting Ollama...")
                    self.db_service.log_operations_event("CRITICAL", "OLLAMA_TIMEOUT_DETECTED", "RESTART_OLLAMA", "PENDING")
                    res = self.recovery_service.restart_ollama()
                    result_str = "SUCCESS" if res else "FAILED"
                    self.db_service.log_operations_event("INFO", "OLLAMA_RESTART_COMPLETED", "RESTART_OLLAMA", result_str)
                    if res:
                        self.recovery_service.warm_model(self.routing_service.model_fast)
                        self.db_service.log_operations_event("INFO", "MODEL_WARMED", "WARM_MODEL", "SUCCESS")
                    actions.append("Restart Ollama")
        
        # Rule 2: Queue Jam
        if processing_count > 5 and oldest_age > 15:
            issues.append("Queue Jam Detected")
            if self.record_recovery_attempt():
                logger.warning("Autopilot: Clearing stuck processing jobs...")
                self.db_service.log_operations_event("WARNING", "QUEUE_JAM_DETECTED", "CLEAR_STUCK_PROCESSING", "PENDING")
                res = self.recovery_service.clear_stuck_processing()
                result_str = "SUCCESS" if res else "FAILED"
                self.db_service.log_operations_event("INFO", "QUEUE_JAM_CLEARED", "CLEAR_STUCK_PROCESSING", result_str)
                actions.append("Clear Stuck Queue")

        # Rule 3: Backlog
        if failed_count > 25:
            issues.append("Failed Queue Backlog")
            if self.record_recovery_attempt():
                logger.warning("Autopilot: Requeueing failed jobs...")
                self.db_service.log_operations_event("WARNING", "FAILED_BACKLOG_DETECTED", "REQUEUE_FAILED_JOBS", "PENDING")
                res = self.recovery_service.requeue_failed()
                result_str = "SUCCESS" if res else "FAILED"
                self.db_service.log_operations_event("INFO", "BACKLOG_REQUEUED", "REQUEUE_FAILED_JOBS", result_str)
                actions.append("Requeue Failed Jobs")

        # Rule 4: Worker Offline
        if not worker_ok:
            issues.append("Worker service Offline")
            if self.record_recovery_attempt():
                logger.warning("Autopilot: Restarting Worker...")
                self.db_service.log_operations_event("CRITICAL", "WORKER_OFFLINE_DETECTED", "RESTART_WORKER", "PENDING")
                res = self.recovery_service.restart_worker()
                result_str = "SUCCESS" if res else "FAILED"
                self.db_service.log_operations_event("INFO", "WORKER_RESTART_COMPLETED", "RESTART_WORKER", result_str)
                actions.append("Restart Worker")

        # Rule 5: Ingest Timer Offline
        if not ingest_ok:
            issues.append("RSS Ingest Timer Offline")
            if self.record_recovery_attempt():
                logger.warning("Autopilot: Restarting RSS Ingest...")
                self.db_service.log_operations_event("CRITICAL", "INGEST_TIMER_DEAD_DETECTED", "RESTART_INGEST", "PENDING")
                res = self.recovery_service.restart_ingest()
                result_str = "SUCCESS" if res else "FAILED"
                self.db_service.log_operations_event("INFO", "INGEST_TIMER_RESTART_COMPLETED", "RESTART_INGEST", result_str)
                actions.append("Restart RSS Ingest")

        score = max(10, score)
        status = "HEALTHY" if score > 90 else ("DEGRADED" if score > 50 else "INCIDENT")
        if self.safe_mode:
            status = f"{status} (SAFE)"
            
        return HealthState(status, score, issues, actions)
