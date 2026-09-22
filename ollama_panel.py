from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class OllamaPanel(Static):
    """
    Displays live Ollama inference statistics and server health details.
    """
    model_name = reactive("phi3:mini")
    server_host = reactive("r510")
    latency_sec = reactive(0.0)
    failures_count = reactive(0)
    status_str = reactive("ONLINE")
    requests_count = reactive(0)
    context_limit = reactive(40960)
    
    current_theme = reactive("matrix-green")
    trend_str = reactive("")

    def on_mount(self):
        # Check if using OpenCode or Ollama
        import os
        use_opencode = os.getenv("USE_OPENCODE", "false").lower() == "true"
        self.border_title = "AI SERVICE" if use_opencode else "OLLAMA"

    def watch_latency_sec(self, old_val: float, new_val: float) -> None:
        """Textual watcher to set latency trend indicators."""
        if old_val > 0.0:
            if new_val < old_val:
                self.trend_str = "↑ improving"
            elif new_val > old_val:
                self.trend_str = "↓ degrading"
            else:
                self.trend_str = ""

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        muted = theme["muted"]
        accent = theme["accent"]
        warning = theme["warning"]
        error = theme["error"]
        healthy = theme["healthy"]

        content = Text()
        content.append("\n Server Status:\n\n", style=f"bold {primary}")

        # Model name
        content.append(f"  Model:    ", style="white")
        content.append(f"{self.model_name}\n", style=accent)

        # Host
        content.append(f"  Server:   ", style="white")
        content.append(f"{self.server_host}\n", style=muted)

        # Latency
        content.append(f"  Latency:  ", style="white")
        latency_val_str = f"{self.latency_sec:.1f}s"
        content.append(f"{latency_val_str:<8}", style=warning)
        if self.trend_str:
            trend_color = healthy if "improving" in self.trend_str else error
            content.append(f" {self.trend_str}", style=trend_color)
        content.append("\n")

        # Requests
        content.append(f"  Requests: ", style="white")
        content.append(f"{self.requests_count}\n", style=healthy)

        # Failures
        content.append(f"  Failures: ", style="white")
        fail_style = error if self.failures_count > 0 else healthy
        content.append(f"{self.failures_count}\n", style=fail_style)

        # Context
        content.append(f"  Context:  ", style="white")
        content.append(f"{self.context_limit}\n", style=accent)

        # Status
        content.append(f"  Status:   ", style="white")
        status_color = healthy if self.status_str == "ONLINE" else error
        content.append(f"{self.status_str}\n", style=f"bold {status_color}")

        return content
