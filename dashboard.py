#!/usr/bin/env python3
import argparse
import sys
import os
import time
import subprocess
import psutil
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Button, Static
from textual.reactive import reactive
from textual.screen import ModalScreen

# Import configuration settings and themes
from config.settings import REFRESH_RATES, OLLAMA_MODEL, OLLAMA_REMOTE
from config.themes import THEMES, THEME_NAMES
from services.db_service import DBService
from services.log_service import LogService
from services.ollama_service import OllamaService
from services.feed_service import FeedService
from services.btc_ticker_service import BTCTickerService
from services.recovery_service import RecoveryService
from services.autopilot_service import AutopilotService
from services.routing_service import RoutingService
from services.ai_server_service import AiServerService

# Import custom widgets
from widgets.header import HeaderWidget
from widgets.system_panel import SystemPanel
from widgets.throughput_panel import ThroughputPanel
from widgets.ollama_panel import OllamaPanel
from widgets.alert_panel import AlertPanel
from widgets.risk_radar import RiskRadar
from widgets.news_feed import NewsFeed
from widgets.log_panel import LogPanel
from widgets.ticker import TickerWidget
from widgets.sys_metrics_panel import SysMetricsPanel
from widgets.risk_trend_panel import RiskTrendPanel
from widgets.confirmation_dialog import ConfirmationDialog
from widgets.runbook_panel import RunbookPanel
from widgets.autopilot_panel import AutopilotPanel
from widgets.ai_server_status_panel import AiServerStatusPanel
from widgets.watchdog_panel import WatchdogPanel

import logging
logger = logging.getLogger("dashboard")

class CallableBool:
    def __init__(self, value: bool):
        self.value = bool(value)
    def __bool__(self) -> bool:
        return self.value
    def __call__(self) -> bool:
        return self.value
    def __eq__(self, other) -> bool:
        return self.value == other
    def __repr__(self) -> str:
        return repr(self.value)
    def __str__(self) -> str:
        return str(self.value)

def safe_widget(widget, app_ref):
    """
    Wraps a widget's key lifecycle and render methods to catch exceptions,
    automatically activating Safe Mode on the app instead of crashing.
    """
    original_on_mount = getattr(widget, "on_mount", None)
    original_compose = getattr(widget, "compose", None)
    original_render = getattr(widget, "render", None)

    def safe_on_mount(*args, **kwargs):
        try:
            if original_on_mount:
                return original_on_mount(*args, **kwargs)
        except Exception as e:
            logger.error(f"SafeMode: Widget {widget.__class__.__name__} crashed during on_mount: {e}")
            app_ref.activate_startup_safe_mode(f"{widget.__class__.__name__} mount crash: {e}")
            try:
                widget.display = False
            except Exception:
                pass

    def safe_compose(*args, **kwargs):
        try:
            if original_compose:
                return original_compose(*args, **kwargs)
        except Exception as e:
            logger.error(f"SafeMode: Widget {widget.__class__.__name__} crashed during compose: {e}")
            app_ref.activate_startup_safe_mode(f"{widget.__class__.__name__} compose crash: {e}")
            return []

    def safe_render(*args, **kwargs):
        try:
            if original_render:
                return original_render(*args, **kwargs)
        except Exception as e:
            logger.error(f"SafeMode: Widget {widget.__class__.__name__} crashed during render: {e}")
            app_ref.activate_startup_safe_mode(f"{widget.__class__.__name__} render crash: {e}")
            from rich.text import Text
            return Text(f"[{widget.__class__.__name__} CRASHED]", style="bold red")

    if original_on_mount:
        widget.on_mount = safe_on_mount
    else:
        widget.on_mount = safe_on_mount
    if original_compose:
        widget.compose = safe_compose
    if original_render:
        widget.render = safe_render

    return widget

class P3NocApp(App):
    """
    P3 NOC — Bitcoin Intelligence Operations Center TUI Dashboard (v4).
    Includes Operator Actions panel, recovery services, and smart recommendations.
    """
    CSS = """
    /* Theme colorways - Explicitly styled to avoid CSS variables */
    
    /* 1. matrix-green */
    .matrix-green Screen {
        background: #020a02;
        color: #00ff00;
    }
    .matrix-green SystemPanel, .matrix-green ThroughputPanel, .matrix-green SysMetricsPanel,
    .matrix-green RiskRadar, .matrix-green RiskTrendPanel, .matrix-green RunbookPanel,
    .matrix-green OllamaPanel, .matrix-green AlertPanel, .matrix-green AutopilotPanel,
    .matrix-green NewsFeed, .matrix-green LogPanel, .matrix-green TickerWidget {
        border: round #008800;
        background: #041404;
        color: #00ff00;
    }
    .matrix-green SystemPanel:focus, .matrix-green ThroughputPanel:focus, .matrix-green SysMetricsPanel:focus,
    .matrix-green RiskRadar:focus, .matrix-green RiskTrendPanel:focus, .matrix-green RunbookPanel:focus,
    .matrix-green OllamaPanel:focus, .matrix-green AlertPanel:focus, .matrix-green AutopilotPanel:focus,
    .matrix-green NewsFeed:focus, .matrix-green LogPanel:focus, .matrix-green TickerWidget:focus {
        border: double #00ff00;
    }
    .matrix-green.wallboard-mode SystemPanel, .matrix-green.wallboard-mode ThroughputPanel, .matrix-green.wallboard-mode SysMetricsPanel,
    .matrix-green.wallboard-mode RiskRadar, .matrix-green.wallboard-mode RiskTrendPanel, .matrix-green.wallboard-mode RunbookPanel,
    .matrix-green.wallboard-mode OllamaPanel, .matrix-green.wallboard-mode AlertPanel, .matrix-green.wallboard-mode AutopilotPanel,
    .matrix-green.wallboard-mode NewsFeed, .matrix-green.wallboard-mode LogPanel, .matrix-green.wallboard-mode TickerWidget {
        border: double #00ff00;
    }
    .matrix-green TickerWidget {
        background: #041404;
    }

    /* 2. amber-crt */
    .amber-crt Screen {
        background: #0a0600;
        color: #ffb000;
    }
    .amber-crt SystemPanel, .amber-crt ThroughputPanel, .amber-crt SysMetricsPanel,
    .amber-crt RiskRadar, .amber-crt RiskTrendPanel, .amber-crt RunbookPanel,
    .amber-crt OllamaPanel, .amber-crt AlertPanel, .amber-crt AutopilotPanel,
    .amber-crt NewsFeed, .amber-crt LogPanel, .amber-crt TickerWidget {
        border: round #aa7000;
        background: #140d00;
        color: #ffb000;
    }
    .amber-crt SystemPanel:focus, .amber-crt ThroughputPanel:focus, .amber-crt SysMetricsPanel:focus,
    .amber-crt RiskRadar:focus, .amber-crt RiskTrendPanel:focus, .amber-crt RunbookPanel:focus,
    .amber-crt OllamaPanel:focus, .amber-crt AlertPanel:focus, .amber-crt AutopilotPanel:focus,
    .amber-crt NewsFeed:focus, .amber-crt LogPanel:focus, .amber-crt TickerWidget:focus {
        border: double #ffb000;
    }
    .amber-crt.wallboard-mode SystemPanel, .amber-crt.wallboard-mode ThroughputPanel, .amber-crt.wallboard-mode SysMetricsPanel,
    .amber-crt.wallboard-mode RiskRadar, .amber-crt.wallboard-mode RiskTrendPanel, .amber-crt.wallboard-mode RunbookPanel,
    .amber-crt.wallboard-mode OllamaPanel, .amber-crt.wallboard-mode AlertPanel, .amber-crt.wallboard-mode AutopilotPanel,
    .amber-crt.wallboard-mode NewsFeed, .amber-crt.wallboard-mode LogPanel, .amber-crt.wallboard-mode TickerWidget {
        border: double #ffb000;
    }
    .amber-crt TickerWidget {
        background: #140d00;
    }

    /* 3. cyber-blue */
    .cyber-blue Screen {
        background: #000911;
        color: #00f0ff;
    }
    .cyber-blue SystemPanel, .cyber-blue ThroughputPanel, .cyber-blue SysMetricsPanel,
    .cyber-blue RiskRadar, .cyber-blue RiskTrendPanel, .cyber-blue RunbookPanel,
    .cyber-blue OllamaPanel, .cyber-blue AlertPanel, .cyber-blue AutopilotPanel,
    .cyber-blue NewsFeed, .cyber-blue LogPanel, .cyber-blue TickerWidget {
        border: round #006699;
        background: #001222;
        color: #00f0ff;
    }
    .cyber-blue SystemPanel:focus, .cyber-blue ThroughputPanel:focus, .cyber-blue SysMetricsPanel:focus,
    .cyber-blue RiskRadar:focus, .cyber-blue RiskTrendPanel:focus, .cyber-blue RunbookPanel:focus,
    .cyber-blue OllamaPanel:focus, .cyber-blue AlertPanel:focus, .cyber-blue AutopilotPanel:focus,
    .cyber-blue NewsFeed:focus, .cyber-blue LogPanel:focus, .cyber-blue TickerWidget:focus {
        border: double #00f0ff;
    }
    .cyber-blue.wallboard-mode SystemPanel, .cyber-blue.wallboard-mode ThroughputPanel, .cyber-blue.wallboard-mode SysMetricsPanel,
    .cyber-blue.wallboard-mode RiskRadar, .cyber-blue.wallboard-mode RiskTrendPanel, .cyber-blue.wallboard-mode RunbookPanel,
    .cyber-blue.wallboard-mode OllamaPanel, .cyber-blue.wallboard-mode AlertPanel, .cyber-blue.wallboard-mode AutopilotPanel,
    .cyber-blue.wallboard-mode NewsFeed, .cyber-blue.wallboard-mode LogPanel, .cyber-blue.wallboard-mode TickerWidget {
        border: double #00f0ff;
    }
    .cyber-blue TickerWidget {
        background: #001222;
    }

    /* 4. red-alert */
    .red-alert Screen {
        background: #110000;
        color: #ff3333;
    }
    .red-alert SystemPanel, .red-alert ThroughputPanel, .red-alert SysMetricsPanel,
    .red-alert RiskRadar, .red-alert RiskTrendPanel, .red-alert RunbookPanel,
    .red-alert OllamaPanel, .red-alert AlertPanel, .red-alert AutopilotPanel,
    .red-alert NewsFeed, .red-alert LogPanel, .red-alert TickerWidget {
        border: round #880000;
        background: #220000;
        color: #ff3333;
    }
    .red-alert SystemPanel:focus, .red-alert ThroughputPanel:focus, .red-alert SysMetricsPanel:focus,
    .red-alert RiskRadar:focus, .red-alert RiskTrendPanel:focus, .red-alert RunbookPanel:focus,
    .red-alert OllamaPanel:focus, .red-alert AlertPanel:focus, .red-alert AutopilotPanel:focus,
    .red-alert NewsFeed:focus, .red-alert LogPanel:focus, .red-alert TickerWidget:focus {
        border: double #ff3333;
    }
    .red-alert.wallboard-mode SystemPanel, .red-alert.wallboard-mode ThroughputPanel, .red-alert.wallboard-mode SysMetricsPanel,
    .red-alert.wallboard-mode RiskRadar, .red-alert.wallboard-mode RiskTrendPanel, .red-alert.wallboard-mode RunbookPanel,
    .red-alert.wallboard-mode OllamaPanel, .red-alert.wallboard-mode AlertPanel, .red-alert.wallboard-mode AutopilotPanel,
    .red-alert.wallboard-mode NewsFeed, .red-alert.wallboard-mode LogPanel, .red-alert.wallboard-mode TickerWidget {
        border: double #ff3333;
    }
    .red-alert TickerWidget {
        background: #220000;
    }

    /* 5. matrix */
    .matrix Screen {
        background: #000000;
        color: #00ff00;
    }
    .matrix SystemPanel, .matrix ThroughputPanel, .matrix SysMetricsPanel,
    .matrix RiskRadar, .matrix RiskTrendPanel, .matrix RunbookPanel,
    .matrix OllamaPanel, .matrix AlertPanel, .matrix AutopilotPanel,
    .matrix NewsFeed, .matrix LogPanel, .matrix TickerWidget {
        border: round #00ff00;
        background: #000000;
        color: #00ff00;
    }
    .matrix SystemPanel:focus, .matrix ThroughputPanel:focus, .matrix SysMetricsPanel:focus,
    .matrix RiskRadar:focus, .matrix RiskTrendPanel:focus, .matrix RunbookPanel:focus,
    .matrix OllamaPanel:focus, .matrix AlertPanel:focus, .matrix AutopilotPanel:focus,
    .matrix NewsFeed:focus, .matrix LogPanel:focus, .matrix TickerWidget:focus {
        border: double #00ff00;
    }
    .matrix.wallboard-mode SystemPanel, .matrix.wallboard-mode ThroughputPanel, .matrix.wallboard-mode SysMetricsPanel,
    .matrix.wallboard-mode RiskRadar, .matrix.wallboard-mode RiskTrendPanel, .matrix.wallboard-mode RunbookPanel,
    .matrix.wallboard-mode OllamaPanel, .matrix.wallboard-mode AlertPanel, .matrix.wallboard-mode AutopilotPanel,
    .matrix.wallboard-mode NewsFeed, .matrix.wallboard-mode LogPanel, .matrix.wallboard-mode TickerWidget {
        border: double #00ff00;
    }
    .matrix TickerWidget {
        background: #000000;
    }

    /* 6. bloomberg */
    .bloomberg Screen {
        background: #000033;
        color: #ff8800;
    }
    .bloomberg SystemPanel, .bloomberg ThroughputPanel, .bloomberg SysMetricsPanel,
    .bloomberg RiskRadar, .bloomberg RiskTrendPanel, .bloomberg RunbookPanel,
    .bloomberg OllamaPanel, .bloomberg AlertPanel, .bloomberg AutopilotPanel,
    .bloomberg NewsFeed, .bloomberg LogPanel, .bloomberg TickerWidget {
        border: round #0044bb;
        background: #000022;
        color: #ff8800;
    }
    .bloomberg SystemPanel:focus, .bloomberg ThroughputPanel:focus, .bloomberg SysMetricsPanel:focus,
    .bloomberg RiskRadar:focus, .bloomberg RiskTrendPanel:focus, .bloomberg RunbookPanel:focus,
    .bloomberg OllamaPanel:focus, .bloomberg AlertPanel:focus, .bloomberg AutopilotPanel:focus,
    .bloomberg NewsFeed:focus, .bloomberg LogPanel:focus, .bloomberg TickerWidget:focus {
        border: double #ff8800;
    }
    .bloomberg.wallboard-mode SystemPanel, .bloomberg.wallboard-mode ThroughputPanel, .bloomberg.wallboard-mode SysMetricsPanel,
    .bloomberg.wallboard-mode RiskRadar, .bloomberg.wallboard-mode RiskTrendPanel, .bloomberg.wallboard-mode RunbookPanel,
    .bloomberg.wallboard-mode OllamaPanel, .bloomberg.wallboard-mode AlertPanel, .bloomberg.wallboard-mode AutopilotPanel,
    .bloomberg.wallboard-mode NewsFeed, .bloomberg.wallboard-mode LogPanel, .bloomberg.wallboard-mode TickerWidget {
        border: double #ff8800;
    }
    .bloomberg TickerWidget {
        background: #000022;
    }

    /* 7. trading-desk */
    .trading-desk Screen {
        background: #1c1c1c;
        color: #00ffff;
    }
    .trading-desk SystemPanel, .trading-desk ThroughputPanel, .trading-desk SysMetricsPanel,
    .trading-desk RiskRadar, .trading-desk RiskTrendPanel, .trading-desk RunbookPanel,
    .trading-desk OllamaPanel, .trading-desk AlertPanel, .trading-desk AutopilotPanel,
    .trading-desk NewsFeed, .trading-desk LogPanel, .trading-desk TickerWidget {
        border: round #444444;
        background: #222222;
        color: #00ffff;
    }
    .trading-desk SystemPanel:focus, .trading-desk ThroughputPanel:focus, .trading-desk SysMetricsPanel:focus,
    .trading-desk RiskRadar:focus, .trading-desk RiskTrendPanel:focus, .trading-desk RunbookPanel:focus,
    .trading-desk OllamaPanel:focus, .trading-desk AlertPanel:focus, .trading-desk AutopilotPanel:focus,
    .trading-desk NewsFeed:focus, .trading-desk LogPanel:focus, .trading-desk TickerWidget:focus {
        border: double #00ffff;
    }
    .trading-desk.wallboard-mode SystemPanel, .trading-desk.wallboard-mode ThroughputPanel, .trading-desk.wallboard-mode SysMetricsPanel,
    .trading-desk.wallboard-mode RiskRadar, .trading-desk.wallboard-mode RiskTrendPanel, .trading-desk.wallboard-mode RunbookPanel,
    .trading-desk.wallboard-mode OllamaPanel, .trading-desk.wallboard-mode AlertPanel, .trading-desk.wallboard-mode AutopilotPanel,
    .trading-desk.wallboard-mode NewsFeed, .trading-desk.wallboard-mode LogPanel, .trading-desk.wallboard-mode TickerWidget {
        border: double #00ffff;
    }
    .trading-desk TickerWidget {
        background: #222222;
    }

    /* 8. midnight */
    .midnight Screen {
        background: #000000;
        color: #ffffff;
    }
    .midnight SystemPanel, .midnight ThroughputPanel, .midnight SysMetricsPanel,
    .midnight RiskRadar, .midnight RiskTrendPanel, .midnight RunbookPanel,
    .midnight OllamaPanel, .midnight AlertPanel, .midnight AutopilotPanel,
    .midnight NewsFeed, .midnight LogPanel, .midnight TickerWidget {
        border: round #333333;
        background: #000000;
        color: #ffffff;
    }
    .midnight SystemPanel:focus, .midnight ThroughputPanel:focus, .midnight SysMetricsPanel:focus,
    .midnight RiskRadar:focus, .midnight RiskTrendPanel:focus, .midnight RunbookPanel:focus,
    .midnight OllamaPanel:focus, .midnight AlertPanel:focus, .midnight AutopilotPanel:focus,
    .midnight NewsFeed:focus, .midnight LogPanel:focus, .midnight TickerWidget:focus {
        border: double #ffffff;
    }
    .midnight.wallboard-mode SystemPanel, .midnight.wallboard-mode ThroughputPanel, .midnight.wallboard-mode SysMetricsPanel,
    .midnight.wallboard-mode RiskRadar, .midnight.wallboard-mode RiskTrendPanel, .midnight.wallboard-mode RunbookPanel,
    .midnight.wallboard-mode OllamaPanel, .midnight.wallboard-mode AlertPanel, .midnight.wallboard-mode AutopilotPanel,
    .midnight.wallboard-mode NewsFeed, .midnight.wallboard-mode LogPanel, .midnight.wallboard-mode TickerWidget {
        border: double #ffffff;
    }
    .midnight TickerWidget {
        background: #000000;
    }

    HeaderWidget {
        height: auto;
        margin: 0 1;
        background: transparent;
    }

    #grid-middle {
        layout: grid;
        grid-size: 3;
        grid-columns: 1fr 1.5fr 1fr;
        height: 28;
        margin: 0 1 1 1;
    }

    #left-col {
        layout: grid;
        grid-size: 1 3;
        grid-rows: 1fr 1fr 1fr;
        grid-gutter: 1;
    }

    #middle-col {
        layout: grid;
        grid-size: 1 3;
        grid-rows: 1fr 1fr 1fr;
        grid-gutter: 1;
    }

    #right-col {
        layout: grid;
        grid-size: 1 5;
        grid-rows: 1fr 1fr 1.2fr 1.1fr 1.1fr; /* Ollama, Alerts, Autopilot, AiServerStatus, Watchdog */
        grid-gutter: 1;
    }

    NewsFeed {
        height: 9;
        margin: 0 1 1 1;
    }

    LogPanel {
        height: 9;
        margin: 0 1 1 1;
    }

    TickerWidget {
        height: 3;
        margin: 0 1;
    }

    /* AiServerStatusPanel & WatchdogPanel Theme styles */
    .matrix-green AiServerStatusPanel, .matrix-green WatchdogPanel {
        border: round #008800;
        background: #041404;
        color: #00ff00;
    }
    .matrix-green AiServerStatusPanel:focus, .matrix-green WatchdogPanel:focus {
        border: double #00ff00;
    }
    .matrix-green.wallboard-mode AiServerStatusPanel, .matrix-green.wallboard-mode WatchdogPanel {
        border: double #00ff00;
    }

    .amber-crt AiServerStatusPanel, .amber-crt WatchdogPanel {
        border: round #aa7000;
        background: #140d00;
        color: #ffb000;
    }
    .amber-crt AiServerStatusPanel:focus, .amber-crt WatchdogPanel:focus {
        border: double #ffb000;
    }
    .amber-crt.wallboard-mode AiServerStatusPanel, .amber-crt.wallboard-mode WatchdogPanel {
        border: double #ffb000;
    }

    .cyber-blue AiServerStatusPanel, .cyber-blue WatchdogPanel {
        border: round #006699;
        background: #001222;
        color: #00f0ff;
    }
    .cyber-blue AiServerStatusPanel:focus, .cyber-blue WatchdogPanel:focus {
        border: double #00f0ff;
    }
    .cyber-blue.wallboard-mode AiServerStatusPanel, .cyber-blue.wallboard-mode WatchdogPanel {
        border: double #00f0ff;
    }

    .red-alert AiServerStatusPanel, .red-alert WatchdogPanel {
        border: round #880000;
        background: #220000;
        color: #ff3333;
    }
    .red-alert AiServerStatusPanel:focus, .red-alert WatchdogPanel:focus {
        border: double #ff3333;
    }
    .red-alert.wallboard-mode AiServerStatusPanel, .red-alert.wallboard-mode WatchdogPanel {
        border: double #ff3333;
    }

    .matrix AiServerStatusPanel, .matrix WatchdogPanel {
        border: round #00ff00;
        background: #000000;
        color: #00ff00;
    }
    .matrix AiServerStatusPanel:focus, .matrix WatchdogPanel:focus {
        border: double #00ff00;
    }
    .matrix.wallboard-mode AiServerStatusPanel, .matrix.wallboard-mode WatchdogPanel {
        border: double #00ff00;
    }

    .bloomberg AiServerStatusPanel, .bloomberg WatchdogPanel {
        border: round #0044bb;
        background: #000022;
        color: #ff8800;
    }
    .bloomberg AiServerStatusPanel:focus, .bloomberg WatchdogPanel:focus {
        border: double #ff8800;
    }
    .bloomberg.wallboard-mode AiServerStatusPanel, .bloomberg.wallboard-mode WatchdogPanel {
        border: double #ff8800;
    }

    .trading-desk AiServerStatusPanel, .trading-desk WatchdogPanel {
        border: round #444444;
        background: #222222;
        color: #00ffff;
    }
    .trading-desk AiServerStatusPanel:focus, .trading-desk WatchdogPanel:focus {
        border: double #00ffff;
    }
    .trading-desk.wallboard-mode AiServerStatusPanel, .trading-desk.wallboard-mode WatchdogPanel {
        border: double #00ffff;
    }

    .midnight AiServerStatusPanel, .midnight WatchdogPanel {
        border: round #333333;
        background: #000000;
        color: #ffffff;
    }
    .midnight AiServerStatusPanel:focus, .midnight WatchdogPanel:focus {
        border: double #ffffff;
    }
    .midnight.wallboard-mode AiServerStatusPanel, .midnight.wallboard-mode WatchdogPanel {
        border: double #ffffff;
    }
    """

    # Keyboard Bindings
    BINDINGS = [
        ("l", "focus_logs", "Focus Logs"),
        ("n", "focus_news", "Focus News"),
        ("r", "focus_risk", "Focus Risk"),
        ("w", "show_weekly_report", "Weekly Report"),
        ("f2", "next_theme", "Cycle Theme"),
        ("f3", "toggle_compact", "Toggle Compact"),
        ("f4", "toggle_fullscreen_logs", "Fullscreen Logs"),
        ("f5", "refresh_data", "Refresh Data"),
        ("f6", "restart_worker", "Restart Worker"),
        ("f7", "restart_ingest", "Restart Ingest"),
        ("f8", "requeue_failed", "Requeue Failed"),
        ("f9", "clear_stuck", "Clear Stuck"),
        ("f10", "restart_ollama", "Restart Ollama"),
        ("f11", "warm_model", "Warm Model Cache"),
        ("f12", "health_recovery", "Full Health Recovery"),
        ("q", "quit_app", "Quit"),
    ]

    def __init__(self, wallboard_mode=False, **kwargs):
        super().__init__(**kwargs)
        self.wallboard_mode = wallboard_mode
        self.theme_index = 0
        self.logs_fullscreen = False
        
        # Initialize services
        self.db_service = DBService()
        self.log_service = LogService()
        self.ollama_service = OllamaService()
        self.feed_service = FeedService()
        self.ticker_service = BTCTickerService()
        self.recovery_service = RecoveryService()
        
        self.routing_service = RoutingService()
        self.autopilot_service = AutopilotService(
            db_service=self.db_service,
            recovery_service=self.recovery_service,
            feed_service=self.feed_service,
            ollama_service=self.ollama_service,
            routing_service=self.routing_service
        )
        self.ai_server_service = AiServerService()
        
        # Runtime status states
        self.worker_online = True
        self.db_online = True
        self.ollama_online = True
        self.ingest_online = True
        self.ai_server_status = "GREEN"
        self.ai_server_first_offline = None
        self.ai_server_flash_toggle = False
        
        # Hardware fault states & Watchdog diagnostics
        self.app_start_time = time.time()
        self.disk_percent = 0.0
        self.fs_readonly = False
        self.ipmi_fault = False
        self.raid_failure = False
        self.ollama_first_offline = None
        self.ollama_is_critical = False
        self.logo_flash_phase = 0
        self.oldest_processing_age = 0.0
        self.ai_server_tags_first_fail = None
        self.ai_server_critical_active = False
        self.status_fetched_once = False
        
        # Cache OLLAMA configurations
        self.ollama_model = OLLAMA_MODEL
        
        # Startup checks failures cache
        self.startup_errors = []
        
        # Audit states
        self.last_audit_date = None
        self.latest_report_path = None
        self.startup_safe_mode_active = False

    def safe_instantiate(self, widget_class, *args, **kwargs):
        """Safely instantiates a widget. If instantiation fails, returns a fallback Static widget."""
        try:
            widget = widget_class(*args, **kwargs)
            return safe_widget(widget, self)
        except Exception as e:
            logger.error(f"SafeMode: Failed to instantiate {widget_class.__name__}: {e}")
            self.activate_startup_safe_mode(f"{widget_class.__name__} instantiation crash: {e}")
            fallback = Static(f"[bold red]SAFE MODE: {widget_class.__name__} Failed[/]")
            fallback.id = f"{widget_class.__name__.lower()}-fallback"
            return fallback

    def compose(self) -> ComposeResult:
        """Compose layout grid."""
        yield self.safe_instantiate(HeaderWidget)
        
        with Container(id="grid-middle"):
            with Container(id="left-col"):
                yield self.safe_instantiate(SystemPanel)
                yield self.safe_instantiate(ThroughputPanel)
                yield self.safe_instantiate(SysMetricsPanel)
            
            with Container(id="middle-col"):
                yield self.safe_instantiate(RiskRadar)
                yield self.safe_instantiate(RiskTrendPanel)
                yield self.safe_instantiate(RunbookPanel)
            
            with Container(id="right-col"):
                yield self.safe_instantiate(OllamaPanel)
                yield self.safe_instantiate(AlertPanel)
                yield self.safe_instantiate(AutopilotPanel)
                yield self.safe_instantiate(AiServerStatusPanel)
                yield self.safe_instantiate(WatchdogPanel)
                
        yield self.safe_instantiate(NewsFeed)
        yield self.safe_instantiate(LogPanel)
        yield self.safe_instantiate(TickerWidget)
        yield Footer()

    def on_mount(self):
        """Register loops and load start theme."""
        # 1. Apply default theme
        self.add_class(THEMES[self.theme_index])
        if self.wallboard_mode:
            self.add_class("wallboard-mode")
            self.set_interval(6.0, self.auto_rotate_focus)
            self.query_one(Footer).display = False

        # 2. Run Startup Health Validation
        self.run_startup_validation()

        # 3. Register background timers
        self.set_interval(REFRESH_RATES["status"], self.run_status_and_logs_update)
        self.set_interval(REFRESH_RATES["db"], self.run_db_metrics_update)
        self.set_interval(REFRESH_RATES["ticker_fetch"], self.run_btc_ticker_update)
        self.set_interval(60.0, self.run_autopilot_cycle)
        self.set_interval(10.0, self.run_ai_server_update)
        self.set_interval(1.0, self.run_flash_timer)
        self.set_interval(0.25, self.run_logo_flash_timer)

        # 4. Trigger initial fetches
        self.run_status_and_logs_update()
        self.run_db_metrics_update()
        self.run_btc_ticker_update()
        self.run_autopilot_cycle()
        self.run_ai_server_update()

    def activate_startup_safe_mode(self, reason: str):
        """Activates Safe Mode fallback on the dashboard."""
        if self.startup_safe_mode_active:
            return
        self.startup_safe_mode_active = True
        logger.warning(f"Safe Mode activated due to: {reason}")
        
        # 1. Update overall status on self and widgets
        try:
            self.query_one(HeaderWidget).status_str = "SAFE MODE ACTIVE"
        except Exception:
            pass

        # 2. Hide/disable non-minimal widgets
        non_minimal_classes = [
            RiskRadar,
            RiskTrendPanel,
            RunbookPanel,
            AlertPanel,
            AutopilotPanel,
            NewsFeed
        ]
        for w_class in non_minimal_classes:
            try:
                self.query_one(w_class).display = False
            except Exception:
                pass
        
        try:
            self.query_one(NewsFeed).auto_scroll_active = False
        except Exception:
            pass
        
        # 3. Disable autopilot cycle and recovery checks
        try:
            self.autopilot_service.locked = True
        except Exception:
            pass

        # Notify user
        self.notify("SAFE MODE ACTIVE", severity="error")

    def check_safe_mode_action(self) -> bool:
        """Returns True if the action should be blocked because of active Safe Mode."""
        if self.startup_safe_mode_active:
            self.notify("ACTION BLOCKED: SAFE MODE ACTIVE", severity="warning")
            return True
        return False

    def run_startup_validation(self):
        """Validate PostgreSQL, services, and feed health on startup."""
        self.startup_errors = []
        
        try:
            if not self.db_service.check_db_health():
                self.startup_errors.append("PostgreSQL Connection Failed")
        except Exception as e:
            self.startup_errors.append(f"PostgreSQL Check Failed: {e}")
            
        try:
            if self.ollama_service.check_ollama_status() != "ONLINE":
                if OLLAMA_REMOTE:
                    self.startup_errors.append("Remote Ollama Endpoint Unreachable")
                else:
                    self.startup_errors.append("Ollama Endpoint Unreachable")
        except Exception as e:
            self.startup_errors.append(f"Ollama Check Failed: {e}")
            
        try:
            if not self.feed_service.check_worker_service_status():
                self.startup_errors.append("Worker service Inactive")
        except Exception as e:
            self.startup_errors.append(f"Worker Check Failed: {e}")
            
        try:
            if not self.feed_service.check_ingest_service_status():
                self.startup_errors.append("Ingest Timer Inactive")
        except Exception as e:
            self.startup_errors.append(f"Ingest Timer Check Failed: {e}")

        try:
            if not self.db_service.get_rss_feed_health():
                self.startup_errors.append("RSS Feed Polling Failed")
        except Exception as e:
            self.startup_errors.append(f"RSS Feed Check Failed: {e}")

        # Push to alert panel
        try:
            alerts = self.query_one(AlertPanel)
            alerts.startup_failures = self.startup_errors
        except Exception:
            pass

    # --- Background Workers & Data Fetching Jobs ---

    def run_status_and_logs_update(self):
        self.run_worker(self._fetch_status_and_logs_job, thread=True)

    def _fetch_status_and_logs_job(self):
        try:
            worker_active = self.feed_service.check_worker_service_status()
            ingest_active = self.feed_service.check_ingest_service_status()
            db_active = self.db_service.check_db_health()
            ollama_stats = self.ollama_service.get_ollama_stats()
            logs = self.log_service.fetch_worker_logs(lines=100)
            
            # Fetch host RAM usage to feed Smart Recommendations
            ram = psutil.virtual_memory().percent
            
            # Layered hardware health check
            hw_status = self._check_hardware_health()
            
            self.app.call_from_thread(
                self._update_status_and_logs_ui,
                worker_active, ingest_active, db_active, ollama_stats, logs, ram, hw_status
            )
        except Exception:
            pass

    def _update_status_and_logs_ui(self, worker, ingest, db, ollama_stats, logs, ram, hw_status):
        ollama_online_now = ollama_stats["status"] == "ONLINE"
        disk_percent = hw_status["disk_percent"]
        fs_readonly = hw_status["fs_readonly"]
        ipmi_fault = hw_status["ipmi_fault"]
        raid_failure = hw_status["raid_failure"]

        # Check and log transition events to operations_log
        if self.status_fetched_once:
            if self.db_online != db:
                severity = "CRITICAL" if not db else "INFO"
                event = "PostgreSQL Connection Offline" if not db else "PostgreSQL Connection Restored"
                action_taken = "Checked PostgreSQL port/socket connectivity"
                result = "ALERT" if not db else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)

            if self.worker_online != worker:
                severity = "CRITICAL" if not worker else "INFO"
                event = "Bitcoin Worker service stopped" if not worker else "Bitcoin Worker service started"
                action_taken = "Checked systemd service status"
                result = "ALERT" if not worker else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)

            if self.ingest_online != ingest:
                severity = "CRITICAL" if not ingest else "INFO"
                event = "RSS Ingest Timer service inactive" if not ingest else "RSS Ingest Timer service active"
                action_taken = "Checked systemd timer status"
                result = "ALERT" if not ingest else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)

            if self.ollama_online != ollama_online_now:
                severity = "CRITICAL" if not ollama_online_now else "INFO"
                event = "Ollama endpoint offline" if not ollama_online_now else "Ollama endpoint restored"
                action_taken = "Checked Ollama tag endpoint status"
                result = "ALERT" if not ollama_online_now else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)

            disk_critical_prev = self.disk_percent > 95.0
            disk_critical_now = disk_percent > 95.0
            if disk_critical_prev != disk_critical_now:
                severity = "CRITICAL" if disk_critical_now else "INFO"
                event = f"Disk usage exceeded 95% ({disk_percent:.1f}%)" if disk_critical_now else "Disk usage returned below 95%"
                action_taken = "Checked local disk space usage"
                result = "ALERT" if disk_critical_now else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)

            if self.fs_readonly != fs_readonly:
                severity = "CRITICAL" if fs_readonly else "INFO"
                event = "Filesystem mounted read-only" if fs_readonly else "Filesystem remounted read-write"
                action_taken = "Checked filesystem mount options"
                result = "ALERT" if fs_readonly else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)

            if self.ipmi_fault != ipmi_fault:
                severity = "CRITICAL" if ipmi_fault else "INFO"
                event = "Critical hardware fault detected via IPMI" if ipmi_fault else "IPMI hardware fault cleared"
                action_taken = "Checked IPMI chassis and sensor logs"
                result = "ALERT" if ipmi_fault else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)

            if self.raid_failure != raid_failure:
                severity = "CRITICAL" if raid_failure else "INFO"
                event = "RAID Controller/Battery Failure" if raid_failure else "RAID recovered"
                action_taken = "Checked storage controller and battery health status"
                result = "ALERT" if raid_failure else "RECOVERY"
                self.db_service.log_operations_event(severity, event, action_taken, result)
        else:
            self.status_fetched_once = True

        self.worker_online = worker
        self.ingest_online = ingest
        self.db_online = db
        self.ollama_online = ollama_online_now
        self.disk_percent = disk_percent
        self.fs_readonly = fs_readonly
        self.ipmi_fault = ipmi_fault
        self.raid_failure = raid_failure

        # Track if Ollama offline > 5 minutes (300 seconds)
        if not self.ollama_online:
            if self.ollama_first_offline is None:
                self.ollama_first_offline = time.time()
            time_offline = time.time() - self.ollama_first_offline
            self.ollama_is_critical = (time_offline > 300)
        else:
            self.ollama_first_offline = None
            self.ollama_is_critical = False

        # Update Header
        try:
            header = self.query_one(HeaderWidget)
            header.worker_status = worker
            header.ingest_status = ingest
            header.db_status = db
            header.ollama_status = self.ollama_online
            if self.startup_safe_mode_active:
                header.status_str = "SAFE MODE ACTIVE"
        except Exception:
            pass

        # Update Ollama panel
        try:
            ollama_panel = self.query_one(OllamaPanel)
            ollama_panel.status_str = ollama_stats["status"]
            ollama_panel.model_name = ollama_stats["model"]
            ollama_panel.server_host = ollama_stats["server"]
            ollama_panel.latency_sec = float(ollama_stats["latency"].replace("s", "")) if ollama_stats["latency"] != "N/A" else 0.0
            ollama_panel.failures_count = ollama_stats["failures"]
            ollama_panel.requests_count = ollama_stats["requests"]
            self.ollama_model = ollama_stats["model"]
        except Exception:
            pass

        # Update Log panel
        try:
            log_panel = self.query_one(LogPanel)
            log_panel.update_logs(logs)
        except Exception:
            pass

        # Update Alerts & Recommendations panel
        try:
            alerts = self.query_one(AlertPanel)
            alerts.ollama_online = self.ollama_online
            alerts.db_online = db
            alerts.worker_active = worker
            alerts.ingest_active = ingest
            alerts.ollama_failures = ollama_stats["failures"]
            try:
                lat = self.query_one(OllamaPanel).latency_sec
            except Exception:
                lat = float(ollama_stats["latency"].replace("s", "")) if ollama_stats["latency"] != "N/A" else 0.0
            alerts.avg_time = lat
            alerts.host_ram_percent = ram
            alerts.env_ollama_model = OLLAMA_MODEL
            alerts.active_ollama_model = ollama_stats["model"]
        except Exception:
            pass

    def run_db_metrics_update(self):
        self.run_worker(self._fetch_db_metrics_job, thread=True)

    def _fetch_db_metrics_job(self):
        try:
            queue_counts = self.db_service.get_queue_counts()
            throughput = self.db_service.get_queue_throughput()
            processed_today = self.db_service.get_processed_today()
            risk_history = self.db_service.get_hourly_risk_history()
            latest_articles = self.db_service.get_latest_articles(limit=50)
            latest_analysis = self.db_service.get_latest_analysis()
            oldest_age = self.db_service.get_oldest_processing_age()
            
            self.app.call_from_thread(
                self._update_db_metrics_ui,
                queue_counts, throughput, processed_today, risk_history, latest_articles, latest_analysis, oldest_age
            )
        except Exception:
            pass

    def _update_db_metrics_ui(self, queue_counts, throughput, processed_today, risk_history, latest_articles, latest_analysis, oldest_age):
        self.oldest_processing_age = oldest_age
        # Update System counts
        try:
            system_panel = self.query_one(SystemPanel)
            system_panel.pending_count = queue_counts["pending"]
            system_panel.processing_count = queue_counts["processing"]
            system_panel.completed_count = queue_counts["completed"]
            system_panel.failed_count = queue_counts["failed"]
        except Exception:
            pass

        # Update Throughput
        try:
            tp_panel = self.query_one(ThroughputPanel)
            tp_panel.processed_last_hour = throughput["processed_last_hour"]
            tp_panel.processed_today = processed_today
            tp_panel.avg_time = throughput["avg_time"]
            tp_panel.remaining = throughput["remaining"]
            tp_panel.eta_str = throughput["eta_str"]
            
            total = queue_counts["completed"] + queue_counts["failed"]
            efficiency = (queue_counts["completed"] / max(total, 1)) * 100.0
            tp_panel.worker_efficiency = efficiency
        except Exception:
            efficiency = 100.0

        # Update Alerts
        try:
            alerts = self.query_one(AlertPanel)
            alerts.max_retry = throughput["max_retry"]
            alerts.failed_queue_count = queue_counts["failed"]
            alerts.worker_efficiency = efficiency
            alerts.queue_processing_count = queue_counts["processing"]
        except Exception:
            pass

        # Update header Giant NOC Status Banner variables
        try:
            header = self.query_one(HeaderWidget)
            header.worker_efficiency = efficiency
            header.avg_time = throughput["avg_time"]
        except Exception:
            pass

        # Update Risk Trend graph
        try:
            trend_panel = self.query_one(RiskTrendPanel)
            trend_panel.risk_history = risk_history
        except Exception:
            pass

        # Update news feed table
        try:
            news = self.query_one(NewsFeed)
            news.update_articles(latest_articles)
        except Exception:
            pass

        # Update Risk Radar
        try:
            risk_radar = self.query_one(RiskRadar)
            if latest_analysis:
                risk_radar.risk_score = latest_analysis.get("importance_score", 0)
                risk_radar.sentiment_str = latest_analysis.get("sentiment", "Neutral")
                risk_radar.sentiment_score = latest_analysis.get("sentiment_score", 0.0)
                risk_radar.importance_score = latest_analysis.get("importance_score", 0)
                risk_radar.confidence_str = latest_analysis.get("confidence", "medium")
                
                try:
                    self.query_one(AlertPanel).latest_risk_score = latest_analysis.get("importance_score", 0)
                except Exception:
                    pass
                
                # Feed header summary banner
                try:
                    h = self.query_one(HeaderWidget)
                    h.risk_score = latest_analysis.get("importance_score", 0)
                    h.queue_remaining = throughput["remaining"]
                    h.eta_str = throughput["eta_str"]
                    h.top_event_str = latest_analysis.get("title", "No headlines yet.")
                except Exception:
                    pass

                try:
                    t = self.query_one(TickerWidget)
                    t.latest_title = latest_analysis.get("title", "No headlines yet.")
                except Exception:
                    pass
        except Exception:
            pass

        # Update ticker stats
        try:
            ticker = self.query_one(TickerWidget)
            ticker.queue_remaining = throughput["remaining"]
            ticker.eta_str = throughput["eta_str"]
            ticker.ollama_status = "ONLINE" if self.ollama_online else "OFFLINE"
        except Exception:
            pass

    def run_btc_ticker_update(self):
        self.run_worker(self._fetch_btc_ticker_job, thread=True)

    def _fetch_btc_ticker_job(self):
        try:
            btc_data = self.ticker_service.fetch_btc_price()
            self.app.call_from_thread(self._update_btc_ticker_ui, btc_data)
        except Exception:
            pass

    def _update_btc_ticker_ui(self, btc_data):
        try:
            header = self.query_one(HeaderWidget)
            header.btc_price_str = btc_data["price_str"]
            header.btc_change_str = btc_data["change_str"]
            header.btc_positive = btc_data["is_positive"]
        except Exception:
            pass

        try:
            ticker = self.query_one(TickerWidget)
            ticker.btc_price_str = btc_data["price_str"]
            ticker.btc_change_str = btc_data["change_str"]
            ticker.btc_positive = btc_data["is_positive"]
        except Exception:
            pass

    # --- Actions / Keyboard Bindings handlers ---

    def action_focus_logs(self):
        self.query_one(LogPanel).focus()

    def action_focus_news(self):
        self.query_one(NewsFeed).focus()

    def action_focus_risk(self):
        self.query_one(RiskRadar).focus()

    def action_next_theme(self):
        """F2: Cycle theme."""
        if self.check_safe_mode_action():
            return
        self.theme_index = (self.theme_index + 1) % len(THEMES)
        new_theme = THEMES[self.theme_index]
        
        # Reset classes
        for t in THEMES:
            self.remove_class(t)
        self.add_class(new_theme)
        if self.wallboard_mode:
            self.add_class("wallboard-mode")
        
        # Push reactive theme update to all widgets
        try:
            self.query_one(HeaderWidget).current_theme = new_theme
            self.query_one(SystemPanel).current_theme = new_theme
            self.query_one(ThroughputPanel).current_theme = new_theme
            self.query_one(SysMetricsPanel).current_theme = new_theme
            self.query_one(OllamaPanel).current_theme = new_theme
            self.query_one(AlertPanel).current_theme = new_theme
            self.query_one(RiskRadar).current_theme = new_theme
            self.query_one(RiskTrendPanel).current_theme = new_theme
            self.query_one(RunbookPanel).current_theme = new_theme
            self.query_one(NewsFeed).current_theme = new_theme
            self.query_one(LogPanel).current_theme = new_theme
            self.query_one(TickerWidget).current_theme = new_theme
            self.query_one(AutopilotPanel).current_theme = new_theme
            self.query_one(AiServerStatusPanel).current_theme = new_theme
            self.query_one(WatchdogPanel).current_theme = new_theme
        except Exception:
            pass
        
        self.notify(f"Theme switched to: {THEME_NAMES[new_theme]}")

    def action_toggle_compact(self):
        try:
            header = self.query_one(HeaderWidget)
            header.compact_mode = not header.compact_mode
        except Exception:
            pass

    def action_toggle_fullscreen_logs(self):
        self.logs_fullscreen = not self.logs_fullscreen
        try:
            grid_mid = self.query_one("#grid-middle")
            grid_mid.display = not self.logs_fullscreen
        except Exception:
            pass
        try:
            news = self.query_one(NewsFeed)
            news.display = not self.logs_fullscreen
        except Exception:
            pass
        try:
            header = self.query_one(HeaderWidget)
            if self.criticalAlarmActive():
                header.display = True
            else:
                header.display = not self.logs_fullscreen
        except Exception:
            pass

    def action_refresh_data(self):
        """F5: Manual refresh."""
        self.run_status_and_logs_update()
        self.run_db_metrics_update()
        self.run_btc_ticker_update()
        self.notify("Dashboard metrics manual refresh triggered.")

    # --- Operator recovery actions ---

    def action_restart_worker(self):
        """F6: Restart Worker service."""
        if self.check_safe_mode_action():
            return
        def check_result(confirm: bool) -> None:
            if confirm:
                res = self.recovery_service.restart_worker()
                if res:
                    self.notify("Worker service restart command sent.")
                else:
                    self.notify("Worker service restart failed.", severity="error")

        self.push_screen(
            ConfirmationDialog("Are you sure you want to RESTART the Worker service?", theme_name=THEMES[self.theme_index]),
            check_result
        )

    def action_restart_ingest(self):
        """F7: Restart RSS Ingest timer."""
        if self.check_safe_mode_action():
            return
        def check_result(confirm: bool) -> None:
            if confirm:
                res = self.recovery_service.restart_ingest()
                if res:
                    self.notify("RSS Ingest Timer restart command sent.")
                else:
                    self.notify("RSS Ingest Timer restart failed.", severity="error")

        self.push_screen(
            ConfirmationDialog("Are you sure you want to RESTART the RSS Ingest timer?", theme_name=THEMES[self.theme_index]),
            check_result
        )

    def action_requeue_failed(self):
        """F8: Requeue Failed Queue Jobs."""
        if self.check_safe_mode_action():
            return
        def check_result(confirm: bool) -> None:
            if confirm:
                res = self.recovery_service.requeue_failed()
                if res:
                    self.notify("Successfully requeued failed and dead letter items.")
                    self.run_db_metrics_update()
                else:
                    self.notify("Failed to update PostgreSQL queue.", severity="error")

        self.push_screen(
            ConfirmationDialog("Are you sure you want to REQUEUE all failed items?", theme_name=THEMES[self.theme_index]),
            check_result
        )

    def action_clear_stuck(self):
        """F9: Clear Stuck Processing (>15m)."""
        if self.check_safe_mode_action():
            return
        def check_result(confirm: bool) -> None:
            if confirm:
                res = self.recovery_service.clear_stuck_processing()
                if res:
                    self.notify("Successfully cleared stuck processing items.")
                    self.run_db_metrics_update()
                else:
                    self.notify("Failed to clear stuck processing items.", severity="error")

        self.push_screen(
            ConfirmationDialog("Are you sure you want to CLEAR stuck processing items?", theme_name=THEMES[self.theme_index]),
            check_result
        )

    def action_restart_ollama(self):
        """F10: Restart Ollama service."""
        if self.check_safe_mode_action():
            return
        def check_result(confirm: bool) -> None:
            if confirm:
                # Runs restart in background since ping tags checking takes a few seconds
                self.run_worker(self._restart_ollama_job, thread=True)

        self.push_screen(
            ConfirmationDialog("Are you sure you want to RESTART the Ollama service?", theme_name=THEMES[self.theme_index]),
            check_result
        )

    def _restart_ollama_job(self):
        self.notify("Restarting Ollama service. Verifying status...")
        res = self.recovery_service.restart_ollama()
        if res:
            self.notify("Ollama service restarted successfully. Active tags confirmed.")
        else:
            self.notify("Ollama restart failed or service timed out.", severity="error")

    def action_warm_model(self):
        """F11: Warm Model Cache."""
        if self.check_safe_mode_action():
            return
        self.notify(f"Pre-loading cache for model: {self.ollama_model}...")
        self.run_worker(self._warm_model_job, thread=True)

    def _warm_model_job(self):
        res = self.recovery_service.warm_model(self.ollama_model)
        if res:
            self.notify(f"Cache preloaded successfully for model '{self.ollama_model}'.")
        else:
            self.notify(f"Failed to preload model cache for '{self.ollama_model}'.", severity="warning")

    def action_health_recovery(self):
        """F12: Full Health Recovery."""
        if self.check_safe_mode_action():
            return
        def check_result(confirm: bool) -> None:
            if confirm:
                self.notify("Executing Full operational Health Recovery Runbook...")
                self.run_worker(self._health_recovery_job, thread=True)

        self.push_screen(
            ConfirmationDialog("Execute FULL operational runbook recovery audit?", theme_name=THEMES[self.theme_index]),
            check_result
        )

    def _health_recovery_job(self):
        try:
            self.autopilot_service.unlock_autopilot()
            results = self.recovery_service.execute_health_recovery(self.ollama_model)
            
            # Build checklist notification
            checklist_lines = []
            for name, ok in results:
                status_icon = "✓" if ok else "✗"
                checklist_lines.append(f"[{status_icon}] {name}")
            
            notification_msg = "Full Recovery Audit completed & Autopilot Unlocked:\n" + "\n".join(checklist_lines)
            self.notify(notification_msg, severity="info" if all(ok for _, ok in results) else "warning")
            
            # Re-fetch UI metrics
            self.run_status_and_logs_update()
            self.run_db_metrics_update()
            self.run_btc_ticker_update()
            self.run_autopilot_cycle()
        except Exception as e:
            self.notify(f"Health recovery runbook execution error: {e}", severity="error")

    def action_quit_app(self):
        self.exit()

    def auto_rotate_focus(self):
        widgets = [
            self.query_one(RiskRadar),
            self.query_one(NewsFeed),
            self.query_one(LogPanel)
        ]
        current_focus = self.focused
        next_focus_index = 0
        for i, w in enumerate(widgets):
            if w == current_focus:
                next_focus_index = (i + 1) % len(widgets)
                break
        widgets[next_focus_index].focus()

    # --- Autopilot Service Background Workers ---

    def run_autopilot_cycle(self):
        if self.startup_safe_mode_active:
            return
        self.run_worker(self._autopilot_cycle_job, thread=True)

    def _autopilot_cycle_job(self):
        try:
            # 1. Gather all metrics needed for telemetry
            db_ok = self.db_service.check_db_health()
            worker_ok = self.feed_service.check_worker_service_status()
            ingest_ok = self.feed_service.check_ingest_service_status()
            ollama_stats = self.ollama_service.get_ollama_stats()
            
            queue_counts = self.db_service.get_queue_counts()
            oldest_age = self.db_service.get_oldest_processing_age()
            throughput = self.db_service.get_queue_throughput()
            
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            
            telemetry = {
                "db_online": db_ok,
                "worker_online": worker_ok,
                "ingest_online": ingest_ok,
                "ollama_online": ollama_stats["status"] == "ONLINE",
                "failed_queue": queue_counts["failed"],
                "processing_queue": queue_counts["processing"],
                "oldest_processing_age_mins": oldest_age,
                "ollama_failures": ollama_stats["failures"],
                "cpu": cpu,
                "ram": ram,
                "queue_remaining": throughput["remaining"],
                "avg_latency": throughput["avg_time"],
                "ai_server_status": self.ai_server_status,
                "disk_percent": self.disk_percent,
                "fs_readonly": self.fs_readonly,
                "ipmi_fault": self.ipmi_fault,
                "raid_failure": self.raid_failure
            }
            
            # 2. Run autopilot cycle on the AutopilotService
            health_state = self.autopilot_service.execute_autopilot_cycle(telemetry)
            
            # 3. Retrieve the last 4 operations actions
            last_actions = self.db_service.get_last_operations_actions(limit=4)
            
            # 4. Trigger UI update
            self.app.call_from_thread(self._update_autopilot_ui, health_state, last_actions)
            
            # 5. Check if today is Sunday to run/generate weekly report
            now = datetime.now()
            if now.weekday() == 6:  # Sunday
                date_str = now.strftime("%Y-%m-%d")
                if self.last_audit_date != date_str:
                    self.generate_weekly_report(date_str)
        except Exception as e:
            logger.error(f"Error in autopilot cycle job: {e}")

    def _update_autopilot_ui(self, health_state, last_actions):
        try:
            # Update Autopilot panel
            ap_panel = self.query_one(AutopilotPanel)
            ap_panel.status_str = health_state.overall_status
            ap_panel.health_score = health_state.score
            ap_panel.uptime_days = self.autopilot_service.get_uptime_days()
            ap_panel.actions_today = self.autopilot_service.total_recoveries_today
            ap_panel.last_actions_list = last_actions
        except Exception:
            pass
            
        # Update Alert panel values
        try:
            alerts = self.query_one(AlertPanel)
            alerts.autopilot_locked = self.autopilot_service.locked
            alerts.predictive_alerts = self.autopilot_service.predictive_alerts
        except Exception:
            pass
            
        # Update Header status_str
        try:
            header = self.query_one(HeaderWidget)
            if self.startup_safe_mode_active:
                header.status_str = "SAFE MODE ACTIVE"
            else:
                header.status_str = health_state.overall_status
        except Exception as e:
            logger.error(f"Error updating autopilot UI: {e}")

    # --- AI Server Monitoring Background Jobs & UI updates ---

    def run_ai_server_update(self):
        if self.startup_safe_mode_active:
            return
        self.run_worker(self._fetch_ai_server_job, thread=True)

    def _fetch_ai_server_job(self):
        try:
            prev_status = self.ai_server_status
            res = self.ai_server_service.perform_full_check()
            new_status = res["status"]
            
            # Log transition if status changed
            if prev_status != new_status:
                severity = "INFO"
                event = f"AI Server (R510) Status Transition: {prev_status} -> {new_status}"
                action_taken = "Checked Ping, SSH, and Ollama status"
                result = "OK"
                
                if new_status == "RED":
                    severity = "CRITICAL"
                    action_taken = "Ping/SSH check failed, flagged status as OFFLINE"
                    result = "ALERT"
                elif new_status == "YELLOW":
                    severity = "WARNING"
                    action_taken = "Ollama tag endpoint check failed, flagged status as DEGRADED"
                    result = "WARNING"
                else: # GREEN
                    severity = "INFO"
                    action_taken = "All checks passed (Ping, SSH, Ollama), flagged status as ONLINE"
                    result = "RECOVERY"
                
                self.db_service.log_operations_event(
                    severity=severity,
                    event=event,
                    action_taken=action_taken,
                    result=result,
                    host="r510"
                )
                
            self.app.call_from_thread(self._update_ai_server_ui, res)
        except Exception as e:
            logger.error(f"Error in AI Server update job: {e}")

    def _update_ai_server_ui(self, res):
        self.ai_server_status = res["status"]
        if self.ai_server_status == "RED":
            if self.ai_server_first_offline is None:
                self.ai_server_first_offline = time.time()
        else:
            self.ai_server_first_offline = None

        # Check if offline > 5 minutes (300 seconds)
        if self.ai_server_status == "RED" and self.ai_server_first_offline is not None:
            time_offline = time.time() - self.ai_server_first_offline
            self.ai_server_is_critical = (time_offline > 300)
        else:
            self.ai_server_is_critical = False

        # AI SERVER CRITICAL Check
        ping_ok = res.get("ping_ok", True)
        ssh_ok = res.get("ssh_ok", True)
        ollama_port_ok = res.get("ollama_port_ok", True)
        ollama_ok = res.get("ollama_ok", True)
        
        # 1. Ping succeeds, SSH succeeds, TCP 11434 fails
        cond1 = ping_ok and ssh_ok and not ollama_port_ok
        
        # 2. /api/tags fails for >60 seconds
        if not ollama_ok:
            if self.ai_server_tags_first_fail is None:
                self.ai_server_tags_first_fail = time.time()
            cond2 = (time.time() - self.ai_server_tags_first_fail > 60)
        else:
            self.ai_server_tags_first_fail = None
            cond2 = False
            
        # 3. Queue item remains processing >15 minutes
        cond3 = self.oldest_processing_age > 15.0
        
        self.ai_server_critical_active = cond1 or cond2 or cond3

        # Update Header Widget reactive variables
        try:
            header = self.query_one(HeaderWidget)
            header.ai_server_status = self.ai_server_status
            header.ai_server_is_critical = self.ai_server_is_critical
        except Exception:
            pass

        # Update Alert Panel reactive variables
        try:
            alerts = self.query_one(AlertPanel)
            alerts.ai_server_status = self.ai_server_status
            alerts.ai_server_is_critical = self.ai_server_is_critical
        except Exception:
            pass

        # Update AiServerStatusPanel reactive variables
        try:
            ai_panel = self.query_one(AiServerStatusPanel)
            ai_panel.ping_latency = res["ping_latency"]
            ai_panel.ssh_status = "ONLINE" if res["ssh_ok"] else "OFFLINE"
            ai_panel.ollama_status = "ONLINE" if res["ollama_ok"] else "OFFLINE"
            if res["status"] in ("GREEN", "YELLOW"):
                from datetime import datetime
                ai_panel.last_success = datetime.fromtimestamp(res["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    def run_flash_toggle_timer(self):
        # Kept for backward compatibility if called elsewhere
        self.run_flash_timer()

    def run_flash_timer(self):
        self.ai_server_flash_toggle = not self.ai_server_flash_toggle
        try:
            header = self.query_one(HeaderWidget)
            header.ai_server_flash_toggle = self.ai_server_flash_toggle
        except Exception:
            pass
        try:
            alerts = self.query_one(AlertPanel)
            alerts.ai_server_flash_toggle = self.ai_server_flash_toggle
        except Exception:
            pass

    def is_in_startup_grace_period(self) -> bool:
        """Returns True if the application or host has booted in the last 5 minutes."""
        app_uptime = time.time() - self.app_start_time
        try:
            system_uptime = time.time() - psutil.boot_time()
        except Exception:
            system_uptime = 9999.0
        return app_uptime < 300.0 or system_uptime < 300.0

    def hasCriticalFault(self) -> bool:
        """Returns True if any critical fault (recoverable or non-recoverable) exists."""
        return (
            self.hasNonRecoverableFault() or
            not self.ollama_online or
            self.ai_server_status == "RED" or
            not self.ingest_online or
            self.autopilot_service.locked
        )

    def hasNonRecoverableFault(self) -> bool:
        """Returns True if any non-recoverable system fault is present."""
        # 1. PostgreSQL offline
        if not self.db_online:
            return True
        # 2. Worker offline
        if not self.worker_online:
            return True
        # 3. Disk usage > 95%
        if self.disk_percent > 95.0:
            return True
        # 4. Filesystem mounted read-only
        if self.fs_readonly:
            return True
        # 5. IPMI fault
        if self.ipmi_fault:
            return True
        # 6. RAID controller/battery failure
        if self.raid_failure:
            return True
        # 7. Ollama unavailable for > 5 mins
        if self.ollama_is_critical:
            return True
        # 8. AI server unreachable for > 5 mins or critical active
        if self.ai_server_is_critical or self.ai_server_critical_active:
            return True
        # 9. Autopilot locked with any critical issue
        if self.autopilot_service.locked:
            if not self.ollama_online or not self.ingest_online:
                return True
        return False

    @property
    def criticalAlarmActive(self) -> CallableBool:
        """Returns CallableBool reflecting active non-recoverable alarm, respecting startup grace period."""
        if self.is_in_startup_grace_period():
            return CallableBool(False)
        return CallableBool(self.hasNonRecoverableFault())

    def _check_hardware_health(self) -> dict:
        """
        Layered hardware health checking:
        1. Disk usage via psutil
        2. Read-only filesystem check
        3. IPMI System Fault check via ipmitool
        4. RAID check via MegaCli / storcli / perccli
        Gracefully degrades if commands are missing.
        """
        disk_percent = float(os.getenv("MOCK_DISK_PERCENT", "0.0"))
        if disk_percent == 0.0:
            try:
                disk_percent = psutil.disk_usage('/').percent
            except Exception:
                disk_percent = 0.0
                
        fs_readonly = os.getenv("MOCK_READ_ONLY_FS", "false").lower() == "true"
        if not fs_readonly:
            try:
                for part in psutil.disk_partitions(all=True):
                    if part.mountpoint == '/':
                        if 'ro' in part.opts.split(','):
                            fs_readonly = True
                            break
            except Exception:
                pass
                
        ipmi_fault = os.getenv("MOCK_IPMI_FAULT", "false").lower() == "true"
        if not ipmi_fault and sys.platform.startswith("linux"):
            try:
                res = subprocess.run(["sudo", "ipmitool", "sel", "elist"], capture_output=True, text=True, timeout=2.0)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        line_lower = line.lower()
                        if "critical" in line_lower or "non-recoverable" in line_lower or "failure" in line_lower:
                            ipmi_fault = True
                            break
                if not ipmi_fault:
                    res = subprocess.run(["sudo", "ipmitool", "sensor"], capture_output=True, text=True, timeout=2.0)
                    if res.returncode == 0:
                        for line in res.stdout.splitlines():
                            parts = line.split('|')
                            if len(parts) >= 4:
                                status_val = parts[3].strip().lower()
                                if status_val in ("cr", "nr", "critical", "non-recoverable", "fail"):
                                    ipmi_fault = True
                                    break
            except Exception:
                pass
                
        raid_failure = os.getenv("MOCK_RAID_FAILURE", "false").lower() == "true"
        if not raid_failure and sys.platform.startswith("linux"):
            for cmd in ["storcli", "perccli", "/opt/MegaRAID/storcli/storcli64", "/opt/MegaRAID/perccli/perccli64"]:
                try:
                    res = subprocess.run([cmd, "/c0", "show"], capture_output=True, text=True, timeout=3.0)
                    if res.returncode == 0:
                        stdout_lower = res.stdout.lower()
                        if "degraded" in stdout_lower or "failed" in stdout_lower or "offline" in stdout_lower:
                            raid_failure = True
                            break
                except FileNotFoundError:
                    continue
                except Exception:
                    pass
            if not raid_failure:
                for cmd in ["MegaCli", "MegaCli64", "/opt/MegaRAID/MegaCli/MegaCli64"]:
                    try:
                        res = subprocess.run([cmd, "-AdpAllInfo", "-aAll"], capture_output=True, text=True, timeout=3.0)
                        if res.returncode == 0:
                            stdout_lower = res.stdout.lower()
                            if "degraded" in stdout_lower or "failed" in stdout_lower or "critical" in stdout_lower:
                                raid_failure = True
                                break
                    except FileNotFoundError:
                        continue
                    except Exception:
                        pass
                        
        return {
            "disk_percent": disk_percent,
            "fs_readonly": fs_readonly,
            "ipmi_fault": ipmi_fault,
            "raid_failure": raid_failure
        }

    def run_logo_flash_timer(self):
        """Runs every 250ms to update logo flashing status and System Watchdog values."""
        t310 = "RED" if (self.disk_percent > 95.0 or self.fs_readonly or self.ipmi_fault or self.raid_failure) else "GREEN"
        
        if self.ai_server_status == "RED":
            r510 = "RED" if self.ai_server_is_critical else "YELLOW"
        else:
            r510 = "RED" if self.ai_server_critical_active else "GREEN"
            
        if not self.ollama_online:
            if self.ollama_is_critical:
                ollama_api = "RED"
            elif self.ai_server_tags_first_fail is not None and (time.time() - self.ai_server_tags_first_fail > 60.0):
                ollama_api = "RED"
            else:
                ollama_api = "YELLOW"
        else:
            ollama_api = "GREEN"
            
        worker = "GREEN" if self.worker_online else "RED"
        postgres = "GREEN" if self.db_online else "RED"
        queue = "RED" if self.oldest_processing_age > 15.0 else "GREEN"

        try:
            w = self.query_one(WatchdogPanel)
            w.t310_status = t310
            w.r510_status = r510
            w.ollama_api_status = ollama_api
            w.worker_status = worker
            w.postgres_status = postgres
            w.queue_status = queue
        except Exception:
            pass

        alarm_active = self.criticalAlarmActive()
        if alarm_active:
            self.logo_flash_phase = (self.logo_flash_phase + 1) % 2
            try:
                h = self.query_one(HeaderWidget)
                h.logo_flash_phase = self.logo_flash_phase
                h.critical_alarm_active = True
                h.refresh()
            except Exception:
                pass
            # Force header display if logs fullscreen is active
            if self.logs_fullscreen:
                try:
                    self.query_one(HeaderWidget).display = True
                except Exception:
                    pass
        else:
            if self.logo_flash_phase != 0 or getattr(self, "_last_alarm_state", False):
                self.logo_flash_phase = 0
                try:
                    h = self.query_one(HeaderWidget)
                    h.logo_flash_phase = 0
                    h.critical_alarm_active = False
                    h.refresh()
                except Exception:
                    pass
                if self.logs_fullscreen:
                    try:
                        self.query_one(HeaderWidget).display = False
                    except Exception:
                        pass
        self._last_alarm_state = alarm_active

    def generate_weekly_report(self, date_str):
        try:
            metrics = self.db_service.get_weekly_audit_metrics()
            
            status = "LOCKED" if self.autopilot_service.locked else ("SAFE" if self.autopilot_service.safe_mode else "ACTIVE")
            try:
                health_score = self.query_one(AutopilotPanel).health_score
            except Exception:
                health_score = 100
                
            uptime_days = self.autopilot_service.get_uptime_days()
            
            report_content = f"""# P3 NOC — Weekly Autonomous Audit Report
Date: {date_str}

## System Performance Metrics (Last 7 Days)
- Processed Articles: {metrics.get('processed', 0)}
- Failed Queue Items: {metrics.get('failed', 0)}
- Auto Recoveries Executed: {metrics.get('recovered', 0)}
- Average Inference Latency: {metrics.get('avg_latency', 0.0):.2f}s

## Subsystem Health Assessment
- Autopilot Status: {status}
- Health Score: {health_score}/100
- Host Uptime: {uptime_days} Days

Report generated autonomously by P3 NOC Autopilot.
"""
            report_dir = "/opt/p3-noc/reports"
            try:
                os.makedirs(report_dir, exist_ok=True)
            except Exception:
                report_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
                os.makedirs(report_dir, exist_ok=True)
                
            report_path = os.path.join(report_dir, f"{date_str}-weekly-report.md")
            with open(report_path, "w") as f:
                f.write(report_content)
                
            self.last_audit_date = date_str
            self.latest_report_path = report_path
            self.app.call_from_thread(self.notify, f"Weekly audit report generated: {os.path.basename(report_path)}")
        except Exception as e:
            logger.error(f"Failed to generate weekly report: {e}")

    def action_show_weekly_report(self):
        """Display the weekly report."""
        if not self.latest_report_path or not os.path.exists(self.latest_report_path):
            self.notify("Generating current week report on demand...")
            self.run_worker(self._generate_and_show_report_job, thread=True)
        else:
            self._show_report_modal(self.latest_report_path)

    def _generate_and_show_report_job(self):
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            self.generate_weekly_report(today_str)
            self.app.call_from_thread(self._show_report_modal, self.latest_report_path)
        except Exception as e:
            logger.error(f"Error generating/showing report on demand: {e}")
            self.app.call_from_thread(self.notify, "Failed to generate report on demand", severity="error")

    def _show_report_modal(self, filepath):
        try:
            with open(filepath, "r") as f:
                content = f.read()
            self.push_screen(
                WeeklyReportDialog(
                    title=f"WEEKLY AUDIT REPORT: {os.path.basename(filepath)}",
                    report_text=content,
                    theme_name=THEMES[self.theme_index]
                )
            )
        except Exception as e:
            self.notify(f"Could not read report file: {e}", severity="error")

# --- Weekly Report Dialog & Autopilot Helpers ---

class WeeklyReportDialog(ModalScreen):
    CSS = """
    WeeklyReportDialog {
        align: center middle;
    }
    #report-box {
        padding: 1 2;
        width: 65;
        height: 18;
    }
    #report-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #report-body {
        height: 10;
        margin-bottom: 1;
        overflow-y: scroll;
    }
    #close-btn {
        width: 100%;
    }

    /* Explicit theme styles for #report-box and #report-title to avoid CSS variables */
    .matrix-green #report-box {
        border: thick #00ff00;
        background: #041404;
        color: #00ff00;
    }
    .matrix-green #report-title {
        background: #00ff00;
        color: #020a02;
    }

    .amber-crt #report-box {
        border: thick #ffb000;
        background: #140d00;
        color: #ffb000;
    }
    .amber-crt #report-title {
        background: #ffb000;
        color: #0a0600;
    }

    .cyber-blue #report-box {
        border: thick #00f0ff;
        background: #001222;
        color: #00f0ff;
    }
    .cyber-blue #report-title {
        background: #00f0ff;
        color: #000911;
    }

    .red-alert #report-box {
        border: thick #ff3333;
        background: #220000;
        color: #ff3333;
    }
    .red-alert #report-title {
        background: #ff3333;
        color: #110000;
    }

    .matrix #report-box {
        border: thick #00ff00;
        background: #000000;
        color: #00ff00;
    }
    .matrix #report-title {
        background: #00ff00;
        color: #000000;
    }

    .bloomberg #report-box {
        border: thick #ff8800;
        background: #000022;
        color: #ff8800;
    }
    .bloomberg #report-title {
        background: #ff8800;
        color: #000033;
    }

    .trading-desk #report-box {
        border: thick #00ffff;
        background: #222222;
        color: #00ffff;
    }
    .trading-desk #report-title {
        background: #00ffff;
        color: #1c1c1c;
    }

    .midnight #report-box {
        border: thick #ffffff;
        background: #000000;
        color: #ffffff;
    }
    .midnight #report-title {
        background: #ffffff;
        color: #000000;
    }
    """

    def __init__(self, title: str, report_text: str, theme_name="matrix-green", **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.report_text = report_text
        self.theme_name = theme_name

    def compose(self):
        yield Container(
            Static(self.title, id="report-title"),
            Static(self.report_text, id="report-body"),
            Button("Close [Esc/Enter]", variant="primary", id="close-btn"),
            id="report-box"
        )

    def on_mount(self):
        self.add_class(self.theme_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss()

    def on_key(self, event) -> None:
        if event.key in ("escape", "enter", "space"):
            self.dismiss()

# --- Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P3 NOC — Bitcoin Intelligence Operations Center")
    parser.add_argument("--wallboard", action="store_true", help="Launch in wallboard mode (auto-focus rotation, double border, no footer)")
    args = parser.parse_args()

    app = P3NocApp(wallboard_mode=args.wallboard)
    app.run()
