from datetime import datetime
from textual.widget import Widget
from textual.reactive import reactive
from rich.text import Text
from rich.align import Align
from config.themes import THEME_COLORS

# Large ASCII logo from request
LOGO_ASCII = """
██████╗ ██████╗ 
██╔══██╗╚════██╗
██████╔╝ █████╔╝
██╔═══╝  ╚═══██╗
██║     ██████╔╝
╚═╝     ╚═════╝ 
"""

class HeaderWidget(Widget):
    """
    Header widget displaying the P3 ASCII branding logo, Giant NOC Status Banner,
    dynamic timestamp, system services status summary, and real-time BTC ticker.
    """
    # Reactive variables to trigger re-renders
    worker_status = reactive(True)
    db_status = reactive(True)
    ollama_status = reactive(True)
    ingest_status = reactive(True)
    btc_price_str = reactive("$104,822")
    btc_change_str = reactive("+2.4%")
    btc_positive = reactive(True)
    
    risk_score = reactive(0)
    queue_remaining = reactive(0)
    eta_str = reactive("0m")
    top_event_str = reactive("No headline intelligence received.")
    
    status_str = reactive("HEALTHY")
    
    # Remote AI Server Monitoring reactive states
    ai_server_status = reactive("GREEN")
    ai_server_is_critical = reactive(False)
    ai_server_flash_toggle = reactive(False)
    
    current_theme = reactive("matrix-green")
    compact_mode = reactive(False)
    
    # Critical Alarm Reactives
    critical_alarm_active = reactive(False)
    logo_flash_phase = reactive(0)

    def render(self) -> Align:
        theme = THEME_COLORS.get(self.current_theme, THEME_COLORS["matrix-green"])
        primary_color = theme["primary"]
        muted_color = theme["muted"]
        healthy_color = theme["healthy"]
        error_color = theme["error"]
        warning_color = theme["warning"]

        # Compute Giant NOC Status Banner based on Autopilot health status
        status_upper = self.status_str.upper()
        if "SAFE" in status_upper:
            status_banner = Text(" [SAFE MODE ACTIVE]        ", style="bold white on red reverse")
        elif "INCIDENT" in status_upper:
            status_banner = Text(" [SYSTEM STATUS: 🔴 INCIDENT] ", style="bold white on red")
        elif "DEGRADED" in status_upper:
            status_banner = Text(" [SYSTEM STATUS: 🟡 DEGRADED] ", style="bold black on yellow")
        elif "LOCKED" in status_upper:
            status_banner = Text(" [AUTOPILOT: 🔴 LOCKED]       ", style="bold white on red reverse")
        else:
            status_banner = Text(" [SYSTEM STATUS: 🟢 HEALTHY]  ", style="bold white on green")

        # Compute AI Server persistent status banner
        ai_banner = Text()
        if self.ai_server_status == "GREEN":
            ai_banner = Text(" [AI SERVER: ONLINE] ", style="bold white on green")
        elif self.ai_server_status == "YELLOW":
            ai_banner = Text(" [⚠ AI SERVER DEGRADED] ", style="bold black on yellow")
        else: # RED
            if self.ai_server_is_critical:
                if self.ai_server_flash_toggle:
                    ai_banner = Text(" [🚨 CHECK AI SERVER (R510) 🚨] ", style="bold white on red")
                else:
                    ai_banner = Text(" [🚨 CHECK AI SERVER (R510) 🚨] ", style="bold red on black")
            else:
                if self.ai_server_flash_toggle:
                    ai_banner = Text(" [🚨 CHECK AI SERVER (R510) 🚨] ", style="bold white on red")
                else:
                    ai_banner = Text(" [🚨 CHECK AI SERVER (R510) 🚨] ", style="bold red")

        # Determine logo styling and borders
        if self.critical_alarm_active:
            # Alternating colors: Phase 0 = Green, Phase 1 = Red
            if self.logo_flash_phase == 0:
                logo_style = "bold bright_green on black"
                compact_style = "bold white on green"
            else:
                logo_style = "bold bright_red on black"
                compact_style = "bold white on red"

            # Wrap logo in an ASCII alarm border
            logo_lines = [line for line in LOGO_ASCII.splitlines() if line.strip()]
            max_len = max(len(line) for line in logo_lines)
            bordered_lines = []
            bordered_lines.append(f"┌─{'─' * max_len}─┐")
            for line in logo_lines:
                padded = line.ljust(max_len)
                bordered_lines.append(f"│ {padded} │")
            bordered_lines.append(f"└─{'─' * max_len}─┘")
            logo_text = Text("\n".join(bordered_lines) + "\n", style=logo_style)

            # Define the flashing alert banner
            if self.logo_flash_phase == 0:
                alert_banner = Text("\n🚨 CRITICAL SYSTEM FAULT - OPERATOR INTERVENTION REQUIRED 🚨\n", style="bold white on red")
            else:
                alert_banner = Text("\n🚨 CRITICAL SYSTEM FAULT - OPERATOR INTERVENTION REQUIRED 🚨\n", style="bold red on white")
        else:
            # Healthy: Green on black logo
            logo_style = "bold bright_green on black"
            logo_text = Text(LOGO_ASCII, style=logo_style)
            compact_style = f"bold reverse {primary_color}"
            alert_banner = Text()

        # Build ASCII branding header if NOT in compact mode
        header_text = Text()
        if not self.compact_mode:
            header_text.append(logo_text)
            sub = Text("P3 NOC — Bitcoin Intelligence Operations Center      ", style=f"bold {primary_color}")
            header_text.append(sub)
            header_text.append(status_banner)
            header_text.append(" ")
            header_text.append(ai_banner)
            if self.critical_alarm_active:
                header_text.append(alert_banner)
            header_text.append("\n")
        else:
            # Minimal compact logo
            header_text.append(Text(" P3 NOC ", style=compact_style))
            header_text.append(Text("   "))
            header_text.append(status_banner)
            header_text.append(" ")
            header_text.append(ai_banner)
            if self.critical_alarm_active:
                header_text.append(alert_banner)
            header_text.append(Text("\n"))

        # Build the Executive Summary Banner text
        banner = Text()
        
        # 1. BTC Price & Change
        btc_style = healthy_color if self.btc_positive else warning_color
        sign = "▲" if self.btc_positive else "▼"
        banner.append("BTC ", style="bold white")
        banner.append(f"{self.btc_price_str} ({sign}{self.btc_change_str})", style=btc_style)
        banner.append("  |  ", style=muted_color)

        # 2. Risk score (e.g. RISK: 72 (HIGH))
        if self.risk_score <= 33:
            risk_label = "LOW"
            risk_color = healthy_color
        elif self.risk_score <= 66:
            risk_label = "MED"
            risk_color = warning_color
        else:
            risk_label = "HIGH"
            risk_color = error_color
        banner.append("RISK: ", style="bold white")
        banner.append(f"{self.risk_score} ({risk_label})", style=f"bold {risk_color}")
        banner.append("  |  ", style=muted_color)

        # 3. Queue Remaining
        banner.append("QUEUE: ", style="bold white")
        banner.append(f"{self.queue_remaining} REMAINING", style=warning_color)
        banner.append("  |  ", style=muted_color)

        # 4. ETA
        banner.append("ETA: ", style="bold white")
        banner.append(self.eta_str, style="white")
        banner.append("  |  ", style=muted_color)

        # 5. Ollama Status
        ollama_status_str = "ONLINE" if self.ollama_status else "OFFLINE"
        ollama_color = healthy_color if self.ollama_status else error_color
        banner.append("OLLAMA: ", style="bold white")
        banner.append(ollama_status_str, style=ollama_color)
        banner.append("  |  ", style=muted_color)

        # 6. Top Event
        banner.append("TOP EVENT: ", style="bold white")
        cropped_headline = self.top_event_str
        if len(cropped_headline) > 42:
            cropped_headline = cropped_headline[:39] + "..."
        banner.append(cropped_headline, style=primary_color)

        # Right-aligned clock
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_line_right = Text(f"🕒 {time_str}", style=muted_color)
        
        # Merge banner and clock
        try:
            full_width = self.app.size.width
        except Exception:
            full_width = 80
        content_len = len(banner.plain) + len(status_line_right.plain)
        padding_spaces = max(1, full_width - content_len - 6)
        
        banner.append(" " * padding_spaces)
        banner.append(status_line_right)
        
        # Join branding and status bar with a divider line
        divider = Text("─" * (full_width - 2), style=muted_color)
        
        result_text = Text()
        if not self.compact_mode:
            result_text.append(header_text)
            result_text.append(divider)
            result_text.append(Text("\n"))
        else:
            result_text.append(header_text)
        
        result_text.append(banner)
        result_text.append(Text("\n"))
        result_text.append(divider)

        return Align.center(result_text)
