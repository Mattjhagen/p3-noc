from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class BitcoinNodePanel(Static):
    """
    Dashboard Card for self-hosted Bitcoin Core node.
    Shows real-time status, block heights, peer counts,
    and a sync progress bar. Clicking opens Detail View.
    """
    node_status = reactive("OFFLINE")
    chain = reactive("main")
    blocks = reactive(0)
    headers = reactive(0)
    verification_progress = reactive(0.0)
    peer_count = reactive(0)
    disk_used = reactive(0.0)
    disk_total = reactive(11000.0)
    node_version = reactive("Unknown")
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "BITCOIN CORE NODE"

    def on_click(self) -> None:
        """Clicking the card opens the dedicated Bitcoin Operations detail page."""
        from widgets.bitcoin_operations_screen import BitcoinOperationsScreen
        self.app.push_screen(BitcoinOperationsScreen(theme_name=self.current_theme))

    def _make_progress_bar(self, percent: float, width=18) -> str:
        """Creates a unicode block progress bar."""
        filled = min(width, int(percent / (100.0 / width)))
        return "█" * filled + "░" * (width - filled)

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        # Status text and color mapping
        status_clean = self.node_status.upper().strip()
        
        if status_clean in ("SYNCED", "ONLINE"):
            status_disp = "Synced"
            status_style = healthy
        elif status_clean == "SYNCING":
            status_disp = "Syncing"
            status_style = warning
        elif status_clean in ("DEGRADED", "WARNING"):
            status_disp = "Warning"
            status_style = warning
        else:
            status_disp = "Offline"
            status_style = error

        content = Text()
        w = self.size.width if self.size.width > 0 else 40

        # format disk string nicely (e.g. GB -> TB if large)
        disk_total_tb = self.disk_total / 1000.0
        
        if w >= 36:
            # Layout A: 2-column wide layout (4-5 rows)
            content.append(" Status:  ", style="white")
            content.append(f"{status_disp:<9}", style=f"bold {status_style}")
            content.append(" | Peers:   ", style="white")
            content.append(f"{self.peer_count}\n", style=accent)

            content.append(" Blocks:  ", style="white")
            content.append(f"{self.blocks:<9,}", style="white")
            content.append(" | Headers: ", style="white")
            content.append(f"{self.headers:<,}\n", style=accent)

            # Sync progress bar row
            if status_disp == "Syncing":
                bar = self._make_progress_bar(self.verification_progress, width=14)
                content.append(" Sync:    ", style="white")
                content.append(f"[{bar}] {self.verification_progress:>.2f}%\n", style=warning)
            else:
                content.append(" Progress:", style="white")
                content.append(f" 100% (Ver: {self.node_version})\n", style=healthy)

            content.append(" Storage: ", style="white")
            content.append(f"{self.disk_used:.2f} GB / {disk_total_tb:.1f} TB\n", style=accent)
        else:
            # Layout B: Vertical narrow layout (6-7 rows)
            content.append(" Status:   ", style="white")
            content.append(f"{status_disp}\n", style=f"bold {status_style}")
            
            content.append(" Peers:    ", style="white")
            content.append(f"{self.peer_count}\n", style=accent)

            content.append(" Blocks:   ", style="white")
            content.append(f"{self.blocks:,}\n", style="white")

            content.append(" Headers:  ", style="white")
            content.append(f"{self.headers:,}\n", style=accent)

            if status_disp == "Syncing":
                bar = self._make_progress_bar(self.verification_progress, width=10)
                content.append(" Sync:     ", style="white")
                content.append(f"[{bar}] {self.verification_progress:.2f}%\n", style=warning)
            
            content.append(" Disk:     ", style="white")
            content.append(f"{self.disk_used:.2f} GB / {disk_total_tb:.1f} TB\n", style=accent)

        return content
