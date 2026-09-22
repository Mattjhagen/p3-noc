import logging
import subprocess
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger("dashboard")

class AIMonitorService:
    """
    AI-powered monitoring and automated fix implementation service.
    Uses OpenCode Big Pickle to diagnose issues and execute fixes.
    """

    def __init__(self, opencode_service, db_service, recovery_service):
        self.opencode_service = opencode_service
        self.db_service = db_service
        self.recovery_service = recovery_service
        self.fix_history = []
        self.max_fixes_per_hour = 5
        self.enabled = True

    def diagnose_alerts(self, alerts: List[str]) -> Optional[str]:
        """
        Send alerts to AI for diagnosis and get recommended fixes.

        Args:
            alerts: List of alert messages

        Returns:
            AI diagnosis and fix recommendations
        """
        if not alerts:
            return None

        # Build diagnosis prompt
        alerts_text = "\n".join(f"- {alert}" for alert in alerts[:5])  # Limit to 5 alerts
        prompt = f"""System alerts detected. Diagnose and provide fixes:

Alerts:
{alerts_text}

For each alert:
1. Identify root cause
2. Provide exact command to fix
3. Rate urgency (LOW/MEDIUM/HIGH)

Format: ALERT | CAUSE | FIX_COMMAND | URGENCY
Keep response under 500 chars."""

        diagnosis = self.opencode_service.generate_response(prompt)
        if diagnosis:
            logger.info(f"AI diagnosis generated for {len(alerts)} alerts")
            self.last_diagnosis = {
                "timestamp": datetime.now(),
                "alerts": alerts,
                "diagnosis": diagnosis
            }
        return diagnosis

    def auto_implement_fix(self, fix_command: str, urgency: str = "MEDIUM") -> Dict:
        """
        Automatically execute a fix command with safety checks.

        Args:
            fix_command: Shell command to execute
            urgency: Urgency level (LOW/MEDIUM/HIGH)

        Returns:
            Result dict with success, output, and error info
        """
        result = {
            "success": False,
            "command": fix_command,
            "output": "",
            "error": "",
            "timestamp": datetime.now()
        }

        # Safety checks
        if not self.enabled:
            result["error"] = "AI monitoring disabled"
            return result

        if len(self.fix_history) >= self.max_fixes_per_hour:
            result["error"] = "Max fixes per hour reached (circuit breaker)"
            logger.warning("AI fix circuit breaker triggered")
            return result

        # Blacklist dangerous commands
        dangerous_keywords = ["rm -rf", "dd if=", "mkfs", ":(){", "shutdown", "reboot"]
        if any(keyword in fix_command.lower() for keyword in dangerous_keywords):
            result["error"] = f"Dangerous command blocked: {fix_command}"
            logger.error(f"AI attempted dangerous command: {fix_command}")
            return result

        # Whitelist safe operations
        safe_commands = ["systemctl restart", "systemctl start", "docker restart", "pkill", "curl"]
        if not any(cmd in fix_command for cmd in safe_commands):
            result["error"] = f"Command not in whitelist: {fix_command}"
            logger.warning(f"AI command not whitelisted: {fix_command}")
            return result

        # Execute the fix
        try:
            logger.info(f"Executing AI fix ({urgency}): {fix_command}")
            proc = subprocess.run(
                fix_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            result["success"] = proc.returncode == 0
            result["output"] = proc.stdout
            result["error"] = proc.stderr if proc.returncode != 0 else ""

            # Log to database
            self.db_service.log_operations_event(
                severity="INFO" if result["success"] else "WARNING",
                event=f"AI_FIX_EXECUTED",
                action_taken=fix_command,
                result="SUCCESS" if result["success"] else "FAILED",
                host="p3noc-ai"
            )

            # Add to history
            self.fix_history.append(result)
            # Keep only last hour of history
            cutoff = datetime.now()
            self.fix_history = [
                f for f in self.fix_history
                if (cutoff - f["timestamp"]).seconds < 3600
            ]

        except subprocess.TimeoutExpired:
            result["error"] = "Command timed out"
            logger.error(f"AI fix timed out: {fix_command}")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"AI fix failed: {e}")

        return result

    def parse_and_execute_fixes(self, diagnosis: str) -> List[Dict]:
        """
        Parse AI diagnosis and automatically execute recommended fixes.

        Args:
            diagnosis: AI diagnosis response

        Returns:
            List of fix results
        """
        if not diagnosis:
            return []

        results = []
        lines = diagnosis.split("\n")

        for line in lines:
            # Parse format: ALERT | CAUSE | FIX_COMMAND | URGENCY
            if "|" in line and "FIX" in line.upper():
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    fix_command = parts[2]
                    urgency = parts[3] if len(parts) > 3 else "MEDIUM"

                    # Only auto-execute MEDIUM and LOW urgency fixes
                    if urgency in ["LOW", "MEDIUM"]:
                        result = self.auto_implement_fix(fix_command, urgency)
                        results.append(result)
                    else:
                        logger.info(f"Skipping HIGH urgency fix (requires approval): {fix_command}")

        return results

    def monitor_and_fix_loop(self, alert_panel) -> Optional[str]:
        """
        Main monitoring loop - check alerts and automatically fix issues.

        Args:
            alert_panel: Reference to alert panel widget

        Returns:
            Summary of actions taken
        """
        if not self.enabled:
            return None

        # Get current alerts
        alerts = alert_panel.get_current_alerts() if hasattr(alert_panel, 'get_current_alerts') else []

        if not alerts:
            return "No alerts - system healthy"

        # Diagnose with AI
        diagnosis = self.diagnose_alerts(alerts)
        if not diagnosis:
            return "AI diagnosis failed"

        # Parse and execute fixes
        fix_results = self.parse_and_execute_fixes(diagnosis)

        # Build summary
        successful_fixes = sum(1 for r in fix_results if r["success"])
        failed_fixes = len(fix_results) - successful_fixes

        summary = f"AI Monitor: {successful_fixes} fixes applied, {failed_fixes} failed"
        logger.info(summary)

        return summary

    def disable(self):
        """Disable AI monitoring (circuit breaker)."""
        self.enabled = False
        logger.warning("AI monitoring disabled")

    def enable(self):
        """Re-enable AI monitoring."""
        self.enabled = True
        logger.info("AI monitoring enabled")
