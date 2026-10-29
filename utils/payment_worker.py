"""Фоновое восстановление подтверждённых платежей и повторная выдача доступа."""
import asyncio
import logging

from aiogram import Bot

from config import config
from db import database as db
from utils.payment_delivery import deliver_paid_access
from utils.yoomoney_api import find_confirmed_operation, YooMoneyAPIError

logger = logging.getLogger(__name__)


async def reconcile_payment(bot: Bot, payment: dict) -> bool:
    """Проверяет конкретный заказ в API кошелька и выдаёт доступ при успехе."""
    try:
        operation = await find_confirmed_operation(payment)
    finally:
        await db.mark_payment_checked(payment["label"])

    if not operation:
        return False

    confirmed = await db.confirm_payment(payment["label"], str(operation["operation_id"]))
    if not confirmed:
        logger.warning("Reconciliation rejected duplicate operation for %s", payment["label"])
        return False
    await db.log_event(payment["user_id"], "guide_purchased_reconciled", {
        "label": payment["label"],
        "operation_id": str(operation["operation_id"]),
    })
    await deliver_paid_access(bot, payment["label"])
    return True


async def maintenance_loop(bot: Bot):
    """Безопасно восстанавливает доставку даже после рестарта процесса."""
    iteration = 0
    while True:
        try:
            for payment in await db.get_pending_deliveries(limit=10):
                await deliver_paid_access(bot, payment["label"])

            # Раз в 5 минут сверяем недавние неоплаченные заказы с ЮMoney.
            if config.YOOMONEY_TOKEN and iteration % 5 == 0:
                for payment in await db.get_pending_for_reconciliation(limit=10):
                    try:
                        await reconcile_payment(bot, payment)
                    except YooMoneyAPIError as exc:
                        logger.warning("Reconciliation unavailable: %s", exc)
                        break
                    except Exception:
                        logger.exception("Failed to reconcile payment")
            iteration += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Payment maintenance loop error")
        await asyncio.sleep(60)
