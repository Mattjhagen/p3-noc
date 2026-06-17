class RoutingService:
    """
    Multi-model intelligence routing engine.
    Optimizes article throughput and inference latency by routing high-impact
    headlines to the deep model and normal headlines to the fast model.
    Supports Safe Mode override which restricts all routing to the fast model.
    """
    def __init__(self, model_fast=None, model_deep="qwen3:8b"):
        from config.settings import OLLAMA_MODEL
        self.model_fast = model_fast if model_fast else OLLAMA_MODEL
        self.model_deep = model_deep
        self.safe_mode_active = False

    def set_safe_mode(self, active: bool):
        self.safe_mode_active = active

    def get_model_for_article(self, title: str) -> str:
        """
        Determine which Ollama model to use for analyzing an article.
        If Safe Mode is active, always falls back to the fast model.
        """
        if self.safe_mode_active:
            return self.model_fast

        t = title.lower()
        escalate_keywords = [
            "etf", "blackrock", "fidelity", "sec", "regulation", 
            "regulatory", "mt. gox", "gox", "exchange hack", "hack",
            "sovereign adoption", "macro shock", "large liquidation", 
            "liquidation", "insolvency", "court", "lawsuit", "exploit"
        ]

        if any(kw in t for kw in escalate_keywords):
            return self.model_deep
            
        return self.model_fast
