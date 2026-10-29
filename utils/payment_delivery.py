"""Идемпотентная выдача доступа после подтверждения оплаты ЮMoney."""
import logging
from datetime import datetime, timedelta

from aiogram import Bot

from config import config
from db import database as db

logger = logging.getLogger(__name__)


async def deliver_paid_access(bot: Bot, label: str) -> bool:
    """Отправляет сохранённую пригласительную ссылку один раз.

    Сначала сохраняем invite в БД. При сбое доставки worker повторит
    отправку той же ссылки; доступ к каналу всё равно проверяет join_request.
    """
    payment = await db.claim_delivery(label)
    if not payment:
        return False

    user_id = payment["user_id"]
    try:
        invite_link = payment.get("invite_link")
        if not invite_link:
            invite = await bot.create_chat_invite_link(
                chat_id=config.PRIVATE_CHANNEL_ID,
                creates_join_request=True,
                expire_date=datetime.now() + timedelta(days=7),
                name=f"Payment {payment['id']}",
            )
            invite_link = invite.invite_link
            await db.save_invite_link(label, invite_link)

        await bot.send_message(
            user_id,
            "✅ <b>Оплата получена! Welcome, manigg!</b>\n\n"
            "Жми на ссылку → нажми «Отправить запрос» → "
            "бот автоматически одобрит вступление:\n\n"
            f"👉 {invite_link}\n\n"
            "get rich or die tryin' 💀",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await db.mark_delivery_sent(label)
        await db.log_event(user_id, "guide_access_delivered", {"label": label})
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"💰 <b>НОВАЯ ПРОДАЖА!</b>\n\n"
                f"Юзер ID: {user_id}\n"
                f"Сумма: {payment['amount']} ₽\n"
                f"Заказ: {label}",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return True
    except Exception as exc:
        logger.exception("Failed to deliver access for order %s", label)
        await db.mark_delivery_failed(label, str(exc))
        await db.log_event(user_id, "guide_delivery_failed", {"label": label})
        if payment.get("delivery_attempts", 0) == 0:
            try:
                await bot.send_message(
                    config.ADMIN_ID,
                    f"⚠️ Оплата подтверждена, но ссылка пока не отправлена.\n"
                    f"Юзер: {user_id}\nЗаказ: {label}\n"
                    "Бот повторит выдачу автоматически. При необходимости: "
                    f"/grant {user_id}",
                )
            except Exception:
                pass
        return False
