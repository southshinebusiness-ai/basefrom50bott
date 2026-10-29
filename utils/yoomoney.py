"""Проверка уведомлений ЮMoney (протокол 2026) и операций кошелька.

Официальная документация:
https://yoomoney.ru/docs/payment-buttons/using-api/notifications
https://yoomoney.ru/docs/wallet/user-account/operation-history
"""
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import re
from urllib.parse import quote


def verify_signature(data: dict, secret: str) -> bool:
    """HMAC-SHA256 параметра sign; устаревший sha1_hash не используется.

    По спецификации URL-кодируются значения (RFC 3986), параметры
    сортируются по имени, параметр sign исключается.
    """
    if not secret or not isinstance(data, dict):
        return False
    received = str(data.get("sign", ""))
    if not re.fullmatch(r"[a-fA-F0-9]{64}", received):
        return False
    canonical = "&".join(
        f"{key}={quote(str(value), safe='-._~')}"
        for key, value in sorted(data.items())
        if key != "sign"
    )
    expected = hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received.lower())


def money(value) -> Decimal | None:
    """Точное сравнение денежных сумм без float-арифметики."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def validate_notification(data: dict, payment: dict) -> bool:
    """Проверяет уже подписанное уведомление относительно заказа в нашей БД.

    amount — зачислено после комиссии; withdraw_amount — списано у покупателя.
    Поэтому сверяем цену именно с withdraw_amount.
    """
    if not payment or not data.get("operation_id"):
        return False
    if data.get("label") != payment.get("label"):
        return False
    if payment.get("product") != "ultimate_guide":
        return False
    if data.get("notification_type") not in {"p2p-incoming", "card-incoming"}:
        return False
    if str(data.get("currency")) != "643":
        return False
    if str(data.get("unaccepted", "false")).lower() != "false":
        return False
    if str(data.get("codepro", "false")).lower() != "false":
        return False

    expected = money(payment.get("amount"))
    gross = money(data.get("withdraw_amount"))
    net = money(data.get("amount"))
    return bool(
        expected is not None
        and gross is not None
        and net is not None
        and expected > 0
        and gross == expected
        and 0 < net <= gross
    )


def validate_history_operation(operation: dict, payment: dict) -> bool:
    """Консервативная проверка fallback по API кошелька.

    В operation-history входящая сумма обычно указана ПОСЛЕ комиссии.
    Полную списанную сумму этот API не отдаёт, поэтому допускаем максимум
    3,2% комиссии; более неоднозначные платежи требуют ручной проверки.
    """
    if not operation or not payment or not operation.get("operation_id"):
        return False
    if operation.get("status") != "success":
        return False
    if operation.get("direction") != "in":
        return False
    if operation.get("type") not in {"incoming-transfer", "deposition"}:
        return False
    if operation.get("label") != payment.get("label"):
        return False
    if payment.get("product") != "ultimate_guide":
        return False

    expected = money(payment.get("amount"))
    received = money(operation.get("amount"))
    return bool(
        expected is not None
        and received is not None
        and expected > 0
        and expected * Decimal("0.968") <= received <= expected
    )
