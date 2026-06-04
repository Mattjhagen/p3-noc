from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from config.themes import THEME_COLORS

from config.settings import OLLAMA_REMOTE

class RunbookPanel(Static):
    """
    Operator Runbook Action panel.
    Displays available F6-F12 operations recovery controls.
    """
    current_theme = reactive("matrix-green")

    def on_mount(self):
        self.border_title = "OPERATOR ACTIONS"

    def render(self) -> Text:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary = theme["primary"]
        muted = theme["muted"]
        accent = theme["accent"]

        content = Text()
        
        # Line 1: F6 & F9
        content.append(" F6  ", style=f"bold {accent}")
        content.append(f"{'Restart Wrk':<12}", style="white")
        content.append(" | F9  ", style=f"bold {accent}")
        content.append("Clear Stuck\n", style="white")

        # Line 2: F7 & F10
        content.append(" F7  ", style=f"bold {accent}")
        content.append(f"{'Restart Ing':<12}", style="white")
        content.append(" | F10 ", style=f"bold {accent}")
        ollama_lbl = "Restart [D]" if OLLAMA_REMOTE else "Restart LLM"
        content.append(f"{ollama_lbl}\n", style="white")

        # Line 3: F8 & F11
        content.append(" F8  ", style=f"bold {accent}")
        content.append(f"{'Requeue Fail':<12}", style="white")
        content.append(" | F11 ", style=f"bold {accent}")
        content.append("Warm Cache\n", style="white")

        # Line 4: F12
        content.append(" F12 ", style=f"bold {accent}")
        content.append("Execute Full Health Recovery\n", style="white")

        return content
