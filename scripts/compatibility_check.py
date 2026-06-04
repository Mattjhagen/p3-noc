import sys
import os
import asyncio

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all widgets
from widgets.header import HeaderWidget
from widgets.system_panel import SystemPanel
from widgets.throughput_panel import ThroughputPanel
from widgets.sys_metrics_panel import SysMetricsPanel
from widgets.risk_radar import RiskRadar
from widgets.risk_trend_panel import RiskTrendPanel
from widgets.ollama_panel import OllamaPanel
from widgets.alert_panel import AlertPanel
from widgets.runbook_panel import RunbookPanel
from widgets.autopilot_panel import AutopilotPanel
from widgets.news_feed import NewsFeed
from widgets.log_panel import LogPanel
from widgets.ticker import TickerWidget
from widgets.display_rotation_control import DisplayRotationControl
from widgets.ai_market_briefing import AiMarketBriefingWidget
from dashboard import P3NocApp

def test_individual_widgets():
    print("Testing individual widgets instantiation and render methods...")
    
    widgets = [
        ("HeaderWidget", HeaderWidget()),
        ("SystemPanel", SystemPanel()),
        ("ThroughputPanel", ThroughputPanel()),
        ("SysMetricsPanel", SysMetricsPanel()),
        ("RiskRadar", RiskRadar()),
        ("RiskTrendPanel", RiskTrendPanel()),
        ("OllamaPanel", OllamaPanel()),
        ("AlertPanel", AlertPanel()),
        ("RunbookPanel", RunbookPanel()),
        ("AutopilotPanel", AutopilotPanel()),
        ("NewsFeed", NewsFeed()),
        ("LogPanel", LogPanel()),
        ("TickerWidget", TickerWidget()),
        ("DisplayRotationControl", DisplayRotationControl(is_readonly=False)),
        ("AiMarketBriefingWidget", AiMarketBriefingWidget()),
    ]
    
    for name, w in widgets:
        print(f" - Instantiated {name} successfully.")
        # Call render if class defines it
        if hasattr(w, "render") and callable(w.render):
            try:
                res = w.render()
                print(f"   ✓ {name}.render() executed successfully.")
            except Exception as e:
                print(f"   ✗ {name}.render() failed: {e}")
                raise e

async def test_full_app():
    print("Testing P3NocApp headless execution (mount, compose, intervals)...")
    app = P3NocApp()
    try:
        async with app.run_test() as pilot:
            # Let it run for 1.5 seconds to trigger status updates, ticker scrolls, and initial autopilot ticks
            await pilot.pause(1.5)
        print("✓ P3NocApp headless execution completed successfully with zero exceptions!")
    except Exception as e:
        print(f"✗ P3NocApp headless execution failed: {e}")
        raise e

def main():
    try:
        test_individual_widgets()
        asyncio.run(test_full_app())
        print("\nAll compatibility checks passed successfully! Build is solid.")
        sys.exit(0)
    except Exception as e:
        print(f"\nCompatibility check FAILED: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
