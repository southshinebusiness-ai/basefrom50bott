"""Integration tests: signed HTTP notifications must never grant unpaid access."""
import hashlib
import hmac
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import quote

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from config import config
from db import database as db
from handlers.yoomoney_webhook import handle_yoomoney_notify


def signed_payload(**overrides):
    payload = {
        "notification_type": "card-incoming",
        "operation_id": "operation-42",
        "amount": "1930.00",
        "withdraw_amount": "1990.00",
        "currency": "643",
        "datetime": "2026-10-29T11:00:00Z",
        "sender": "",
        "codepro": "false",
        "unaccepted": "false",
        "label": "order-42",
    }
    payload.update(overrides)
    canonical = "&".join(
        f"{key}={quote(str(value), safe='-._~')}"
        for key, value in sorted(payload.items())
    )
    payload["sign"] = hmac.new(
        b"test-secret", canonical.encode(), hashlib.sha256
    ).hexdigest()
    return payload


class WebhookTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = config.DB_PATH
        self.old_secret = config.YOOMONEY_SECRET
        config.DB_PATH = os.path.join(self.tmp.name, "test.db")
        config.YOOMONEY_SECRET = "test-secret"
        await db.init_db()
        await db.add_user(42, "buyer", "Buyer")
        await db.create_payment(42, 1990, "ultimate_guide", "order-42")
        app = web.Application()
        app["bot"] = object()
        app.router.add_post("/yoomoney/notify", handle_yoomoney_notify)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        config.DB_PATH = self.old_path
        config.YOOMONEY_SECRET = self.old_secret
        self.tmp.cleanup()

    async def test_signed_payment_confirmed_once(self):
        with patch(
            "handlers.yoomoney_webhook.deliver_paid_access",
            new_callable=AsyncMock,
        ) as deliver:
            resp = await self.client.post("/yoomoney/notify", data=signed_payload())
            self.assertEqual(resp.status, 200)
            self.assertEqual((await db.get_payment_by_label("order-42"))["status"], "completed")
            self.assertTrue((await db.get_user(42))["purchased_guide"])
            self.assertEqual(deliver.await_count, 1)

            resp = await self.client.post("/yoomoney/notify", data=signed_payload())
            self.assertEqual(resp.status, 200)
            # Функция выдачи вызывается повторно, но её DB claim_delivery
            # предотвращает повторную отправку уже доставленной ссылки.

    async def test_bad_signature_never_confirms(self):
        payload = signed_payload()
        payload["amount"] = "99999.00"
        resp = await self.client.post("/yoomoney/notify", data=payload)
        self.assertEqual(resp.status, 403)
        self.assertEqual((await db.get_payment_by_label("order-42"))["status"], "pending")

    async def test_wrong_gross_amount_never_confirms(self):
        resp = await self.client.post(
            "/yoomoney/notify", data=signed_payload(withdraw_amount="1.00")
        )
        self.assertEqual(resp.status, 200)
        self.assertEqual((await db.get_payment_by_label("order-42"))["status"], "pending")

    async def test_unknown_label_never_confirms(self):
        resp = await self.client.post(
            "/yoomoney/notify", data=signed_payload(label="other-order")
        )
        self.assertEqual(resp.status, 200)
        self.assertEqual((await db.get_payment_by_label("order-42"))["status"], "pending")


if __name__ == "__main__":
    unittest.main()
