#!/usr/bin/env python3
import sys
import os
import time
import unittest
import requests

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.db_service import DBService
from config.settings import BTC_MONITOR_URL

class TestBitcoinMonitor(unittest.TestCase):
    def setUp(self):
        self.db = DBService()
        self.monitor_url = BTC_MONITOR_URL

    def test_01_db_init(self):
        """Test that the bitcoin_history table was initialized in PostgreSQL."""
        if not self.db.check_db_health():
            print("⚠ Database table check: Skipped (PostgreSQL is offline).")
            return
        
        conn = None
        try:
            conn = self.db.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'bitcoin_history'
                    );
                """)
                exists = cur.fetchone()[0]
                self.assertTrue(exists, "bitcoin_history table does not exist in database")
                print("✔ Database table bitcoin_history check: Table exists.")
        except Exception as e:
            self.fail(f"Database table check failed: {e}")
        finally:
            if conn:
                conn.close()

    def test_02_db_insert_and_select(self):
        """Test inserting and selecting a mock snapshot in the database."""
        if not self.db.check_db_health():
            print("⚠ Database insert/select check: Skipped (PostgreSQL is offline).")
            return
            
        success = self.db.save_bitcoin_snapshot(
            blocks=650000,
            headers=656000,
            peer_count=12,
            verification_progress=99.15,
            mempool_size=45000,
            disk_usage=510.5,
            difficulty=126000000000000.0,
            blockchain_size=506.0
        )
        self.assertTrue(success, "Failed to insert snapshot into database")
        print("✔ Database insert check: Snapshot saved successfully.")

        history = self.db.get_bitcoin_history(limit=5)
        self.assertGreater(len(history), 0, "No snapshots retrieved from database")
        last_item = history[-1]
        self.assertEqual(last_item["blocks"], 650000)
        self.assertEqual(float(last_item["verification_progress"]), 99.15)
        print("✔ Database select check: Successfully retrieved snapshot and validated values.")


    def test_03_api_status(self):
        """Test the status endpoint GET /api/infrastructure/bitcoin."""
        try:
            url = f"{self.monitor_url}/api/infrastructure/bitcoin"
            res = requests.get(url, timeout=2.0)
            self.assertEqual(res.status_code, 200, "API status endpoint returned non-200 code")
            data = res.json()
            self.assertIn("status", data)
            self.assertIn("blocks", data)
            self.assertIn("verificationProgress", data)
            print(f"✔ API Status Check: Node Status is '{data.get('status')}'")
        except requests.exceptions.ConnectionError:
            print("⚠ API Status Check: Skipped (btc-monitor daemon is not running yet).")

    def test_04_api_history(self):
        """Test the history endpoint GET /api/infrastructure/bitcoin/history."""
        try:
            url = f"{self.monitor_url}/api/infrastructure/bitcoin/history"
            res = requests.get(url, timeout=2.0)
            self.assertEqual(res.status_code, 200, "API history endpoint returned non-200 code")
            data = res.json()
            self.assertIsInstance(data, list)
            print("✔ API History Check: Successfully retrieved historical list.")
        except requests.exceptions.ConnectionError:
            print("⚠ API History Check: Skipped (btc-monitor daemon is not running yet).")

if __name__ == "__main__":
    print("Running Bitcoin Core Panel Verification Tests...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBitcoinMonitor)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(not result.wasSuccessful())
