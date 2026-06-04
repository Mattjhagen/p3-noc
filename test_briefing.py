import sys
import os
import json
import logging
from datetime import datetime

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_briefing")

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import DATABASE_URL, OLLAMA_URL, OLLAMA_MODEL
from services.db_service import DBService
from services.ollama_service import OllamaService
from dashboard import classify_headline_impact

def main():
    logger.info("Initializing services...")
    db_service = DBService()
    ollama_service = OllamaService()
    
    db_ok = db_service.check_db_health()
    logger.info(f"Database health: {'ONLINE' if db_ok else 'OFFLINE'}")
    if not db_ok:
        sys.exit(1)
        
    logger.info("Fetching articles...")
    articles = db_service.get_latest_analyzed_articles_for_briefing(limit=50)
    logger.info(f"Found {len(articles)} articles.")
    
    if not articles:
        logger.warning("No articles found in PostgreSQL.")
        sys.exit(0)
        
    # Local computed variables (defaults)
    now_str = datetime.now().strftime("%I:%M %p")
    market_state = "NEUTRAL"
    confidence_str = "0%"
    themes = ["Market consolidation", "Institutional flows", "ETF activity"]
    risks = ["Macro uncertainty", "Regulatory headlines", "Reduced volume"]
    outlook = "Range-bound with moderate volatility."
    summary = "AI summary loading..."
    ai_online = False

    bull_count = 0
    bear_count = 0
    neutral_count = 0
    total_weight = 0
    sentiment_weight = 0
    category_counts = {}
    category_risk_scores = {}
    
    for art in articles:
        title = art.get("title", "")
        sentiment = str(art.get("sentiment", "")).upper()
        importance = float(art.get("importance_score") or 1)
        
        if "BULL" in sentiment:
            bull_count += 1
            total_weight += importance
            sentiment_weight += importance
        elif "BEAR" in sentiment:
            bear_count += 1
            total_weight += importance
            sentiment_weight -= importance
        else:
            neutral_count += 1
            total_weight += importance
        
        category = classify_headline_impact(title)
        category_counts[category] = category_counts.get(category, 0) + 1
        
        risk_val = 0
        if "BEAR" in sentiment:
            risk_val = importance
        elif "BULL" not in sentiment:  # NEUTRAL
            risk_val = importance * 0.5
        category_risk_scores[category] = category_risk_scores.get(category, 0.0) + risk_val

    if bull_count > bear_count:
        market_state = "BULLISH"
    elif bear_count > bull_count:
        market_state = "BEARISH"
    else:
        market_state = "NEUTRAL"
        
    if total_weight > 0:
        confidence_val = int(round((abs(sentiment_weight) / total_weight) * 100))
    else:
        confidence_val = 0
    confidence_str = f"{confidence_val}%"
        
    sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    THEME_MAP = {
        "ETF": "ETF activity",
        "WHALE": "Whale movements",
        "SECURITY": "Security protocols",
        "MINING": "Mining operations",
        "REGULATION": "Regulatory progress",
        "EXCHANGE": "Exchange flows",
        "MACRO": "Macroeconomics",
        "MARKET": "Market consolidation"
    }
    DEFAULT_THEMES = ["Market consolidation", "Institutional flows", "ETF activity"]
    themes = []
    for cat, _ in sorted_cats:
        theme_str = THEME_MAP.get(cat, "Market consolidation")
        if theme_str not in themes:
            themes.append(theme_str)
    while len(themes) < 3:
        for default in DEFAULT_THEMES:
            if default not in themes:
                themes.append(default)
                break
        else:
            themes.append("Market consolidation")
    themes = themes[:3]

    sorted_risks = sorted(category_risk_scores.items(), key=lambda x: x[1], reverse=True)
    RISK_MAP = {
        "ETF": "ETF outflows",
        "WHALE": "Whale selling pressure",
        "SECURITY": "Vulnerabilities/hacks",
        "MINING": "Miner capitulation",
        "REGULATION": "Regulatory headlines",
        "EXCHANGE": "Exchange outflows",
        "MACRO": "Macro uncertainty",
        "MARKET": "Reduced volume"
    }
    DEFAULT_RISKS = ["Macro uncertainty", "Regulatory headlines", "Reduced volume"]
    risks = []
    for cat, score in sorted_risks:
        if score > 0:
            risk_str = RISK_MAP.get(cat, "Reduced volume")
            if risk_str not in risks:
                risks.append(risk_str)
    while len(risks) < 3:
        for default in DEFAULT_RISKS:
            if default not in risks:
                risks.append(default)
                break
        else:
            risks.append("Reduced volume")
    risks = risks[:3]

    if market_state == "BULLISH":
        outlook = "Upside momentum with positive sentiment."
    elif market_state == "BEARISH":
        outlook = "Downside pressure with support testing."
    else:
        outlook = "Range-bound with moderate volatility."

    logger.info(f"Local computation results:")
    logger.info(f" - Market State: {market_state}")
    logger.info(f" - Confidence: {confidence_str}")
    logger.info(f" - Themes: {themes}")
    logger.info(f" - Risks: {risks}")
    logger.info(f" - Outlook: {outlook}")

    logger.info(f"Querying Ollama at {OLLAMA_URL} with model {OLLAMA_MODEL}...")
    headlines = [art.get("title", "") for art in articles[:15]]
    headlines_str = "\n".join(f"- {h}" for h in headlines)
    prompt_text = (
        f"headlines:\n{headlines_str}\n\n"
        "Synthesize a concise one-sentence operator briefing from these market headlines."
    )
    
    import requests
    try:
        res = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": OLLAMA_MODEL,
            "prompt": prompt_text,
            "stream": False
        }, timeout=45.0)
        
        logger.info(f"Ollama response status: {res.status_code}")
        if res.status_code == 200:
            summary = res.json().get("response", "").strip()
            summary = summary.replace('"', '').replace('`', '').strip()
            ai_online = True
            logger.info(f"Generated summary: {summary}")
        else:
            logger.error(f"Response text: {res.text}")
    except Exception as e:
        logger.exception("Failed to query Ollama:")

    briefing_object = {
        "summary": summary,
        "market_state": market_state,
        "confidence": confidence_str,
        "themes": themes,
        "risks": risks,
        "outlook": outlook,
        "updated": now_str,
        "ai_online": ai_online
    }
    
    # Save cache
    try:
        cache_dir = "/opt/p3-noc/cache"
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "market_briefing.json")
        logger.info(f"Saving cache to {cache_path}...")
        with open(cache_path, "w") as f:
            json.dump(briefing_object, f)
        logger.info("Successfully saved cache.")
    except Exception as e:
        logger.exception("Failed to save cache file:")

if __name__ == "__main__":
    main()
