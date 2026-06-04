from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class WatchdogPanel(Static):
    """
    SYSTEM WATCHDOG Panel
    Displays the real-time operational status (GREEN/YELLOW/RED)
    of 6 core dashboard components.
    """
    t310_status = reactive("GREEN")
    r510_status = reactive("GREEN")
    ollama_api_status = reactive("GREEN")
    worker_status = reactive("GREEN")
    postgres_status = reactive("GREEN")
    queue_status = reactive("GREEN")

    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "SYSTEM WATCHDOG"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        content = Text()
        content.append("\n Subsystem Diagnostics:\n\n", style=f"bold {theme['primary']}")

        def append_row(label: str, status: str):
            content.append(f"  {label.ljust(17)}", style="white")
            if status == "RED":
                content.append("🔴 RED", style=f"bold {error}")
            elif status == "YELLOW":
                content.append("🟡 YELLOW", style=f"bold {warning}")
            else:
                content.append("🟢 GREEN", style=f"bold {healthy}")
            content.append("\n")

        append_row("T310 Status", self.t310_status)
        append_row("R510 Status", self.r510_status)
        append_row("Ollama API", self.ollama_api_status)
        append_row("Bitcoin Worker", self.worker_status)
        append_row("PostgreSQL", self.postgres_status)
        append_row("Queue Progress", self.queue_status)

        return content
