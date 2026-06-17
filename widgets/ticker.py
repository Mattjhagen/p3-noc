from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

class TickerWidget(Static):
    """
    Renders a Bloomberg-style scrolling bottom ticker displaying BTC price,
    queue load, Ollama status, and latest article headlines.
    """
    btc_price_str = reactive("$104,822")
    btc_change_str = reactive("+2.4%")
    btc_positive = reactive(True)
    queue_remaining = reactive(0)
    eta_str = reactive("1h 29m")
    ollama_status = reactive("ONLINE")
    latest_title = reactive("No headlines yet.")
    
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.ticker_offset = 0
        self.ticker_text = ""
        self.border_title = "MARKET TICKER"
        # Run scroll timer frequently (every 100ms) for smooth animation
        self.set_interval(0.12, self.animate_ticker)

    def update_ticker_text(self):
        """Recompile the ticker text string from state variables."""
        sign = "▲" if self.btc_positive else "▼"
        self.ticker_text = (
            f"BTC {self.btc_price_str} {sign}{self.btc_change_str}  •  "
            f"Queue Remaining: {self.queue_remaining} (ETA: {self.eta_str})  •  "
            f"Ollama Server: {self.ollama_status}  •  "
            f"Latest Headline: {self.latest_title}"
        )

    def animate_ticker(self):
        """Scroll the compiled ticker text by shifting characters."""
        self.update_ticker_text()
        if not self.ticker_text:
            return

        try:
            full_width = self.app.size.width
        except Exception:
            full_width = 80
        text_with_gap = self.ticker_text + "   ||   "
        
        # Calculate offset
        self.ticker_offset = (self.ticker_offset + 1) % len(text_with_gap)
        
        # Construct scrolling sliced text
        scrolled = text_with_gap[self.ticker_offset:] + text_with_gap[:self.ticker_offset]
        
        # Ensure it fits the terminal width by padding or cropping
        display_str = scrolled[:full_width - 4]
        
        # Apply theme styling
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        
        text_obj = Text(display_str, style=primary)
        # Highlight ONLINE green and OFFLINE red independently
        text_obj.highlight_words(["ONLINE"], "bold green")
        text_obj.highlight_words(["OFFLINE"], "bold red")
        
        self.update(text_obj)
