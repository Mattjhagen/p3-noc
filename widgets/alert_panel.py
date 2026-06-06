from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS
from config.settings import OLLAMA_REMOTE

class AlertPanel(Static):
    """
    Displays real-time operational alerts, Smart Recommendations,
    and trend-based Predictive Anomaly Warnings.
    """
    # Active states for alerts
    ollama_online = reactive(True)
    db_online = reactive(True)
    worker_active = reactive(True)
    ingest_active = reactive(True)
    
    ollama_failures = reactive(0)
    max_retry = reactive(0)
    failed_queue_count = reactive(0)
    latest_risk_score = reactive(0)
    worker_efficiency = reactive(100.0)
    avg_time = reactive(0.0)
    
    # v4 Smart Recommendations states
    host_ram_percent = reactive(0.0)
    queue_processing_count = reactive(0)
    active_ollama_model = reactive("")
    env_ollama_model = reactive("")
    
    # v5 Autopilot & Predictive states
    autopilot_locked = reactive(False)
    predictive_alerts = reactive([])
    startup_failures = reactive([])
    
    # Remote AI Server Monitoring reactive states
    ai_server_status = reactive("GREEN")
    ai_server_is_critical = reactive(False)
    ai_server_flash_toggle = reactive(False)

    # Bitcoin Core Node reactive states
    btc_node_status = reactive("OFFLINE")
    btc_node_peers = reactive(0)
    btc_node_disk_used = reactive(0.0)
    btc_node_disk_total = reactive(11000.0)
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "ALERTS"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        error = theme["error"]
        warning = theme["warning"]
        healthy = theme["healthy"]
        accent = theme["accent"]

        # Ensure instance tracking variables exist
        if not hasattr(self, "alert_timestamps"):
            self.alert_timestamps = {}
        if not hasattr(self, "last_alert_time"):
            self.last_alert_time = "N/A"

        # Gather active alerts
        active_alerts = []
        
        if not self.db_online:
            active_alerts.append(("Database Offline", "CRITICAL"))
        if not self.worker_active:
            active_alerts.append(("Worker Offline", "CRITICAL"))
        if not self.ingest_active:
            active_alerts.append(("Ingest Offline", "CRITICAL"))
        if not self.ollama_online or self.ollama_failures >= 3:
            active_alerts.append(("Ollama Offline/Timeout", "CRITICAL"))
        if self.ai_server_status == "RED":
            active_alerts.append(("AI Server Connection Failed", "CRITICAL"))
        elif self.ai_server_status == "YELLOW":
            active_alerts.append(("AI Server Degraded", "WARNING"))
        if self.env_ollama_model and self.active_ollama_model and self.env_ollama_model.lower() != self.active_ollama_model.lower():
            active_alerts.append(("Model Mismatch", "WARNING"))
        if self.latest_risk_score >= 80:
            active_alerts.append((f"High Risk ({self.latest_risk_score})", "CRITICAL"))
        elif self.latest_risk_score >= 50:
            active_alerts.append((f"Elevated Risk ({self.latest_risk_score})", "WARNING"))
        if self.worker_efficiency < 85.0:
            active_alerts.append((f"Queue Failures High ({100.0 - self.worker_efficiency:.1f}%)", "CRITICAL"))
        elif self.worker_efficiency < 95.0:
            active_alerts.append((f"Queue Failures Elevated ({100.0 - self.worker_efficiency:.1f}%)", "WARNING"))
        if self.failed_queue_count > 25:
            active_alerts.append((f"Failed Queue Large ({self.failed_queue_count})", "CRITICAL"))
        elif self.failed_queue_count > 10:
            active_alerts.append((f"Failed Queue Elevated ({self.failed_queue_count})", "WARNING"))
        if self.avg_time > 180.0:
            active_alerts.append((f"Analysis Latency High ({self.avg_time:.1f}s)", "WARNING"))
        if self.startup_failures:
            for fail in self.startup_failures:
                active_alerts.append((f"Startup: {fail}", "CRITICAL"))
        if self.predictive_alerts:
            for pred in self.predictive_alerts:
                active_alerts.append((f"Predictive: {pred}", "WARNING"))

        # Bitcoin Node alerts
        btc_status_upper = self.btc_node_status.upper().strip()
        if btc_status_upper == "OFFLINE":
            active_alerts.append(("Bitcoin Node Offline", "CRITICAL"))
        elif btc_status_upper == "RPC_UNREACHABLE":
            active_alerts.append(("Bitcoin RPC Unreachable", "CRITICAL"))
        elif btc_status_upper == "SYNC_STALLED":
            active_alerts.append(("Bitcoin Sync Stalled", "WARNING"))
        
        if self.btc_node_peers < 3 and btc_status_upper != "OFFLINE":
            active_alerts.append((f"Bitcoin Peers Low ({self.btc_node_peers})", "WARNING"))

        if self.btc_node_disk_total > 0:
            util = (self.btc_node_disk_used / self.btc_node_disk_total) * 100.0
            if util > 90.0:
                active_alerts.append((f"Bitcoin Disk >90% ({util:.1f}%)", "CRITICAL"))

        content = Text()
        import time

        if not active_alerts:
            content.append("\n  ✔ No Active Alerts\n", style=f"bold {healthy}")
            self.alert_timestamps = {}
            self.last_alert_time = "N/A"
            return content

        # Update timestamps for alerts
        current_alert_names = set(name for name, sev in active_alerts)
        now_str = time.strftime("%H:%M:%S")
        added_any = False
        for name, sev in active_alerts:
            if name not in self.alert_timestamps:
                self.alert_timestamps[name] = now_str
                added_any = True
        for name in list(self.alert_timestamps.keys()):
            if name not in current_alert_names:
                del self.alert_timestamps[name]
        if added_any:
            self.last_alert_time = now_str

        alert_count = len(active_alerts)
        has_critical = any(sev == "CRITICAL" for name, sev in active_alerts)
        has_warning = any(sev == "WARNING" for name, sev in active_alerts)
        highest_severity = "CRITICAL" if has_critical else ("WARNING" if has_warning else "INFO")
        newest_alert = active_alerts[-1][0]
        sev_color = error if highest_severity == "CRITICAL" else warning

        width = self.size.width if self.size.width > 0 else 40

        if width >= 36:
            # Layout A: Wide (3 rows)
            content.append(" Alert Count: ", style="white")
            content.append(f"{alert_count:<3}", style=f"bold {sev_color}")
            content.append(" | Sev: ", style="white")
            content.append(f"{highest_severity}\n", style=f"bold {sev_color}")

            # truncate newest alert to fit
            newest_disp = newest_alert
            if len(newest_disp) > 20:
                newest_disp = newest_disp[:17] + "..."
            content.append(" Newest Alert: ", style="white")
            content.append(f"{newest_disp}\n", style=accent)

            content.append(" Last Alert:   ", style="white")
            content.append(f"{self.last_alert_time}\n", style=accent)
        else:
            # Layout B: Narrow (4 rows)
            content.append(" Alert Count: ", style="white")
            content.append(f"{alert_count}\n", style=f"bold {sev_color}")

            content.append(" Sev:   ", style="white")
            content.append(f"{highest_severity}\n", style=f"bold {sev_color}")

            newest_disp = newest_alert
            if len(newest_disp) > 20:
                newest_disp = newest_disp[:17] + "..."
            content.append(" Newest: ", style="white")
            content.append(f"{newest_disp}\n", style=accent)

            content.append(" Last:   ", style="white")
            content.append(f"{self.last_alert_time}\n", style=accent)

        return content
