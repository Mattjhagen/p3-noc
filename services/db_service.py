import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime, timedelta
from config.settings import DATABASE_URL

logger = logging.getLogger("dashboard")

class DBService:
    def __init__(self):
        self.db_url = DATABASE_URL
        self.init_operations_log_table()
        self.init_briefing_cache_table()
        self.init_bitcoin_history_table()

    def init_operations_log_table(self):
        """Create operations_log table if it does not exist."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS operations_log (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        severity VARCHAR(50) NOT NULL,
                        event TEXT NOT NULL,
                        action_taken TEXT,
                        result TEXT,
                        host VARCHAR(100) DEFAULT 'p3noc'
                    );
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize operations_log table: {e}")
        finally:
            if conn:
                conn.close()

    def get_connection(self):
        """Establish a connection to the database. May raise psycopg2 exceptions."""
        return psycopg2.connect(self.db_url, connect_timeout=3)

    def check_db_health(self) -> bool:
        """Test database connection health."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_queue_counts(self) -> dict:
        """
        Query processing_queue counts by status.
        Returns: { 'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0 }
        """
        counts = {'pending': 0, 'processing': 0, 'completed': 0, 'failed': 0}
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status, COUNT(*) 
                    FROM processing_queue 
                    GROUP BY status;
                """)
                rows = cur.fetchall()
                for status, count in rows:
                    if status in counts:
                        counts[status] = count
                    elif status == 'dead_letter':
                        # Group dead_letter under failed for status displays if needed,
                        # or track it. Let's add it to failed count.
                        counts['failed'] += count
            return counts
        except Exception as e:
            logger.error(f"Failed to get queue counts: {e}")
            return counts  # Return default zeros on error
        finally:
            if conn:
                conn.close()

    def get_latest_articles(self, limit=50) -> list:
        """
        Get latest analyzed articles.
        Returns: list of dicts with title, sentiment_score, importance_score, sentiment, confidence.
        """
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT a.id, a.title, an.sentiment_score, an.importance_score, 
                           an.sentiment, an.confidence, an.created_at
                    FROM analyses an
                    JOIN articles a ON an.article_id = a.id
                    ORDER BY an.created_at DESC
                    LIMIT %s;
                """, (limit,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch latest articles: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_latest_analysis(self) -> dict:
        """
        Get the single latest article analysis details for the Risk Radar.
        """
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT a.title, an.sentiment_score, an.importance_score, 
                           an.sentiment, an.confidence, an.summary
                    FROM analyses an
                    JOIN articles a ON an.article_id = a.id
                    ORDER BY an.created_at DESC
                    LIMIT 1;
                """)
                row = cur.fetchone()
                return row if row else {}
        except Exception as e:
            logger.error(f"Failed to fetch latest analysis: {e}")
            return {}
        finally:
            if conn:
                conn.close()

    def get_queue_throughput(self) -> dict:
        """
        Compute queue throughput and ETA.
        Returns: {
            'processed_last_hour': int,
            'avg_time': float, (in seconds)
            'remaining': int,
            'eta_str': str, (e.g. "1h 29m")
            'max_retry': int
        }
        """
        stats = {
            'processed_last_hour': 0,
            'avg_time': 0.0,
            'remaining': 0,
            'eta_str': "0m",
            'max_retry': 0
        }
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # 1. Processed in the last hour
                cur.execute("""
                    SELECT COUNT(*) FROM analyses 
                    WHERE created_at >= NOW() - INTERVAL '1 hour';
                """)
                stats['processed_last_hour'] = cur.fetchone()[0]

                # 2. Avg analysis time (in seconds)
                # First try last hour
                cur.execute("""
                    SELECT AVG(response_time_ms) FROM analysis_versions 
                    WHERE created_at >= NOW() - INTERVAL '1 hour';
                """)
                avg_ms = cur.fetchone()[0]
                if avg_ms is None:
                    # Fallback to overall average
                    cur.execute("SELECT AVG(response_time_ms) FROM analysis_versions;")
                    avg_ms = cur.fetchone()[0]
                
                stats['avg_time'] = (float(avg_ms) / 1000.0) if avg_ms is not None else 224.0 # Fallback default 224s

                # 3. Queue remaining
                cur.execute("""
                    SELECT COUNT(*) FROM processing_queue 
                    WHERE status IN ('pending', 'processing', 'failed');
                """)
                stats['remaining'] = cur.fetchone()[0]

                # 4. Max retry count in active queue
                cur.execute("""
                    SELECT MAX(retry_count) FROM processing_queue 
                    WHERE status IN ('pending', 'processing', 'failed');
                """)
                val = cur.fetchone()[0]
                stats['max_retry'] = val if val is not None else 0

                # 5. ETA Calculation
                total_seconds = stats['remaining'] * stats['avg_time']
                if total_seconds > 0:
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    if hours > 0:
                        stats['eta_str'] = f"{hours}h {minutes}m"
                    else:
                        stats['eta_str'] = f"{minutes}m"
                else:
                    stats['eta_str'] = "0m"

            return stats
        except Exception as e:
            logger.error(f"Failed to calculate queue throughput: {e}")
            return stats
        finally:
            if conn:
                conn.close()

    def get_processed_today(self) -> int:
        """Count analyses processed today since midnight local time."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Count analyses since start of today
                cur.execute("""
                    SELECT COUNT(*) FROM analyses 
                    WHERE created_at >= CURRENT_DATE;
                """)
                return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to count processed today: {e}")
            return 0
        finally:
            if conn:
                conn.close()

    def get_hourly_risk_history(self) -> list:
        """
        Query average risk (importance_score) grouped by hour for the last 24 hours.
        Returns: list of exactly 24 integers representing hourly averages.
        """
        history = [0] * 24
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DATE_TRUNC('hour', created_at) AS hr, AVG(importance_score) as avg_risk
                    FROM analyses
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY hr
                    ORDER BY hr ASC;
                """)
                rows = cur.fetchall()
                
                # Align rows into 24-hour bins
                now = datetime.now()
                # Create 24 hourly timestamps ending now
                bins = [now - timedelta(hours=i) for i in range(23, -1, -1)]
                
                # Map query results to their closest bins
                row_map = {}
                for hr, avg_risk in rows:
                    if hr:
                        # Normalize timezone if necessary
                        hr_naive = hr.replace(tzinfo=None)
                        row_map[hr_naive.hour] = int(avg_risk)
                
                # Fill the history list
                last_val = 0
                for idx, b in enumerate(bins):
                    h = b.hour
                    if h in row_map:
                        history[idx] = row_map[h]
                        last_val = row_map[h]
                    else:
                        history[idx] = last_val # forward-fill last known risk level
            return history
        except Exception as e:
            logger.error(f"Failed to fetch hourly risk history: {e}")
            return [0] * 24
        finally:
            if conn:
                conn.close()

    def requeue_failed_items(self) -> bool:
        """Requeue failed and dead_letter queue items by setting status='pending' and retry_count=0."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE processing_queue 
                    SET status = 'pending', retry_count = 0, last_error = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE status IN ('failed', 'dead_letter');
                """)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to requeue failed items: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def clear_stuck_processing(self) -> bool:
        """Clear items stuck in 'processing' status for over 15 minutes by marking them 'failed'."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE processing_queue 
                    SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'processing' 
                      AND updated_at <= CURRENT_TIMESTAMP - INTERVAL '15 minutes';
                """)
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to clear stuck processing items: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def get_rss_feed_health(self) -> bool:
        """Verify that RSS feeds are queryable and have successfully polled in the last 24 hours."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Check if there's any successful feed poll in the last 24 hours
                cur.execute("""
                    SELECT COUNT(*) FROM feed_sources 
                    WHERE enabled = TRUE 
                      AND (last_successful_poll IS NULL OR last_successful_poll >= NOW() - INTERVAL '24 hours');
                """)
                count = cur.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(f"Failed to check RSS feed health: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def log_operations_event(self, severity: str, event: str, action_taken: str, result: str, host="p3noc"):
        """Insert a recovery or system health journal log entry."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO operations_log (severity, event, action_taken, result, host)
                    VALUES (%s, %s, %s, %s, %s);
                """, (severity, event, action_taken, result, host))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log operations event: {e}")
        finally:
            if conn:
                conn.close()

    def get_last_operations_actions(self, limit=4) -> list:
        """Fetch the last N operations actions taken from the log journal."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT timestamp, severity, event, action_taken, result 
                    FROM operations_log 
                    ORDER BY timestamp DESC 
                    LIMIT %s;
                """, (limit,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to get last operations actions: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_weekly_audit_metrics(self) -> dict:
        """Fetch processed articles, errors, recoveries, and latencies for the last 7 days."""
        conn = None
        metrics = {"processed": 0, "failed": 0, "recovered": 0, "avg_latency": 0.0}
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Processed in the last 7 days
                cur.execute("SELECT COUNT(*) FROM analyses WHERE created_at >= NOW() - INTERVAL '7 days';")
                metrics["processed"] = cur.fetchone()[0]

                # Failed in the last 7 days
                cur.execute("SELECT COUNT(*) FROM processing_queue WHERE status = 'failed' AND updated_at >= NOW() - INTERVAL '7 days';")
                metrics["failed"] = cur.fetchone()[0]

                # Count recoveries logged in the last 7 days
                cur.execute("SELECT COUNT(*) FROM operations_log WHERE result = 'SUCCESS' AND timestamp >= NOW() - INTERVAL '7 days';")
                metrics["recovered"] = cur.fetchone()[0]

                # Average latency in the last 7 days
                cur.execute("SELECT AVG(response_time_ms) FROM analysis_versions WHERE created_at >= NOW() - INTERVAL '7 days';")
                avg_ms = cur.fetchone()[0]
                metrics["avg_latency"] = (float(avg_ms) / 1000.0) if avg_ms is not None else 58.2
        except Exception as e:
            logger.error(f"Failed to fetch weekly audit metrics: {e}")
        finally:
            if conn:
                conn.close()
        return metrics

    def get_oldest_processing_age(self) -> float:
        """Returns the oldest processing job age in minutes."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXTRACT(EPOCH FROM (NOW() - MIN(updated_at)))/60 
                    FROM processing_queue 
                    WHERE status = 'processing';
                """)
                val = cur.fetchone()[0]
                return float(val) if val is not None else 0.0
        except Exception:
            return 0.0
        finally:
            if conn:
                conn.close()

    def init_briefing_cache_table(self):
        """Create briefing_cache table if it does not exist."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS briefing_cache (
                        id SERIAL PRIMARY KEY,
                        market_state VARCHAR(50) NOT NULL,
                        confidence VARCHAR(10) NOT NULL,
                        briefing_text TEXT NOT NULL,
                        generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize briefing_cache table: {e}")
        finally:
            if conn:
                conn.close()

    def save_briefing_to_cache(self, market_state: str, confidence: str, briefing_text: str) -> bool:
        """Persist generated AI briefing to database cache."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO briefing_cache (market_state, confidence, briefing_text, generated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP);
                """, (market_state, confidence, briefing_text))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save briefing to cache: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def get_latest_cached_briefing(self) -> dict:
        """Retrieve the most recent AI briefing from PostgreSQL cache."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT market_state, confidence, briefing_text, generated_at
                    FROM briefing_cache
                    ORDER BY generated_at DESC
                    LIMIT 1;
                """)
                return cur.fetchone()
        except Exception as e:
            logger.error(f"Failed to fetch latest cached briefing: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_latest_analysis_id(self) -> int:
        """Get the max ID in analyses to track new arrivals."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(id) FROM analyses;")
                val = cur.fetchone()[0]
                return val if val is not None else 0
        except Exception:
            return 0
        finally:
            if conn:
                conn.close()

    def get_latest_analyzed_articles_for_briefing(self, limit=10) -> list:
        """Get latest articles and analyses for briefing Ollama context."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT a.title, an.sentiment, an.importance_score, an.summary
                    FROM analyses an
                    JOIN articles a ON an.article_id = a.id
                    ORDER BY an.created_at DESC
                    LIMIT %s;
                """, (limit,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch analyzed articles for briefing: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_last_analysis_time(self):
        """Get the created_at timestamp of the most recent analysis version."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT created_at FROM analysis_versions ORDER BY created_at DESC LIMIT 1;")
                row = cur.fetchone()
                return row[0] if row else None
        except Exception:
            return None
        finally:
            if conn:
                conn.close()

    def init_bitcoin_history_table(self):
        """Create bitcoin_history table if it does not exist."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bitcoin_history (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        blocks INTEGER NOT NULL,
                        headers INTEGER NOT NULL,
                        peer_count INTEGER NOT NULL,
                        verification_progress NUMERIC(5, 2) NOT NULL,
                        mempool_size INTEGER NOT NULL,
                        disk_usage NUMERIC(10, 2) NOT NULL,
                        difficulty NUMERIC(30, 4) NOT NULL,
                        blockchain_size NUMERIC(10, 2) NOT NULL
                    );
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize bitcoin_history table: {e}")
        finally:
            if conn:
                conn.close()

    def save_bitcoin_snapshot(self, blocks: int, headers: int, peer_count: int,
                              verification_progress: float, mempool_size: int,
                              disk_usage: float, difficulty: float, blockchain_size: float) -> bool:
        """Persist a new Bitcoin Core node state snapshot."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bitcoin_history (
                        blocks, headers, peer_count, verification_progress,
                        mempool_size, disk_usage, difficulty, blockchain_size
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (blocks, headers, peer_count, verification_progress,
                      mempool_size, disk_usage, difficulty, blockchain_size))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to save bitcoin snapshot: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def get_bitcoin_history(self, limit=288) -> list:
        """Retrieve historical bitcoin node snapshots, ordered by timestamp ascending."""
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT timestamp, blocks, headers, peer_count, verification_progress,
                           mempool_size, disk_usage, difficulty, blockchain_size
                    FROM bitcoin_history
                    ORDER BY timestamp DESC
                    LIMIT %s;
                """, (limit,))
                # Order ascending for time series graphing
                rows = cur.fetchall()
                return list(reversed(rows))
        except Exception as e:
            logger.error(f"Failed to fetch bitcoin history: {e}")
            return []
        finally:
            if conn:
                conn.close()

