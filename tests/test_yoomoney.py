"""Тесты протокола ЮMoney 2026: официальный HMAC-вектор и защита от подмены."""
import unittest

from utils.yoomoney import (
    verify_signature, validate_notification, validate_history_operation,
)

# Официальный пример из документации ЮMoney:
# https://yoomoney.ru/docs/payment-buttons/using-api/notifications
EXAMPLE = {
    "notification_type": "p2p-incoming",
    "operation_id": "441361714955017004",
    "amount": "98.00",
    "withdraw_amount": "100.00",
    "currency": "643",
    "datetime": "2013-12-26T08:28:34Z",
    "sender": "41000000000",
    "codepro": "false",
    "label": "ML23045",
    "unaccepted": "false",
    "sha1_hash": "ac13833bd6ba9eff1fa9e4bed76f3d6ebb57f6c0",
    "sign": "a452af731650e2c5b39abcdc7c28dd27db7b3b654c2230ad2c386e64afb98605",
}
PAYMENT = {"label": "ML23045", "amount": 100, "product": "ultimate_guide"}
HISTORY = {
    "status": "success", "direction": "in", "type": "incoming-transfer",
    "operation_id": "441361714955017004", "label": "ML23045",
    "amount": 97.0,
}


class YooMoneySignatureTests(unittest.TestCase):
    def test_official_hmac_vector(self):
        self.assertTrue(verify_signature(EXAMPLE, "secret123"))

    def test_tampered_amount_rejected(self):
        changed = dict(EXAMPLE, amount="198.00")
        self.assertFalse(verify_signature(changed, "secret123"))

    def test_wrong_secret_rejected(self):
        self.assertFalse(verify_signature(EXAMPLE, "wrong"))

    def test_sha1_only_rejected(self):
        changed = dict(EXAMPLE)
        changed.pop("sign")
        self.assertFalse(verify_signature(changed, "secret123"))

    def test_missing_secret_rejected(self):
        self.assertFalse(verify_signature(EXAMPLE, ""))


class YooMoneyPaymentTests(unittest.TestCase):
    def test_correct_gross_with_net_fee(self):
        self.assertTrue(validate_notification(EXAMPLE, PAYMENT))

    def test_wrong_gross_amount_rejected(self):
        self.assertFalse(validate_notification(dict(EXAMPLE, withdraw_amount="99.00"), PAYMENT))

    def test_wrong_label_rejected(self):
        self.assertFalse(validate_notification(dict(EXAMPLE, label="another"), PAYMENT))

    def test_wrong_currency_rejected(self):
        self.assertFalse(validate_notification(dict(EXAMPLE, currency="840"), PAYMENT))

    def test_frozen_payment_rejected(self):
        self.assertFalse(validate_notification(dict(EXAMPLE, unaccepted="true"), PAYMENT))

    def test_missing_operation_id_rejected(self):
        self.assertFalse(validate_notification(dict(EXAMPLE, operation_id=""), PAYMENT))

    def test_history_success_with_fee(self):
        self.assertTrue(validate_history_operation(HISTORY, PAYMENT))

    def test_history_wrong_direction_rejected(self):
        self.assertFalse(validate_history_operation(dict(HISTORY, direction="out"), PAYMENT))

    def test_history_underpayment_rejected(self):
        self.assertFalse(validate_history_operation(dict(HISTORY, amount=80), PAYMENT))

    def test_history_wrong_label_rejected(self):
        self.assertFalse(validate_history_operation(dict(HISTORY, label="wrong"), PAYMENT))

    def test_history_pending_rejected(self):
        self.assertFalse(validate_history_operation(dict(HISTORY, status="in_progress"), PAYMENT))


if __name__ == "__main__":
    unittest.main()
