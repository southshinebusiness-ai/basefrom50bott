"""Regression test: /stats must count the current instant-delivery PDF events."""
import asyncio
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from config import config
from handlers.admin import get_full_stats


class FreeGuideStatsTests(unittest.TestCase):
    def test_free_guide_events_are_counted_by_unique_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bot.db")
            conn = sqlite3.connect(path)
            conn.executescript("""
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    lesson_progress INTEGER DEFAULT 0,
                    course_completed INTEGER DEFAULT 0,
                    purchased_guide INTEGER DEFAULT 0
                );
                CREATE TABLE events (
                    user_id INTEGER,
                    event_type TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE payments (
                    amount INTEGER,
                    status TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO users (user_id) VALUES (1), (2), (3);
                INSERT INTO events (user_id,event_type) VALUES
                    (1,'free_guide_opened'),
                    (1,'free_guide_opened'),
                    (2,'free_guide_opened'),
                    (1,'free_guide_sent'),
                    (2,'free_guide_sent'),
                    (3,'received_pdfs');
            """)
            conn.commit()
            conn.close()
            with patch.object(config, "DB_PATH", path):
                stats = asyncio.run(get_full_stats())
            self.assertEqual(stats["free_opened"], 2)
            self.assertEqual(stats["free_sent"], 2)
            self.assertEqual(stats["got_pdf"], 1)
            self.assertEqual(stats["total"], 3)


if __name__ == "__main__":
    unittest.main()
