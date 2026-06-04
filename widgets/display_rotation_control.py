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
    is_readonly = reactive(False)
    
    # Idle-aware screensaver system fields
    pause_reason = reactive("None")
    inactivity_timer_str = reactive("N/A")
    next_auto_resume_str = reactive("N/A")
    
    def __init__(self, is_readonly=False, **kwargs):
        super().__init__(**kwargs)
        self.is_readonly = is_readonly
        
    def on_mount(self):
        self.border_title = "DISPLAY ROTATION CONTROL"
        
    def watch_status_str(self, old_value: str, new_value: str):
        """Watch status_str to dynamically apply style classes."""
        if "PAUSED" in new_value:
            self.add_class("paused-panel")
        else:
            self.remove_class("paused-panel")
            
    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]
        
        content = Text()
        
        # 1. Visual Indicator
        content.append(" ")
        if self.status_str == "ACTIVE" or self.status_str == "RUNNING":
            content.append("▶ AUTO ROTATION ACTIVE\n", style=f"bold {healthy}")
        elif self.status_str == "PAUSED":
            content.append("⏸ OPERATOR ACTIVE\n", style=f"bold {warning}")
        elif "CRITICAL" in self.status_str:
            content.append("🚨 CRITICAL SYSTEM FAULT\n", style=f"bold {error}")
        else:
            content.append("🚨 ROTATION OFFLINE\n", style=f"bold {error}")
            
        # 2. Main Rotation status fields
        content.append(" STATUS: ", style="white")
        if self.status_str == "ACTIVE" or self.status_str == "RUNNING":
            content.append("ACTIVE\n", style=healthy)
        elif self.status_str == "PAUSED":
            content.append("PAUSED\n", style=warning)
        else:
            content.append(f"{self.status_str}\n", style=error)
            
        content.append(" REASON: ", style="white")
        reason_style = warning if self.pause_reason != "None" else "white"
        content.append(f"{self.pause_reason}\n", style=reason_style)
        
        content.append(" TIMER:  ", style="white")
        content.append(f"{self.inactivity_timer_str}\n", style=accent)
        
        content.append(" RESUME: ", style="white")
        content.append(f"{self.next_auto_resume_str}\n", style="cyan")
        
        # 3. Details
        content.append(f" TTY: {self.current_tty} | INT: {self.rotation_interval}s | LAST: {self.last_switch_time}\n", style=primary)
        
        # 4. Hotkeys details / READ-ONLY VIEWER
        if self.is_readonly:
            content.append(" [READ-ONLY VIEWER]\n", style=f"bold {warning}")
            content.append(" Controlled by T310\n", style="white")
        else:
            content.append(" [P] Pause [R] Resume [C] Auto\n", style="white")
            content.append(" [1] Lock1 [2] Lock2  [+]/[-]\n", style="white")
            
        return content
