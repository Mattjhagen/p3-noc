from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class DisplayRotationControl(Static):
    """
    DISPLAY ROTATION CONTROL Panel for the R510 Dashboard.
    Displays remote T310 TTY rotation status, active console,
    switch countdown, and control hotkeys.
    """
    status_str = reactive("OFFLINE")
    current_tty = reactive("N/A")
    rotation_interval = reactive(60)
    last_switch_time = reactive("N/A")
    next_switch_str = reactive("00:00")
    current_theme = reactive("matrix-green")
    
    def on_mount(self):
        self.border_title = "DISPLAY ROTATION CONTROL"
        
    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]
        
        content = Text()
        content.append("\n Remote T310 Monitor Status:\n\n", style=f"bold {primary}")
        
        # Print current status values
        content.append("  Status:   ", style="white")
        if self.status_str == "RUNNING":
            content.append("RUNNING\n", style=healthy)
        elif self.status_str == "PAUSED":
            content.append("PAUSED\n", style=warning)
        elif "CRITICAL" in self.status_str:
            content.append("CRITICAL ALARM\n", style=error)
        else:
            content.append("OFFLINE / UNREACHABLE\n", style=error)
            
        content.append("  Current:  ", style="white")
        content.append(f"TTY {self.current_tty}\n", style=accent)
        
        content.append("  Interval: ", style="white")
        content.append(f"{self.rotation_interval} seconds\n", style=accent)
        
        content.append("  Last:     ", style="white")
        content.append(f"{self.last_switch_time}\n\n", style="cyan")
        
        # Prominent Status Block Box
        content.append(" ")
        if self.status_str == "RUNNING":
            content.append("╔════════════════════════════╗\n", style=healthy)
            content.append("  ║ ", style=healthy)
            content.append("DISPLAY ROTATION ACTIVE   ", style=f"bold {healthy}")
            content.append(" ║\n", style=healthy)
            content.append("  ║ ", style=healthy)
            content.append(f"Current: TTY {self.current_tty}".ljust(26), style="white")
            content.append(" ║\n", style=healthy)
            content.append("  ║ ", style=healthy)
            content.append(f"Next Switch: {self.next_switch_str}".ljust(26), style="white")
            content.append(" ║\n", style=healthy)
            content.append("  ║ ", style=healthy)
            content.append(f"Interval: {self.rotation_interval} sec".ljust(26), style="white")
            content.append(" ║\n", style=healthy)
            content.append("  ╚════════════════════════════╝\n", style=healthy)
        elif self.status_str == "PAUSED":
            content.append("╔════════════════════════════╗\n", style=warning)
            content.append("  ║ ", style=warning)
            content.append("DISPLAY ROTATION PAUSED   ", style=f"bold {warning}")
            content.append(" ║\n", style=warning)
            content.append("  ║ ", style=warning)
            content.append(f"Locked On: TTY {self.current_tty}".ljust(26), style="white")
            content.append(" ║\n", style=warning)
            content.append("  ╚════════════════════════════╝\n", style=warning)
        elif "CRITICAL" in self.status_str:
            content.append("╔════════════════════════════╗\n", style=error)
            content.append("  ║ ", style=error)
            content.append("CRITICAL SYSTEM FAULT     ", style=f"bold white on {error}")
            content.append(" ║\n", style=error)
            content.append("  ║ ", style=error)
            content.append("Locked On: TTY 1".ljust(26), style="white")
            content.append(" ║\n", style=error)
            content.append("  ╚════════════════════════════╝\n", style=error)
        else:
            content.append("╔════════════════════════════╗\n", style=error)
            content.append("  ║ ", style=error)
            content.append("DISPLAY ROTATION OFFLINE  ", style=f"bold {error}")
            content.append(" ║\n", style=error)
            content.append("  ║ ", style=error)
            content.append("Unreachable / Disconnected".ljust(26), style="white")
            content.append(" ║\n", style=error)
            content.append("  ╚════════════════════════════╝\n", style=error)
            
        # Hotkeys details
        content.append("\n  Control Keys:\n", style=f"bold {primary}")
        content.append("  [P] Pause  [R] Resume  [A] Auto\n", style="white")
        content.append("  [1] Lock T1 [2] Lock T2  [+]/[-] Int\n", style="white")
        
        return content
