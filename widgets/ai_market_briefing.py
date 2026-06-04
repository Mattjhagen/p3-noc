import datetime
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

def get_greeting() -> str:
    """Helper to return greeting based on local server time."""
    hour = datetime.datetime.now().hour
    if 5 <= hour < 12:
        return "Good Morning Matty,"
    elif 12 <= hour < 17:
        return "Good Afternoon Matty,"
    else:
        return "Good Evening Matty,"

class AiMarketBriefingWidget(Static):
    """
    AI MARKET BRIEFING Panel.
    Fits in the exact WORKER LOGS footprint (9 rows).
    Renders structured PostgreSQL-derived news telemetry
    and an Ollama-generated summary sentence.
    """
    # Reactive briefing data object
    briefing_data = reactive({
        "summary": "AI summary loading...",
        "market_state": "NEUTRAL",
        "confidence": "0%",
        "themes": ["Market consolidation", "Institutional flows", "ETF activity"],
        "risks": ["Macro uncertainty", "Regulatory headlines", "Reduced volume"],
        "outlook": "Range-bound with moderate volatility.",
        "updated": "N/A",
        "ai_online": True
    })
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "AI MARKET BRIEFING"
        # Refresh widget rendering every 10 seconds to keep greeting and time current
        self.set_interval(10.0, self.refresh)

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        data = self.briefing_data or {}
        summary = data.get("summary", "No summary available.")
        state = data.get("market_state", "NEUTRAL").upper().strip()
        confidence = data.get("confidence", "N/A")
        themes = data.get("themes", [])
        risks = data.get("risks", [])
        outlook = data.get("outlook", "No outlook available.")
        updated = data.get("updated", "N/A")
        ai_online = data.get("ai_online", True)

        # 1. Greeting
        greeting = get_greeting()
        
        # Color coding state
        state_style = healthy if "BULL" in state else (error if "BEAR" in state else warning)

        content = Text()
        
        # Row 1: Greeting + Summary
        # Maximum character width of TTY is 80 columns. Printable space inside borders is 78 chars.
        greeting_line = f"{greeting} {summary}"
        if len(greeting_line) > 78:
            greeting_line = greeting_line[:75] + "..."
        content.append(f"{greeting_line}\n", style="white")

        # Row 2: Market State | Confidence | Updated
        content.append("Market State: ", style="white")
        content.append(state, style=f"bold {state_style}")
        content.append(" | Confidence: ", style="white")
        content.append(confidence, style=f"bold {accent}")
        content.append(" | Updated: ", style="white")
        updated_suffix = "" if ai_online else " (AI Offline)"
        content.append(f"{updated}{updated_suffix}\n", style="cyan")

        # Row 3: Themes | Risks header columns side-by-side
        # Column 1 starts at 0, Column 2 starts at 40
        header_row = f"{'Themes:':<40}{'Risks:'}"
        content.append(f"{header_row}\n", style=f"bold {primary}")

        # Rows 4-6: Theme bullets and Risk bullets side-by-side
        for i in range(3):
            t_val = themes[i] if i < len(themes) else ""
            r_val = risks[i] if i < len(risks) else ""
            
            t_bullet = f"• {t_val}" if t_val else ""
            r_bullet = f"• {r_val}" if r_val else ""
            
            # Format columns
            t_cropped = t_bullet[:37]
            line_str = f"{t_cropped:<40}{r_bullet[:38]}"
            content.append(f"{line_str}\n", style="white")

        # Row 7: Outlook
        outlook_line = f"Outlook: {outlook}"
        if len(outlook_line) > 78:
            outlook_line = outlook_line[:75] + "..."
        content.append(outlook_line, style="white")

        return content
