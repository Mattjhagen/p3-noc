from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class ThroughputPanel(Static):
    """
    Displays operational performance statistics:
    throughput rate, processing latencies, remaining load, and completion ETA.
    """
    processed_last_hour = reactive(0)
    processed_today = reactive(0)
    avg_time = reactive(0.0)
    remaining = reactive(0)
    eta_str = reactive("0m")
    worker_efficiency = reactive(100.0)
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "THROUGHPUT"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        muted = theme["muted"]
        accent = theme["accent"]
        warning = theme["warning"]
        error = theme["error"]
        healthy = theme["healthy"]

        content = Text()
        
        # Line 1: LAST HOUR & TODAY
        content.append(" Hour: ", style="white")
        content.append(f"{self.processed_last_hour:<6} ", style=healthy)
        content.append("| Today:  ", style="white")
        content.append(f"{self.processed_today:,}\n", style=healthy)

        # Line 2: AVG TIME & REMAINING
        content.append(" Lat:  ", style="white")
        content.append(f"{self.avg_time:.1f}s   ", style=accent)
        content.append("| Remain: ", style="white")
        content.append(f"{self.remaining}\n", style=warning)

        # Line 3: ETA & EFFICIENCY
        content.append(" ETA:  ", style="white")
        content.append(f"{self.eta_str:<6} ", style="bold white")
        content.append("| Eff:    ", style="white")
        eff_style = healthy if self.worker_efficiency >= 95.0 else (warning if self.worker_efficiency >= 85.0 else error)
        content.append(f"{self.worker_efficiency:.1f}%\n", style=f"bold {eff_style}")

        return content
