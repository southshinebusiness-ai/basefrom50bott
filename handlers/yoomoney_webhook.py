"""Приём подписанных HTTP-уведомлений ЮMoney (HMAC-SHA256, протокол 2026)."""
import logging

from aiohttp import web

from db import database as db
from config import config
from utils.payment_delivery import deliver_paid_access
from utils.yoomoney import verify_signature, validate_notification

logger = logging.getLogger(__name__)


async def handle_yoomoney_notify(request: web.Request) -> web.Response:
    """Подтверждает только известные заказы с правильной суммой и подписью."""
    try:
        form = await request.post()
        if not form:
            # Кнопка «Протестировать» в настройках ЮMoney может отправить
            # пустое уведомление, не являющееся настоящим платежом.
            return web.Response(text="test ok")
        if len(form) != len(set(form.keys())):
            return web.Response(status=400, text="duplicate parameters")
        data = dict(form)

        if not verify_signature(data, config.YOOMONEY_SECRET):
            logger.warning("YooMoney notification rejected: invalid HMAC-SHA256")
            return web.Response(status=403, text="invalid signature")

        label = data.get("label", "")
        payment = await db.get_payment_by_label(label)
        if not payment:
            logger.info("YooMoney notification for unknown order ignored")
            return web.Response(text="ignored")

        if not validate_notification(data, payment):
            logger.warning("YooMoney notification failed order/amount validation")
            return web.Response(text="invalid order")

        operation_id = data["operation_id"]
        confirmed = await db.confirm_payment(label, operation_id)
        if not confirmed:
            logger.warning("YooMoney duplicate operation or order mismatch")
            return web.Response(text="duplicate operation")

        await db.log_event(payment["user_id"], "guide_purchased_webhook", {
            "label": label, "operation_id": operation_id,
        })

        # Ошибку Telegram не превращаем в потерю оплаты: состояние уже
        # сохранено, фоновый worker повторит выдачу доступа.
        await deliver_paid_access(request.app["bot"], label)
        return web.Response(text="ok")
    except Exception:
        logger.exception("YooMoney webhook internal error")
        # Не отвечаем 200 при сбое БД: ЮMoney сделает повторную доставку.
        return web.Response(status=503, text="retry later")
