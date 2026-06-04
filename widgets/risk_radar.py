from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from rich.align import Align
from config.themes import THEME_COLORS

class RiskRadar(Static):
    """
    Displays the primary risk intelligence radar:
    renders a stylized ASCII circular dial that dynamically changes color
    based on the latest article's importance/risk score (0-100).
    """
    risk_score = reactive(0)
    sentiment_str = reactive("Neutral")
    sentiment_score = reactive(0.0)
    importance_score = reactive(0)
    confidence_str = reactive("medium")
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "RISK RADAR"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        healthy = theme["healthy"]
        warning = theme["warning"]
        error = theme["error"]

        if self.risk_score <= 33:
            dial_color = healthy
        elif self.risk_score <= 66:
            dial_color = warning
        else:
            dial_color = error

        # Sentiment mappings for display
        sentiment_label = self.sentiment_str.capitalize()
        sent_style = healthy if "pos" in self.sentiment_str.lower() else (error if "neg" in self.sentiment_str.lower() else "white")

        content = Text()
        
        # Line 1
        content.append("  .-~-.  ", style=dial_color)
        content.append(" Sent: ", style="white")
        content.append(f"{sentiment_label} ({self.sentiment_score:+.2f})\n", style=sent_style)

        # Line 2
        content.append(f" ( {self.risk_score:>3} ) ", style=dial_color)
        content.append(" Imp:  ", style="white")
        content.append(f"{self.importance_score}/100\n", style=primary)

        # Line 3
        content.append("  '-~-'  ", style=dial_color)
        content.append(" Conf: ", style="white")
        content.append(f"{self.confidence_str.upper()}\n", style=primary)

        return content
