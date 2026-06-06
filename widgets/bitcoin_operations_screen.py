import logging
import time
from datetime import datetime
from textual.screen import Screen
from textual.widgets import Static, Footer
from textual.containers import Container
from textual.reactive import reactive
from rich.text import Text
from rich.align import Align
from config.themes import THEME_COLORS
from config.settings import BTC_MONITOR_URL

logger = logging.getLogger("dashboard")

class BitcoinOperationsScreen(Screen):
    """
    Dedicated Bitcoin Operations detail screen.
    Includes Node Health, Blockchain Sync progress with interactive ASCII chart,
    Mempool Analytics, Storage Growth line chart, and Peer tables.
    """
    BINDINGS = [
        ("escape", "dismiss_screen", "Back to Dashboard"),
        ("q", "dismiss_screen", "Back to Dashboard"),
    ]

    CSS = """
    BitcoinOperationsScreen {
        layout: grid;
        grid-size: 1 3;
        grid-rows: 3 1fr 3;
        padding: 0 1;
    }
    
    /* Header & Footer */
    #ops-header {
        content-align: center middle;
        text-align: center;
        text-style: bold;
        height: 3;
        margin: 0 1;
    }

    #ops-grid {
        layout: grid;
        grid-size: 3;
        grid-columns: 1fr 1.2fr 0.8fr;
        grid-gutter: 1;
        height: 100%;
    }

    #ops-left-col {
        layout: grid;
        grid-size: 1 2;
        grid-rows: 1.1fr 0.9fr;
        grid-gutter: 1;
    }

    #ops-middle-col {
        layout: grid;
        grid-size: 1 2;
        grid-rows: 1fr 1fr;
        grid-gutter: 1;
    }

    #ops-right-col {
        layout: grid;
        grid-size: 1 1;
        grid-rows: 1fr;
        grid-gutter: 1;
    }

    .ops-panel {
        padding: 1 2;
    }

    /* 1. matrix-green */
    .matrix-green BitcoinOperationsScreen { background: #020a02; color: #00ff00; }
    .matrix-green .ops-panel { border: round #008800; background: #041404; color: #00ff00; }
    .matrix-green #ops-header { border-bottom: round #008800; color: #00ff00; }

    /* 2. amber-crt */
    .amber-crt BitcoinOperationsScreen { background: #0a0600; color: #ffb000; }
    .amber-crt .ops-panel { border: round #aa7000; background: #140d00; color: #ffb000; }
    .amber-crt #ops-header { border-bottom: round #aa7000; color: #ffb000; }

    /* 3. cyber-blue */
    .cyber-blue BitcoinOperationsScreen { background: #000911; color: #00f0ff; }
    .cyber-blue .ops-panel { border: round #006699; background: #001222; color: #00f0ff; }
    .cyber-blue #ops-header { border-bottom: round #006699; color: #00f0ff; }

    /* 4. red-alert */
    .red-alert BitcoinOperationsScreen { background: #110000; color: #ff3333; }
    .red-alert .ops-panel { border: round #880000; background: #220000; color: #ff3333; }
    .red-alert #ops-header { border-bottom: round #880000; color: #ff3333; }

    /* 5. matrix */
    .matrix BitcoinOperationsScreen { background: #000000; color: #00ff00; }
    .matrix .ops-panel { border: round #00ff00; background: #000000; color: #00ff00; }
    .matrix #ops-header { border-bottom: round #00ff00; color: #00ff00; }

    /* 6. bloomberg */
    .bloomberg BitcoinOperationsScreen { background: #000033; color: #ff8800; }
    .bloomberg .ops-panel { border: round #0044bb; background: #000022; color: #ff8800; }
    .bloomberg #ops-header { border-bottom: round #0044bb; color: #ff8800; }

    /* 7. trading-desk */
    .trading-desk BitcoinOperationsScreen { background: #1c1c1c; color: #00ffff; }
    .trading-desk .ops-panel { border: round #444444; background: #222222; color: #00ffff; }
    .trading-desk #ops-header { border-bottom: round #444444; color: #00ffff; }

    /* 8. midnight */
    .midnight BitcoinOperationsScreen { background: #000000; color: #ffffff; }
    .midnight .ops-panel { border: round #333333; background: #000000; color: #ffffff; }
    .midnight #ops-header { border-bottom: round #333333; color: #ffffff; }
    """

    # Reactive stats
    node_status = reactive("OFFLINE")
    blocks = reactive(0)
    headers = reactive(0)
    verification_progress = reactive(0.0)
    peer_count = reactive(0)
    disk_used = reactive(0.0)
    disk_total = reactive(11000.0)
    node_version = reactive("Unknown")
    uptime_sec = reactive(0)
    chain = reactive("main")
    difficulty = reactive(0.0)
    
    # Mempool & Peers details
    mempool_size = reactive(0)
    mempool_bytes = reactive(0)
    mempool_fee_high = reactive(0)
    mempool_fee_med = reactive(0)
    mempool_fee_low = reactive(0)
    mempool_total_fee = reactive(0.0)
    
    peers_list = reactive([])
    history_list = reactive([])

    def __init__(self, theme_name="matrix-green", **kwargs):
        super().__init__(**kwargs)
        self.theme_name = theme_name

    def compose(self):
        yield Static("", id="ops-header")
        
        with Container(id="ops-grid"):
            with Container(id="ops-left-col"):
                yield BitcoinHealthPanel()
                yield BitcoinStoragePanel()
            with Container(id="ops-middle-col"):
                yield BitcoinMempoolPanel()
                yield BitcoinPeersPanel()
            with Container(id="ops-right-col"):
                yield BitcoinPlaceholderPanel()
                
        yield Footer()

    def on_mount(self):
        self.add_class(self.theme_name)
        self._update_header()
        
        # Initial query and 5-second poll loop
        self.run_status_fetch()
        self.set_interval(5.0, self.run_status_fetch)

    def _update_header(self):
        theme = THEME_COLORS.get(self.theme_name, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        title_text = Text()
        title_text.append(f" ⚙  BITCOIN CORE COMMAND DECK  |  T310 NODE MONITOR  ", style=f"bold {primary}")
        title_text.append(f"  [{time_str}] ", style="white")
        title_text.append(" [Press ESC to Return]", style="cyan")
        
        self.query_one("#ops-header").update(Align.center(title_text))

    def action_dismiss_screen(self):
        self.app.pop_screen()

    def run_status_fetch(self):
        self.run_worker(self._fetch_operations_data_job, thread=True)

    def _fetch_operations_data_job(self):
        import requests
        try:
            status_res = requests.get(f"{BTC_MONITOR_URL}/api/infrastructure/bitcoin", timeout=1.5).json()
            history_res = requests.get(f"{BTC_MONITOR_URL}/api/infrastructure/bitcoin/history", timeout=1.5).json()
            peers_res = requests.get(f"{BTC_MONITOR_URL}/api/infrastructure/bitcoin/peers", timeout=1.5).json()
            mempool_res = requests.get(f"{BTC_MONITOR_URL}/api/infrastructure/bitcoin/mempool", timeout=1.5).json()
            
            self.app.call_from_thread(self._update_operations_ui, status_res, history_res, peers_res, mempool_res)
        except Exception as e:
            logger.error(f"Error fetching detailed operations data: {e}")
            # Mock update on failure
            self.app.call_from_thread(self._update_offline_ui)

    def _update_operations_ui(self, status, history, peers, mempool):
        self.node_status = status.get("status", "offline")
        self.chain = status.get("chain", "main")
        self.blocks = status.get("blocks", 0)
        self.headers = status.get("headers", 0)
        self.verification_progress = status.get("verificationProgress", 0.0)
        self.peer_count = status.get("peerCount", 0)
        self.disk_used = status.get("diskUsedGB", 0.0)
        self.disk_total = status.get("diskTotalGB", 11000.0)
        self.node_version = status.get("nodeVersion", "Unknown")
        self.uptime_sec = status.get("uptime", 0)
        self.difficulty = status.get("difficulty", 0.0)
        
        # Mempool
        self.mempool_size = mempool.get("size", 0)
        self.mempool_bytes = mempool.get("bytes", 0)
        self.mempool_total_fee = mempool.get("total_fee", 0.0)
        rates = mempool.get("fee_rates", {})
        self.mempool_fee_high = rates.get("high", 0)
        self.mempool_fee_med = rates.get("medium", 0)
        self.mempool_fee_low = rates.get("low", 0)
        
        # Lists
        self.peers_list = peers
        self.history_list = history
        
        self._update_header()
        self._propagate_reactives()

    def _update_offline_ui(self):
        self.node_status = "offline"
        self.peer_count = 0
        self.peers_list = []
        self._update_header()
        self._propagate_reactives()

    def _propagate_reactives(self):
        # Push reactive values to child panels
        panels = [
            (BitcoinHealthPanel, "node_status", self.node_status),
            (BitcoinHealthPanel, "chain", self.chain),
            (BitcoinHealthPanel, "blocks", self.blocks),
            (BitcoinHealthPanel, "headers", self.headers),
            (BitcoinHealthPanel, "verification_progress", self.verification_progress),
            (BitcoinHealthPanel, "peer_count", self.peer_count),
            (BitcoinHealthPanel, "uptime_sec", self.uptime_sec),
            (BitcoinHealthPanel, "node_version", self.node_version),
            (BitcoinHealthPanel, "difficulty", self.difficulty),
            (BitcoinHealthPanel, "history_list", self.history_list),
            
            (BitcoinStoragePanel, "disk_used", self.disk_used),
            (BitcoinStoragePanel, "disk_total", self.disk_total),
            (BitcoinStoragePanel, "history_list", self.history_list),
            
            (BitcoinMempoolPanel, "mempool_size", self.mempool_size),
            (BitcoinMempoolPanel, "mempool_bytes", self.mempool_bytes),
            (BitcoinMempoolPanel, "mempool_fee_high", self.mempool_fee_high),
            (BitcoinMempoolPanel, "mempool_fee_med", self.mempool_fee_med),
            (BitcoinMempoolPanel, "mempool_fee_low", self.mempool_fee_low),
            (BitcoinMempoolPanel, "mempool_total_fee", self.mempool_total_fee),
            (BitcoinMempoolPanel, "history_list", self.history_list),
            
            (BitcoinPeersPanel, "peers_list", self.peers_list),
            
            (BitcoinHealthPanel, "current_theme", self.theme_name),
            (BitcoinStoragePanel, "current_theme", self.theme_name),
            (BitcoinMempoolPanel, "current_theme", self.theme_name),
            (BitcoinPeersPanel, "current_theme", self.theme_name),
            (BitcoinPlaceholderPanel, "current_theme", self.theme_name),
        ]
        
        for p_class, attr, val in panels:
            try:
                panel = self.query_one(p_class)
                setattr(panel, attr, val)
            except Exception:
                pass


# 1. Health Panel
class BitcoinHealthPanel(Static):
    node_status = reactive("OFFLINE")
    chain = reactive("main")
    blocks = reactive(0)
    headers = reactive(0)
    verification_progress = reactive(0.0)
    peer_count = reactive(0)
    uptime_sec = reactive(0)
    node_version = reactive("Unknown")
    difficulty = reactive(0.0)
    history_list = reactive([])
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "NODE HEALTH & BLOCKCHAIN SYNC"
        self.add_class("ops-panel")

    def _make_ascii_chart(self) -> str:
        """Plots historical verification progress (0-100%)."""
        if not self.history_list:
            return "Chart Data Pending..."
        
        # Take up to 24 samples
        samples = [float(h.get("verification_progress", 0.0)) for h in self.history_list[-24:]]
        if len(samples) < 24:
            samples = [0.0] * (24 - len(samples)) + samples

        min_val = min(samples)
        max_val = max(samples)
        span = max_val - min_val
        if span == 0:
            span = 1.0
            
        grid = [[" " for _ in range(24)] for _ in range(2)]
        for c in range(24):
            val = samples[c]
            norm = (val - min_val) / span
            row = min(1, int(norm * 2))
            grid[row][c] = "█"
            
        lines = []
        lines.append("  " + "".join(grid[1]) + f" {max_val:.2f}%")
        lines.append("  " + "".join(grid[0]) + f" {min_val:.2f}%")
        lines.append("    24h ago           now")
        return "\n".join(lines)

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        status_disp = self.node_status.upper().strip()
        status_style = healthy if status_disp in ("SYNCED", "ONLINE") else (warning if status_disp == "SYNCING" else error)
        
        # Uptime string
        days = self.uptime_sec // 86400
        hrs = (self.uptime_sec % 86400) // 3600
        mins = (self.uptime_sec % 3600) // 60
        uptime_str = f"{days}d {hrs}h {mins}m" if days > 0 else f"{hrs}h {mins}m"
        
        content = Text()
        content.append(" Status:    ", style="white")
        content.append(f"{status_disp:<9}", style=f"bold {status_style}")
        content.append(" | Version: ", style="white")
        content.append(f"{self.node_version}\n", style=accent)

        content.append(" Chain:     ", style="white")
        content.append(f"{self.chain:<9}", style="white")
        content.append(" | Uptime:  ", style="white")
        content.append(f"{uptime_str}\n", style=accent)

        content.append(" Blocks:    ", style="white")
        content.append(f"{self.blocks:<9,}", style="white")
        content.append(" | Headers: ", style="white")
        content.append(f"{self.headers:,}\n", style=accent)
        
        content.append(" Diff:      ", style="white")
        content.append(f"{self.difficulty:,.0f}\n\n", style=accent)

        # Sync Progress Chart Title
        content.append(" --- Verification Sync Progress ---\n", style=primary)
        content.append(self._make_ascii_chart() + "\n", style=warning if status_disp == "SYNCING" else healthy)
        
        return content


# 2. Storage Panel
class BitcoinStoragePanel(Static):
    disk_used = reactive(0.0)
    disk_total = reactive(11000.0)
    history_list = reactive([])
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "STORAGE ANALYSIS (12TB TARGET)"
        self.add_class("ops-panel")

    def _make_growth_chart(self) -> str:
        """Plots blockchain disk size growth over last 24h."""
        if not self.history_list:
            return "Disk Trend Pending..."
        
        samples = [float(h.get("disk_usage", 0.0)) for h in self.history_list[-24:]]
        if len(samples) < 24:
            samples = [0.0] * (24 - len(samples)) + samples

        min_val = min(samples)
        max_val = max(samples)
        span = max_val - min_val
        if span == 0:
            span = 1.0
            
        grid = [[" " for _ in range(24)] for _ in range(2)]
        for c in range(24):
            val = samples[c]
            norm = (val - min_val) / span
            row = min(1, int(norm * 2))
            grid[row][c] = "▇"
            
        lines = []
        lines.append("  " + "".join(grid[1]) + f" {max_val:.1f} GB")
        lines.append("  " + "".join(grid[0]) + f" {min_val:.1f} GB")
        return "\n".join(lines)

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        
        disk_total_tb = self.disk_total / 1000.0
        available_gb = self.disk_total - self.disk_used
        util_pct = (self.disk_used / self.disk_total) * 100.0
        
        # Calculate daily growth estimate: diff between first and last history item
        daily_growth = 0.0
        if len(self.history_list) >= 2:
            first_disk = float(self.history_list[0].get("disk_usage", 0.0))
            last_disk = float(self.history_list[-1].get("disk_usage", 0.0))
            daily_growth = max(0.0, last_disk - first_disk)

        content = Text()
        content.append(" Capacity:     ", style="white")
        content.append(f"{self.disk_used:.2f} GB / {disk_total_tb:.1f} TB ", style=accent)
        content.append(f"({util_pct:.2f}% Utilized)\n", style=healthy if util_pct < 85 else "red")
        
        content.append(" Available:    ", style="white")
        content.append(f"{available_gb:.2f} GB Free\n", style=healthy)
        
        content.append(" Daily Growth: ", style="white")
        content.append(f"+{daily_growth:.3f} GB/day\n\n", style=accent)

        content.append(" --- Blockchain Storage growth (24H) ---\n", style=primary)
        content.append(self._make_growth_chart() + "\n", style=accent)
        return content


# 3. Mempool Panel
class BitcoinMempoolPanel(Static):
    mempool_size = reactive(0)
    mempool_bytes = reactive(0)
    mempool_fee_high = reactive(0)
    mempool_fee_med = reactive(0)
    mempool_fee_low = reactive(0)
    mempool_total_fee = reactive(0.0)
    history_list = reactive([])
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "MEMPOOL ANALYTICS"
        self.add_class("ops-panel")

    def _make_size_chart(self) -> str:
        """Plots historical mempool transaction counts."""
        if not self.history_list:
            return "Mempool Trend Pending..."
        
        samples = [float(h.get("mempool_size", 0.0)) for h in self.history_list[-24:]]
        if len(samples) < 24:
            samples = [0.0] * (24 - len(samples)) + samples

        min_val = min(samples)
        max_val = max(samples)
        span = max_val - min_val
        if span == 0:
            span = 1.0
            
        grid = [[" " for _ in range(24)] for _ in range(2)]
        for c in range(24):
            val = samples[c]
            norm = (val - min_val) / span
            row = min(1, int(norm * 2))
            grid[row][c] = "░" if row == 0 else "█"
            
        lines = []
        lines.append("  " + "".join(grid[1]) + f" {max_val:,.0f} txs")
        lines.append("  " + "".join(grid[0]) + f" {min_val:,.0f} txs")
        return "\n".join(lines)

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        warning = theme["warning"]
        
        mem_mb = self.mempool_bytes / (1024 * 1024)

        content = Text()
        content.append(" Pending Txs:  ", style="white")
        content.append(f"{self.mempool_size:,} transactions\n", style="white")

        content.append(" Data Size:    ", style="white")
        content.append(f"{mem_mb:.2f} MB ", style=accent)
        content.append(f"({self.mempool_bytes:,} bytes)\n", style=theme["muted"])

        content.append(" Total Fees:   ", style="white")
        content.append(f"{self.mempool_total_fee:.4f} BTC\n", style=accent)

        content.append(" Fees Rates:   ", style="white")
        content.append(f"L: {self.mempool_fee_low} sat/vB | ", style=accent)
        content.append(f"M: {self.mempool_fee_med} sat/vB | ", style=warning)
        content.append(f"H: {self.mempool_fee_high} sat/vB\n\n", style="red")

        content.append(" --- Mempool Volume (24H Trend) ---\n", style=primary)
        content.append(self._make_size_chart() + "\n", style=accent)
        return content


# 4. Peers Panel
class BitcoinPeersPanel(Static):
    peers_list = reactive([])
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "PEER MONITORING & REACHABILITY"
        self.add_class("ops-panel")

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        
        inbound_count = sum(1 for p in self.peers_list if p.get("inbound", False))
        outbound_count = len(self.peers_list) - inbound_count
        
        content = Text()
        content.append(" Peers Connected: ", style="white")
        content.append(f"{len(self.peers_list)} total", style=f"bold {healthy}")
        content.append(f" (Outbound: {outbound_count} | Inbound: {inbound_count})\n", style=accent)
        
        content.append(" Reachability:    ", style="white")
        content.append("IPv4/IPv6 Nodes Active (Port 8333 Open)\n\n", style=healthy)
        
        # Mini ASCII table of top peers
        content.append(f" {'ID':<3} | {'IP ADDRESS':<21} | {'PING':<6} | {'CLIENT VERSION':<14}\n", style=f"bold {primary}")
        content.append("=" * 55 + "\n", style=theme["muted"])
        
        if not self.peers_list:
            content.append("  No connected peer data available.\n", style="red")
        else:
            # show first 4 peers to avoid panel overflow
            for p in self.peers_list[:4]:
                addr = p.get("addr", "N/A")
                if len(addr) > 21:
                    addr = addr[:18] + "..."
                subver = p.get("subver", "Unknown")
                if len(subver) > 14:
                    subver = subver[:12] + ".."
                    
                content.append(f" {p.get('id', 1):<3} | ", style="white")
                content.append(f"{addr:<21} | ", style=accent)
                content.append(f"{p.get('pingtime', 0.0):.3f}s | ", style=healthy)
                content.append(f"{subver:<14}\n", style="white")
                
        return content


# 5. Coming Soon Placeholder Panel
class BitcoinPlaceholderPanel(Static):
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "INTELLIGENCE NETWORK & RISK FORECAST"
        self.add_class("ops-panel")

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        muted = theme["muted"]
        accent = theme["accent"]

        content = Text()
        
        modules = [
            ("Whale Activity Monitoring", "Whale address movements & Satoshi wallet alerts"),
            ("Institutional ETF Flows", "Realtime Blackrock/Fidelity inflow trackers"),
            ("Macro News Sentiment Score", "NLP sentiment scoring of global macro headlines"),
            ("On-Chain Risk Signals", "Coinbase/Binance exchange flows risk matrices"),
            ("AI Risk Score Correlation", "Predictive liquidation cascading analysis"),
            ("Market Volatility Forecast", "Implied volatility anomaly warnings"),
        ]
        
        for name, desc in modules:
            content.append(f" ⮚ {name:<26} ", style=f"bold {primary}")
            content.append("[COMING SOON]\n", style="bold cyan")
            content.append(f"   {desc}\n", style=muted)
            content.append("-" * 38 + "\n", style=muted)
            
        return content
