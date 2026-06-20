#!/usr/bin/env python3
"""
Bitcoin Research Ingest Worker
Polls RSS feeds, stores articles, sends to Ollama for analysis, saves results.
"""
import os
import time
import json
import logging
import hashlib
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ingest_worker")

# --- Config ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://researcher:secure_password_change_me@localhost:5432/bitcoin_research")
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "100.105.154.91").strip()
OLLAMA_PORT  = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))   # seconds between feed polls
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300")) # seconds to wait for Ollama

OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"

RSS_FEEDS = [
    {"name": "CoinDesk",         "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "Bitcoin Magazine",  "url": "https://bitcoinmagazine.com/.rss/full/"},
    {"name": "Blockworks",        "url": "https://blockworks.co/feed"},
    {"name": "Cointelegraph",     "url": "https://cointelegraph.com/rss"},
    {"name": "The Block",         "url": "https://www.theblock.co/rss.xml"},
]

ANALYSIS_PROMPT = """You are a Bitcoin market analyst. Analyze the following news article and respond with ONLY a JSON object, no other text.

Title: {title}
Content: {content}

Respond with exactly this JSON structure:
{{
  "sentiment": "BULLISH" or "BEARISH" or "NEUTRAL",
  "sentiment_score": float between -1.0 (very bearish) and 1.0 (very bullish),
  "importance_score": float between 0.0 (not important) and 10.0 (extremely important),
  "confidence": float between 0.0 and 1.0,
  "summary": "one sentence summary of market impact",
  "category": "ETF" or "REGULATION" or "MINING" or "MACRO" or "EXCHANGE" or "WHALE" or "SECURITY" or "MARKET"
}}"""


def get_db():
    parsed = urlparse(DATABASE_URL)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        connect_timeout=10
    )


def ensure_feed_sources(conn):
    with conn.cursor() as cur:
        for feed in RSS_FEEDS:
            cur.execute(
                "INSERT INTO feed_sources (name, enabled) VALUES (%s, true) ON CONFLICT DO NOTHING",
                (feed["name"],)
            )
    conn.commit()


def fetch_feed(feed_url: str) -> list[dict]:
    try:
        resp = requests.get(feed_url, timeout=15, headers={"User-Agent": "P3-NOC-Ingest/1.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        items = []
        # Handle both RSS and Atom
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for item in root.findall(".//item") or root.findall(".//atom:entry", ns):
            title_el   = item.find("title")
            link_el    = item.find("link")
            desc_el    = item.find("description") or item.find("summary")
            pub_el     = item.find("pubDate") or item.find("published")

            title   = title_el.text.strip()   if title_el   is not None and title_el.text   else ""
            link    = link_el.text.strip()    if link_el    is not None and link_el.text    else ""
            desc    = desc_el.text.strip()    if desc_el    is not None and desc_el.text    else ""
            pub_raw = pub_el.text.strip()     if pub_el     is not None and pub_el.text     else ""

            if title and link:
                items.append({"title": title, "url": link, "content": desc, "published": pub_raw})

        return items
    except Exception as e:
        logger.warning(f"Failed to fetch {feed_url}: {e}")
        return []


def article_exists(conn, url: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM articles WHERE url = %s", (url,))
        return cur.fetchone() is not None


def save_article(conn, title: str, url: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO articles (title, url, created_at) VALUES (%s, %s, %s) RETURNING id",
            (title, url, datetime.now(timezone.utc))
        )
        article_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO processing_queue (article_id, status, created_at, updated_at) VALUES (%s, 'pending', %s, %s)",
            (article_id, datetime.now(timezone.utc), datetime.now(timezone.utc))
        )
    conn.commit()
    return article_id


def analyze_with_ollama(title: str, content: str) -> dict | None:
    prompt = ANALYSIS_PROMPT.format(
        title=title,
        content=content[:2000] if content else "No content available."
    )
    try:
        start = time.time()
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "think": False},
            timeout=OLLAMA_TIMEOUT
        )
        elapsed_ms = (time.time() - start) * 1000
        resp.raise_for_status()

        raw = resp.json().get("response", "").strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        result["response_time_ms"] = elapsed_ms
        return result
    except json.JSONDecodeError as e:
        logger.warning(f"Ollama JSON parse error: {e} — raw: {raw[:200]}")
        return None
    except Exception as e:
        logger.warning(f"Ollama request failed: {e}")
        return None


def save_analysis(conn, article_id: int, analysis: dict, response_time_ms: float):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO analyses
               (article_id, sentiment_score, importance_score, sentiment, confidence, summary, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                article_id,
                analysis.get("sentiment_score", 0.0),
                analysis.get("importance_score", 5.0),
                analysis.get("sentiment", "NEUTRAL"),
                analysis.get("confidence", 0.5),
                analysis.get("summary", ""),
                datetime.now(timezone.utc)
            )
        )
        analysis_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO analysis_versions (analysis_id, model_name, response_time_ms, created_at)
               VALUES (%s, %s, %s, %s)""",
            (analysis_id, OLLAMA_MODEL, response_time_ms, datetime.now(timezone.utc))
        )
        cur.execute(
            """UPDATE processing_queue SET status = 'completed', updated_at = %s
               WHERE article_id = %s AND status != 'completed'""",
            (datetime.now(timezone.utc), article_id)
        )
    conn.commit()


def mark_failed(conn, article_id: int, error: str):
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE processing_queue
               SET status = 'failed', last_error = %s, retry_count = retry_count + 1, updated_at = %s
               WHERE article_id = %s""",
            (error[:500], datetime.now(timezone.utc), article_id)
        )
    conn.commit()


def update_feed_source_poll_time(conn, name: str):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE feed_sources SET last_successful_poll = %s WHERE name = %s",
            (datetime.now(timezone.utc), name)
        )
    conn.commit()


def process_pending_queue(conn):
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """SELECT q.article_id, a.title, a.url
               FROM processing_queue q
               JOIN articles a ON a.id = q.article_id
               WHERE q.status = 'pending' AND COALESCE(q.retry_count, 0) < 3
               ORDER BY q.created_at ASC
               LIMIT 10"""
        )
        pending = cur.fetchall()

    for row in pending:
        article_id = row["article_id"]
        title      = row["title"]
        logger.info(f"[queue] Analyzing article {article_id}: {title[:80]}")

        analysis = analyze_with_ollama(title, "")
        if analysis:
            save_analysis(conn, article_id, analysis, analysis.get("response_time_ms", 0))
            logger.info(f"[queue] Saved analysis for article {article_id} — {analysis.get('sentiment')} ({analysis.get('sentiment_score', 0):.2f})")
        else:
            mark_failed(conn, article_id, "Ollama returned no valid response")
            logger.warning(f"[queue] Failed to analyze article {article_id}")


def run_poll_cycle(conn):
    new_articles = 0
    for feed in RSS_FEEDS:
        logger.info(f"[feed] Polling {feed['name']}...")
        items = fetch_feed(feed["url"])
        logger.info(f"[feed] {feed['name']}: {len(items)} items fetched")

        saved = 0
        for item in items:
            if not article_exists(conn, item["url"]):
                save_article(conn, item["title"], item["url"])
                saved += 1

        if saved:
            logger.info(f"[feed] {feed['name']}: {saved} new articles saved")
            update_feed_source_poll_time(conn, feed["name"])
        new_articles += saved

    return new_articles


def main():
    logger.info("P3 Bitcoin Ingest Worker starting...")
    logger.info(f"Database: {DATABASE_URL.split('@')[-1]}")
    logger.info(f"Ollama:   {OLLAMA_URL} model={OLLAMA_MODEL}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")

    # Wait for DB
    while True:
        try:
            conn = get_db()
            logger.info("Database connected.")
            break
        except Exception as e:
            logger.warning(f"DB not ready: {e} — retrying in 10s")
            time.sleep(10)

    ensure_feed_sources(conn)

    while True:
        try:
            # Reconnect if needed
            try:
                conn.cursor().execute("SELECT 1")
            except Exception:
                logger.warning("DB connection lost — reconnecting...")
                conn = get_db()

            logger.info("--- Starting poll cycle ---")
            new = run_poll_cycle(conn)
            logger.info(f"--- Poll complete: {new} new articles ---")

            logger.info("--- Processing analysis queue ---")
            process_pending_queue(conn)
            logger.info("--- Queue processing complete ---")

        except Exception as e:
            logger.error(f"Cycle error: {e}", exc_info=True)

        logger.info(f"Sleeping {POLL_INTERVAL}s until next cycle...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
