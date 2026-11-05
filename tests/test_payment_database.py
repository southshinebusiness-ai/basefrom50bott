"""Тесты атомарного подтверждения, повторов и миграции старой базы."""
import os
import sqlite3
import tempfile
import unittest

from config import config
from db import database as db


class PaymentDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = config.DB_PATH
        config.DB_PATH = os.path.join(self.tmp.name, "payments.db")
        await db.init_db()
        await db.add_user(123, "test", "Tester")

    async def asyncTearDown(self):
        config.DB_PATH = self.old_path
        self.tmp.cleanup()

    async def test_confirm_and_idempotency(self):
        await db.create_payment(123, 1990, "ultimate_guide", "bf50_123_one")
        result = await db.confirm_payment("bf50_123_one", "op-1")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["operation_id"], "op-1")
        self.assertTrue((await db.get_user(123))["purchased_guide"])

        again = await db.confirm_payment("bf50_123_one", "op-1")
        self.assertEqual(again["status"], "completed")
        self.assertIsNone(await db.confirm_payment("bf50_123_one", "op-2"))

    async def test_operation_id_cannot_be_reused(self):
        await db.create_payment(123, 1990, "ultimate_guide", "first")
        await db.create_payment(456, 1990, "ultimate_guide", "second")
        self.assertIsNotNone(await db.confirm_payment("first", "op-same"))
        self.assertIsNone(await db.confirm_payment("second", "op-same"))
        self.assertEqual((await db.get_payment_by_label("second"))["status"], "pending")

    async def test_delivery_state(self):
        await db.create_payment(123, 1990, "ultimate_guide", "delivery")
        await db.confirm_payment("delivery", "op-delivery")
        self.assertIsNotNone(await db.claim_delivery("delivery"))
        self.assertIsNone(await db.claim_delivery("delivery"))
        await db.save_invite_link("delivery", "https://t.me/+example")
        await db.mark_delivery_failed("delivery", "temporary")
        self.assertIsNotNone(await db.claim_delivery("delivery"))
        await db.mark_delivery_sent("delivery")
        self.assertIsNone(await db.claim_delivery("delivery"))
        result = await db.get_payment_by_label("delivery")
        self.assertEqual(result["delivery_status"], "sent")
        self.assertEqual(result["invite_link"], "https://t.me/+example")

    async def test_pending_reconciliation_selection(self):
        await db.create_payment(123, 1990, "ultimate_guide", "pending")
        self.assertIsNotNone(await db.get_latest_payment(123))
        await db.mark_payment_checked("pending")
        self.assertEqual((await db.get_payment_by_label("pending"))["status"], "pending")


class MigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_paid_orders_not_redelivered(self):
        with tempfile.TemporaryDirectory() as directory:
            old_path = config.DB_PATH
            try:
                config.DB_PATH = os.path.join(directory, "old.db")
                with sqlite3.connect(config.DB_PATH) as conn:
                    conn.execute("""CREATE TABLE payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER, amount INTEGER, product TEXT,
                        status TEXT DEFAULT 'pending', label TEXT UNIQUE,
                        operation_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )""")
                    conn.execute(
                        "INSERT INTO payments(user_id,amount,product,status,label,operation_id)"
                        " VALUES(123,1990,'ultimate_guide','completed','old','op-old')"
                    )
                await db.init_db()
                old = await db.get_payment_by_label("old")
                self.assertEqual(old["delivery_status"], "legacy")
                self.assertEqual(await db.get_pending_deliveries(), [])
            finally:
                config.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
