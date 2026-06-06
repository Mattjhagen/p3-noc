from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class WatchdogPanel(Static):
    """
    SYSTEM WATCHDOG Panel
    Displays the real-time operational status (GREEN/YELLOW/RED)
    of core dashboard components and a Service Dependency Graph.
    """
    database_status = reactive("ONLINE")
    worker_status = reactive("ONLINE")
    ai_server_status = reactive("GREEN")
    disk_health = reactive("NOMINAL")
    memory_health = reactive("NOMINAL")
    filesystem_state = reactive("READ-WRITE")
    btc_node_status = reactive("OFFLINE")

    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "SYSTEM WATCHDOG"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        def get_status_str_and_style(status: str) -> (str, str):
            status_upper = status.upper().strip()
            if status_upper in ("GREEN", "NOMINAL", "ONLINE", "READ-WRITE", "RW", "SYNCED"):
                return status, healthy
            elif status_upper in ("YELLOW", "WARNING", "DEGRADED", "SYNCING"):
                return status, warning
            else:
                return status, error

        content = Text()
        width = self.size.width if self.size.width > 0 else 40

        if width >= 36:
            # Layout A: Wide (4 rows + dependency graph)
            status, style = get_status_str_and_style(self.database_status)
            content.append(" Database: ", style="white")
            content.append(f"{status:<8}", style=style)
            
            status, style = get_status_str_and_style(self.worker_status)
            content.append(" | Worker: ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.ai_server_status)
            content.append(" AI Serv:  ", style="white")
            content.append(f"{status:<8}", style=style)
            
            status, style = get_status_str_and_style(self.disk_health)
            content.append(" | Disk:   ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.memory_health)
            content.append(" Memory:   ", style="white")
            content.append(f"{status:<8}", style=style)
            
            status, style = get_status_str_and_style(self.filesystem_state)
            fs_lbl = "RW" if "WRITE" in status.upper() else "RO"
            content.append(" | FS:     ", style="white")
            content.append(f"{fs_lbl}\n", style=style)

            status, style = get_status_str_and_style(self.btc_node_status)
            btc_lbl = "SYNCED" if "SYNCED" in status.upper() else ("SYNCING" if "SYNCING" in status.upper() else status)
            content.append(" BTC Node: ", style="white")
            content.append(f"{btc_lbl:<8}\n\n", style=style)

            # Service Dependency Graph
            content.append(" [Service Dependency Graph]\n", style="white")
            
            db_s = "🟢" if self.database_status == "ONLINE" else "🔴"
            wrk_s = "🟢" if self.worker_status == "ONLINE" else "🔴"
            btc_s = "🟢" if self.btc_node_status in ("SYNCED", "ONLINE") else ("🟡" if self.btc_node_status == "SYNCING" else "🔴")
            
            content.append(f" {btc_s} BTC Node ──► {db_s} Database ──► {wrk_s} AI Worker\n", style=primary)
        else:
            # Layout B: Narrow (8 rows)
            status, style = get_status_str_and_style(self.database_status)
            content.append(" Database: ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.worker_status)
            content.append(" Worker:   ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.ai_server_status)
            content.append(" AI Serv:  ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.disk_health)
            content.append(" Disk:     ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.memory_health)
            content.append(" Memory:   ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.filesystem_state)
            content.append(" FS State: ", style="white")
            content.append(f"{status}\n", style=style)

            status, style = get_status_str_and_style(self.btc_node_status)
            content.append(" BTC Node: ", style="white")
            content.append(f"{status}\n", style=style)

        return content
