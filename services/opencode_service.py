import subprocess
import logging
import json
from typing import Optional

logger = logging.getLogger("dashboard")

class OpenCodeService:
    """
    Service to interact with OpenCode free AI models.
    Uses the opencode CLI to generate responses.
    Supports: gemini-free, deepseek, claude-fable models.
    """

    def __init__(self, model="gemini-free/gemini-3-flash-preview"):
        self.model = model
        self.status_cache = "UNKNOWN"

    def check_status(self) -> str:
        """Check if OpenCode service is available."""
        # Return cached status if we've checked recently
        if self.status_cache != "UNKNOWN":
            return self.status_cache

        try:
            # Quick check - just see if opencode command exists
            result = subprocess.run(
                ["which", "opencode"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                self.status_cache = "ONLINE"
                return "ONLINE"
            else:
                self.status_cache = "OFFLINE"
                return "OFFLINE"
        except Exception as e:
            logger.warning(f"OpenCode status check failed: {e}")
            self.status_cache = "OFFLINE"
            return "OFFLINE"

    def generate_response(self, prompt: str, max_length: int = 500) -> Optional[str]:
        """
        Generate a response using OpenCode Big Pickle.

        Args:
            prompt: The prompt to send to the AI
            max_length: Maximum response length (not strictly enforced)

        Returns:
            AI response as string, or None if failed
        """
        try:
            # Run opencode with the prompt
            result = subprocess.run(
                [
                    "opencode",
                    "run",
                    prompt,
                    "--model", self.model,
                    "--pure"  # Run without external plugins for faster response
                ],
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            if result.returncode == 0:
                # Extract the response from stdout
                response = result.stdout.strip()
                # Remove ANSI color codes
                response = self._strip_ansi(response)
                logger.info(f"OpenCode response generated (model: {self.model})")
                return response
            else:
                logger.error(f"OpenCode generation failed: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.error("OpenCode generation timed out")
            return None
        except Exception as e:
            logger.error(f"OpenCode generation error: {e}")
            return None

    def analyze_issue(self, issue_description: str) -> Optional[str]:
        """
        Analyze a system issue and suggest fixes.

        Args:
            issue_description: Description of the issue

        Returns:
            Analysis and recommendations
        """
        prompt = f"""Analyze this system issue and provide a concise fix recommendation:

Issue: {issue_description}

Provide:
1. Root cause (one line)
2. Recommended fix (one command or action)
3. Prevention tip (one line)

Keep response under 300 characters."""

        return self.generate_response(prompt)

    def get_stats(self) -> dict:
        """Get OpenCode service statistics."""
        status = self.check_status()
        # Extract model name for display
        model_display = self.model.split("/")[-1] if "/" in self.model else self.model
        return {
            "model": model_display,
            "server": "OpenCode Free AI",
            "status": status,
            "provider": "gemini-free" if "gemini" in self.model else "opencode",
            "latency": "~2s",  # Gemini is fast
            "cost": "$0.00"
        }

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Remove ANSI color codes from text."""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
