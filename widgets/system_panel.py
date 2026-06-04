import time
import psutil
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class SystemPanel(Static):
    """
    SYSTEM Panel.
    Displays host CPU %, RAM %, Disk %, Uptime, Worker and PostgreSQL
    online statuses, and a queue summary (pending, processing, completed, failed).
    """
    pending_count = reactive(0)
    processing_count = reactive(0)
    completed_count = reactive(0)
    failed_count = reactive(0)
    
    cpu_percent = reactive(0.0)
    ram_percent = reactive(0.0)
    disk_percent = reactive(0.0)
    uptime_str = reactive("N/A")
    worker_status = reactive("OFFLINE")
    db_status = reactive("OFFLINE")
    fs_status = reactive("READ-WRITE")
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "SYSTEM"
        self.set_interval(1.0, self.update_host_metrics)

    def update_host_metrics(self):
        """Fetch system statistics and compute host uptime."""
        self.cpu_percent = psutil.cpu_percent()
        self.ram_percent = psutil.virtual_memory().percent
        try:
            self.disk_percent = psutil.disk_usage('/').percent
        except Exception:
            self.disk_percent = 0.0

        try:
            uptime_seconds = time.time() - psutil.boot_time()
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            if days > 0:
                self.uptime_str = f"{days}d {hours}h"
            elif hours > 0:
                self.uptime_str = f"{hours}h {minutes}m"
            else:
                self.uptime_str = f"{minutes}m"
        except Exception:
            self.uptime_str = "N/A"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        cpu_style = error if self.cpu_percent > 85 else (warning if self.cpu_percent > 60 else healthy)
        ram_style = error if self.ram_percent > 85 else (warning if self.ram_percent > 60 else healthy)
        disk_style = error if self.disk_percent > 90 else (warning if self.disk_percent > 75 else healthy)
        db_color = healthy if self.db_status == "ONLINE" else error
        worker_color = healthy if self.worker_status == "ONLINE" else error
        fs_color = healthy if "WRITE" in self.fs_status.upper() else error

        content = Text()

        # Check widget width for adaptive rendering
        width = self.size.width if self.size.width > 0 else 40

        if width >= 36:
            # Layout A: Dense 2-column layout (exactly 4 rows)
            content.append(" CPU:  ", style="white")
            content.append(f"{self.cpu_percent or 0.0:>5.1f}%", style=cpu_style)
            content.append(f"{'':<10}RAM:  ", style="white")
            content.append(f"{self.ram_percent or 0.0:>5.1f}%\n", style=ram_style)

            content.append(" Disk: ", style="white")
            content.append(f"{self.disk_percent or 0.0:>5.1f}%", style=disk_style)
            content.append(f"{'':<10}UP:   ", style="white")
            content.append(f"{self.uptime_str or 'N/A'}\n", style=accent)

            content.append(" DB:   ", style="white")
            content.append(f"{self.db_status or 'OFFLINE':<9}", style=db_color)
            content.append(" | WRK:  ", style="white")
            content.append(f"{self.worker_status or 'OFFLINE'}\n", style=worker_color)

            content.append(" FS:   ", style="white")
            fs_lbl = "RW" if "WRITE" in self.fs_status.upper() else "RO"
            content.append(f"{fs_lbl:<9}", style=fs_color)
            content.append(" | Q:    ", style="white")
            content.append(f"P:{self.pending_count} R:{self.processing_count} C:{self.completed_count}", style=accent)
        else:
            # Layout B: Vertical layout for narrow space (8 rows)
            content.append(" CPU:  ", style="white")
            content.append(f"{self.cpu_percent or 0.0:>5.1f}%\n", style=cpu_style)
            
            content.append(" RAM:  ", style="white")
            content.append(f"{self.ram_percent or 0.0:>5.1f}%\n", style=ram_style)
            
            content.append(" Disk: ", style="white")
            content.append(f"{self.disk_percent or 0.0:>5.1f}%\n", style=disk_style)
            
            content.append(" UP:   ", style="white")
            content.append(f"{self.uptime_str or 'N/A'}\n", style=accent)
            
            content.append(" DB:   ", style="white")
            content.append(f"{self.db_status or 'OFFLINE'}\n", style=db_color)
            
            content.append(" WRK:  ", style="white")
            content.append(f"{self.worker_status or 'OFFLINE'}\n", style=worker_color)
            
            content.append(" FS:   ", style="white")
            content.append(f"{self.fs_status or 'Unknown'}\n", style=fs_color)
            
            content.append(" Q:    ", style="white")
            content.append(f"P:{self.pending_count} R:{self.processing_count} C:{self.completed_count}\n", style=accent)

        return content

