from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class OllamaPanel(Static):
    """
    OLLAMA Panel.
    Displays live Ollama endpoint health (Online/Offline), configured model,
    loaded model, response time, last query age, active requests, and queue state.
    """
    status_str = reactive("OFFLINE")
    configured_model = reactive("N/A")
    loaded_model = reactive("N/A")
    latency_sec = reactive(0.0)
    last_query_age_str = reactive("N/A")
    active_requests = reactive(0)
    queue_state = reactive("IDLE")
    server_host = reactive("r510")
    failures_count = reactive(0)
    requests_count = reactive(0)
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "OLLAMA"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        status_color = healthy if self.status_str == "ONLINE" else error
        latency_val_str = f"{self.latency_sec:.1f}s" if self.latency_sec > 0.0 else "N/A"
        state = self.queue_state.upper().strip()
        state_color = healthy if state == "IDLE" else (warning if state == "PENDING" else error)

        content = Text()

        width = self.size.width if self.size.width > 0 else 40

        if width >= 36:
            # Layout A: Wide (3 rows)
            content.append(" Status: ", style="white")
            content.append(f"{self.status_str or 'OFFLINE':<8}", style=status_color)
            content.append(" | Configured: ", style="white")
            content.append(f"{self.configured_model or 'N/A'}\n", style=accent)

            content.append(" Loaded: ", style="white")
            content.append(f"{self.loaded_model or 'None':<8}", style=accent)
            content.append(" | Latency:    ", style="white")
            content.append(f"{latency_val_str}\n", style=warning)

            content.append(" Last Q: ", style="white")
            content.append(f"{self.last_query_age_str or 'N/A':<8}", style=accent)
            content.append(" | Queue:      ", style="white")
            content.append(f"{state}\n", style=state_color)

            content.append(" Req:    ", style="white")
            content.append(f"{self.requests_count:<8}", style=accent)
            content.append(" | Failures:   ", style="white")
            content.append(f"{self.failures_count}\n", style=error if self.failures_count > 0 else healthy)
        else:
            # Layout B: Narrow (6 rows)
            content.append(" Status: ", style="white")
            content.append(f"{self.status_str or 'OFFLINE'}\n", style=status_color)

            content.append(" Configured: ", style="white")
            content.append(f"{self.configured_model or 'N/A'}\n", style=accent)

            content.append(" Loaded: ", style="white")
            content.append(f"{self.loaded_model or 'None'}\n", style=accent)

            content.append(" Latency: ", style="white")
            content.append(f"{latency_val_str}\n", style=warning)

            content.append(" Last Q: ", style="white")
            content.append(f"{self.last_query_age_str or 'N/A'}\n", style=accent)

            content.append(" Queue: ", style="white")
            content.append(f"{state}\n", style=state_color)

            content.append(" Req/Fail: ", style="white")
            content.append(f"{self.requests_count}", style=accent)
            content.append("/", style="white")
            content.append(f"{self.failures_count}\n", style=error if self.failures_count > 0 else healthy)

        return content
