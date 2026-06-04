import time
import psutil
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class SysMetricsPanel(Static):
    """
    Btop-style live host system metrics panel.
    Monitors CPU, RAM, Disk usage and RX/TX network speeds.
    """
    cpu_percent = reactive(0.0)
    ram_percent = reactive(0.0)
    disk_percent = reactive(0.0)
    net_rx_str = reactive("0.0 B/s")
    net_tx_str = reactive("0.0 B/s")
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "SYSTEM HOST METRICS"
        self.last_net_bytes = psutil.net_io_counters()
        self.last_time = time.time()
        
        # Poll metrics every 1.0 second
        self.set_interval(1.0, self.update_host_metrics)

    def update_host_metrics(self):
        """Fetch system statistics and compute network rates."""
        # CPU
        self.cpu_percent = psutil.cpu_percent()
        
        # RAM
        self.ram_percent = psutil.virtual_memory().percent
        
        # Disk
        try:
            self.disk_percent = psutil.disk_usage('/').percent
        except Exception:
            self.disk_percent = 0.0

        # Network RX/TX speeds
        try:
            current_net = psutil.net_io_counters()
            now = time.time()
            dt = max(0.1, now - self.last_time)
            
            rx_bytes_diff = current_net.bytes_recv - self.last_net_bytes.bytes_recv
            tx_bytes_diff = current_net.bytes_sent - self.last_net_bytes.bytes_sent
            
            rx_rate = rx_bytes_diff / dt
            tx_rate = tx_bytes_diff / dt
            
            self.net_rx_str = self._format_network_speed(rx_rate)
            self.net_tx_str = self._format_network_speed(tx_rate)
            
            self.last_net_bytes = current_net
            self.last_time = now
        except Exception:
            self.net_rx_str = "0.0 B/s"
            self.net_tx_str = "0.0 B/s"

    def _format_network_speed(self, bytes_per_sec: float) -> str:
        """Convert rate to human readable string."""
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.1f} B/s"
        elif bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        elif bytes_per_sec < 1024 * 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
        else:
            return f"{bytes_per_sec / (1024 * 1024 * 1024):.1f} GB/s"

    def _make_progress_bar(self, percent: float) -> str:
        """Draw btop-style progress bar length 10."""
        bar_len = 10
        filled = min(bar_len, int(percent / (100.0 / bar_len)))
        return "█" * filled + "░" * (bar_len - filled)

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        muted = theme["muted"]
        accent = theme["accent"]
        warning = theme["warning"]
        error = theme["error"]
        healthy = theme["healthy"]

        content = Text()
        
        # CPU row
        cpu_bar = self._make_progress_bar(self.cpu_percent)
        cpu_style = error if self.cpu_percent > 85 else (warning if self.cpu_percent > 60 else healthy)
        content.append(" CPU:  ", style="white")
        content.append(cpu_bar, style=cpu_style)
        content.append(f" {self.cpu_percent:>5.1f}%\n", style=cpu_style)

        # RAM row
        ram_bar = self._make_progress_bar(self.ram_percent)
        ram_style = error if self.ram_percent > 85 else (warning if self.ram_percent > 60 else healthy)
        content.append(" RAM:  ", style="white")
        content.append(ram_bar, style=ram_style)
        content.append(f" {self.ram_percent:>5.1f}%\n", style=ram_style)

        # Disk row
        disk_bar = self._make_progress_bar(self.disk_percent)
        disk_style = error if self.disk_percent > 90 else (warning if self.disk_percent > 75 else healthy)
        content.append(" DISK: ", style="white")
        content.append(disk_bar, style=disk_style)
        content.append(f" {self.disk_percent:>5.1f}%\n", style=disk_style)

        # Network row
        content.append(" NET:  ", style="white")
        content.append(f"RX: {self.net_rx_str:<10}", style=accent)
        content.append(f"TX: {self.net_tx_str}\n", style=accent)

        return content
