from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS
from config.settings import AI_SERVER_HOST, AI_SERVER_IP

class AiServerStatusPanel(Static):
    """
    Displays the status of the remote AI Server (R510).
    """
    host = reactive(AI_SERVER_HOST)
    ip = reactive(AI_SERVER_IP)
    ping_latency = reactive(0.0)
    ssh_status = reactive("OFFLINE")
    ollama_status = reactive("OFFLINE")
    last_success = reactive("N/A")
    installed_models = reactive([])
    loaded_models = reactive([])
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "AI SERVER STATUS"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        ping_val = f"{self.ping_latency:.1f}ms" if self.ping_latency > 0 else "TIMEOUT"
        ping_style = healthy if self.ping_latency > 0 else error
        ssh_style = healthy if self.ssh_status == "ONLINE" else error
        ollama_style = healthy if self.ollama_status == "ONLINE" else error

        # Build models summary
        models_list = []
        if self.loaded_models:
            models_list.append(f"Loaded: {','.join(self.loaded_models)}")
        if self.installed_models:
            models_list.append(f"Inst: {','.join(self.installed_models)}")
        models_summary = "; ".join(models_list) if models_list else "None"
        
        content = Text()
        width = self.size.width if self.size.width > 0 else 40

        if width >= 36:
            # Layout A: Wide (4 rows)
            content.append(" Host: ", style="white")
            content.append(f"{self.host or 'Unknown':<9}", style=accent)
            content.append(" | Ping:   ", style="white")
            content.append(f"{ping_val}\n", style=ping_style)

            content.append(" SSH:  ", style="white")
            content.append(f"{self.ssh_status or 'OFFLINE':<9}", style=ssh_style)
            content.append(" | Ollama: ", style="white")
            content.append(f"{self.ollama_status or 'OFFLINE'}\n", style=ollama_style)

            # limit length of models_summary to prevent wrapping
            models_summary_disp = models_summary
            if len(models_summary_disp) > 22:
                models_summary_disp = models_summary_disp[:19] + "..."
            content.append(" Models: ", style="white")
            content.append(f"{models_summary_disp}\n", style=accent)

            content.append(" Seen:   ", style="white")
            # Show just time part of seen string to fit
            seen_time = self.last_success
            if len(seen_time) > 10:
                seen_time = seen_time.split(" ")[-1]
            content.append(f"{seen_time or 'Never'}\n", style="cyan")
        else:
            # Layout B: Narrow (6 rows)
            content.append(" Host: ", style="white")
            content.append(f"{self.host or 'Unknown'}\n", style=accent)

            content.append(" Ping: ", style="white")
            content.append(f"{ping_val}\n", style=ping_style)

            content.append(" SSH:  ", style="white")
            content.append(f"{self.ssh_status or 'OFFLINE'}\n", style=ssh_style)

            content.append(" Ollama: ", style="white")
            content.append(f"{self.ollama_status or 'OFFLINE'}\n", style=ollama_style)

            models_summary_disp = models_summary
            if len(models_summary_disp) > 22:
                models_summary_disp = models_summary_disp[:19] + "..."
            content.append(" Models: ", style="white")
            content.append(f"{models_summary_disp}\n", style=accent)

            content.append(" Seen: ", style="white")
            content.append(f"{self.last_success or 'Never'}\n", style="cyan")

        return content
