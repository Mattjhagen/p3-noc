import datetime
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class AiMarketBriefingWidget(Static):
    """
    AI MARKET BRIEFING Panel.
    Displays color-coded market state, top themes, key risks,
    outlook, and confidence matching the terminal layout exactly.
    """
    market_state = reactive("NEUTRAL")
    confidence = reactive("N/A")
    briefing_text = reactive("")
    generated_at = reactive(None)
    stale_mode = reactive(False)
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "AI MARKET BRIEFING"
        # Refresh widget rendering every 10 seconds to update age alerts
        self.set_interval(10.0, self.refresh)

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        accent = theme["accent"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        content = Text()
        
        # Parse themes, risks, and outlook from briefing_text
        themes = []
        risks = []
        outlook = "No outlook available."
        
        if self.briefing_text:
            lines = [l.strip() for l in self.briefing_text.splitlines() if l.strip()]
            current_section = None
            for line in lines:
                line_upper = line.upper()
                if "THEMES" in line_upper:
                    current_section = "themes"
                    continue
                elif "RISKS" in line_upper:
                    current_section = "risks"
                    continue
                elif "OUTLOOK" in line_upper:
                    current_section = "outlook"
                    if ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1 and parts[1].strip():
                            outlook = parts[1].strip()
                    continue
                elif "CONFIDENCE" in line_upper or "STATE:" in line_upper:
                    current_section = None
                    continue
                    
                if current_section == "themes":
                    cleaned = line.lstrip("•-* ").strip()
                    if cleaned:
                        themes.append(cleaned)
                elif current_section == "risks":
                    cleaned = line.lstrip("•-* ").strip()
                    if cleaned:
                        risks.append(cleaned)
                elif current_section == "outlook":
                    outlook = line.strip()
                    current_section = None

        # Build lines matching the target layout:
        # Line 1: MARKET STATE: BULLISH/BEARISH/NEUTRAL
        state = self.market_state.upper().strip()
        state_style = healthy if "BULL" in state else (error if "BEAR" in state else warning)
        content.append("MARKET STATE: ", style="white")
        content.append(f"{state}\n", style=f"bold {state_style}")
        
        # Line 2: (blank)
        content.append("\n")
        
        # Line 3: THEMES
        content.append("THEMES\n", style=f"bold {primary}")
        
        # Line 4 & 5: Themes bullets
        for t in themes[:2]:
            cropped = t[:76]
            content.append(f"• {cropped}\n", style="white")
        for _ in range(2 - len(themes[:2])):
            content.append("•\n", style="white")
            
        # Line 6: (blank)
        content.append("\n")
        
        # Line 7: RISKS
        content.append("RISKS\n", style=f"bold {primary}")
        
        # Line 8 & 9: Risks bullets
        for r in risks[:2]:
            cropped = r[:76]
            content.append(f"• {cropped}\n", style="white")
        for _ in range(2 - len(risks[:2])):
            content.append("•\n", style="white")
            
        # Line 10: (blank)
        content.append("\n")
        
        # Line 11: 24H OUTLOOK
        content.append("24H OUTLOOK\n", style=f"bold {primary}")
        
        # Line 12: Outlook description
        cropped_outlook = outlook[:76]
        content.append(f"{cropped_outlook}\n", style="white")
        
        # Line 13: (blank)
        content.append("\n")
        
        # Line 14: CONFIDENCE XX%
        conf_val = self.confidence.strip()
        if conf_val and "%" not in conf_val and conf_val != "N/A":
            conf_val += "%"
        content.append("CONFIDENCE ", style="white")
        content.append(f"{conf_val}\n", style=f"bold {accent}")
        
        # Line 15: HH:MM UTC (and stale warnings)
        time_str = "N/A"
        if self.generated_at:
            try:
                if isinstance(self.generated_at, str):
                    dt_str = self.generated_at.split("+")[0].split(".")[0]
                    gen_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                else:
                    gen_dt = self.generated_at
                time_str = gen_dt.strftime("%H:%M UTC")
            except Exception:
                pass
                
        status_line = ""
        if self.generated_at:
            try:
                if isinstance(self.generated_at, str):
                    dt_str = self.generated_at.split("+")[0].split(".")[0]
                    gen_dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                elif isinstance(self.generated_at, datetime.datetime):
                    if self.generated_at.tzinfo is not None:
                        gen_dt = self.generated_at.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    else:
                        gen_dt = self.generated_at
                else:
                    gen_dt = None

                if gen_dt:
                    age_delta = datetime.datetime.utcnow() - gen_dt
                    age_minutes = age_delta.total_seconds() / 60.0
                    
                    if age_minutes > 120.0:  # > 2 hours
                        status_line = "🚨 AI BRIEFING OFFLINE"
                    elif age_minutes > 30.0:  # > 30 minutes
                        status_line = "⚠ AI BRIEFING STALE"
            except Exception:
                pass

        if self.stale_mode:
            if status_line:
                status_line += " - "
            status_line += "AI Briefing stale — waiting for AI server."

        if status_line:
            content.append(f"{time_str}  ({status_line})\n", style="cyan")
        else:
            content.append(f"{time_str}\n", style="cyan")

        return content
