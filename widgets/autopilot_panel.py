from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class AutopilotPanel(Static):
    """
    Autopilot Status Widget.
    Displays health scores, uptime, current automation mode (ACTIVE/LOCKED/SAFE),
    and a persistent log of the last 4 self-healing recovery actions.
    """
    status_str = reactive("ACTIVE")
    health_score = reactive(100)
    uptime_days = reactive(37)
    actions_today = reactive(0)
    last_actions_list = reactive([]) # list of dicts with timestamp, action_taken, result
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "AUTOPILOT STATUS"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        muted = theme["muted"]
        accent = theme["accent"]
        error = theme["error"]
        warning = theme["warning"]
        healthy = theme["healthy"]

        content = Text()
        
        # Line 1: STATUS & HEALTH
        content.append(" Status:  ", style="white")
        if "LOCKED" in self.status_str.upper():
            status_style = f"bold {error} reverse"
        elif "SAFE" in self.status_str.upper():
            status_style = f"bold {warning}"
        else:
            status_style = f"bold {healthy}"
        content.append(f"{self.status_str:<7} ", style=status_style)
        
        content.append("| Health: ", style="white")
        score_style = healthy if self.health_score > 90 else (warning if self.health_score > 50 else error)
        content.append(f"{self.health_score}/100\n", style=f"bold {score_style}")

        # Line 2: UPTIME & ACTIONS TODAY
        content.append(" Uptime:  ", style="white")
        content.append(f"{self.uptime_days:<6}D ", style=accent)
        content.append("| Actions:", style="white")
        content.append(f" {self.actions_today} Today\n", style=healthy if self.actions_today == 0 else warning)

        # Line 3: LAST AUTO ACTION
        content.append(" Last:    ", style="white")
        if self.last_actions_list:
            act = self.last_actions_list[0]
            action = act.get("action_taken", "Unknown Action")
            action_clean = action.replace("_", " ").title()
            if len(action_clean) > 15:
                action_clean = action_clean[:12] + "..."
            result = act.get("result", "SUCCESS")
            res_color = healthy if result == "SUCCESS" else error
            content.append(f"{action_clean} ", style="white")
            content.append(f"({result})", style=res_color)
        else:
            content.append("None", style=muted)
        content.append("\n")

        return content
