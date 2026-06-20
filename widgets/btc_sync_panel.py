#!/usr/bin/env python3
import json
import subprocess
from textual.widgets import Static
from textual.reactive import reactive


class BtcSyncPanel(Static):
    DEFAULT_CSS = """
    BtcSyncPanel {
        height: 1fr;
        border: round #00ff41;
        padding: 1 2;
        color: #00ff41;
        background: #0a0a0a;
        margin: 0 1 1 1;
    }
    """

    def __init__(self):
        super().__init__("  BITCOIN CORE  --  NODE SYNC STATUS\n\n  Connecting...")
        self._blocks = 0
        self._headers = 0
        self._progress = 0.0
        self._peers = 0
        self._status = "connecting"

    def on_mount(self) -> None:
        self.set_interval(10, self._schedule_refresh)
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        self.run_worker(self._fetch, thread=True)

    def _fetch(self) -> None:
        try:
            r = subprocess.run(
                ["bitcoin-cli", "getblockchaininfo"],
                capture_output=True, text=True, timeout=5
            )
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip())
            info = json.loads(r.stdout)
            r2 = subprocess.run(
                ["bitcoin-cli", "getconnectioncount"],
                capture_output=True, text=True, timeout=3
            )
            peers = int(r2.stdout.strip()) if r2.returncode == 0 else 0
            self.app.call_from_thread(
                self._update_display,
                info.get("blocks", 0),
                info.get("headers", 0),
                info.get("verificationprogress", 0.0) * 100.0,
                peers,
            )
        except Exception:
            self.app.call_from_thread(self._set_offline)

    def _update_display(self, blocks, headers, progress, peers):
        self._blocks = blocks
        self._headers = headers
        self._progress = progress
        self._peers = peers
        self._status = "synced" if progress >= 99.9 else "syncing"
        self._draw()

    def _set_offline(self):
        self._status = "offline"
        self._draw()

    def _draw(self):
        BAR_W = 50
        pct = self._progress
        filled = min(int(BAR_W * pct / 100.0), BAR_W)
        bar = "#" * filled + "." * (BAR_W - filled)
        if self._status == "offline":
            status_line = "[red]  OFFLINE  --  bitcoin-cli unreachable[/red]"
        elif self._status == "syncing":
            remaining = self._headers - self._blocks
            status_line = f"[yellow]  SYNCING  --  {remaining:,} blocks remaining[/yellow]"
        elif self._status == "synced":
            status_line = "[green]  SYNCED  --  at tip of chain[/green]"
        else:
            status_line = "[dim]  CONNECTING...[/dim]"
        peer_color = "green" if self._peers >= 8 else ("yellow" if self._peers >= 3 else "red")
        lines = [
            "",
            "  BITCOIN CORE  --  NODE SYNC STATUS",
            "",
            status_line,
            "",
            f"  Progress   [{bar}]",
            f"             {pct:.4f}%",
            "",
            f"  Blocks     {self._blocks:>10,}  /  {self._headers:,} headers",
            f"  Peers      [{peer_color}]{self._peers}[/{peer_color}]  connected",
            "",
        ]
        self.update("\n".join(lines))
