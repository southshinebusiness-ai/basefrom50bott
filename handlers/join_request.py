"""
Обработчик запросов на вступление в закрытый канал.

Логика:
- Юзер кликает invite-ссылку → отправляет запрос на вступление
- Бот проверяет в БД: купил ли этот user_id ULTIMATE GUIDE
- Если купил → approve (одобряем)
- Если нет → decline (отклоняем)

Так работает надёжно: даже если ссылку получат 100 человек,
войдёт только тот кто заплатил.
"""
from aiogram import Router
from aiogram.types import ChatJoinRequest

from db import database as db
from config import config

router = Router()


@router.chat_join_request()
async def handle_join_request(update: ChatJoinRequest):
    """Обрабатывает запрос на вступление в закрытый канал."""
    user_id = update.from_user.id
    chat_id = update.chat.id

    # Обрабатываем только запросы в наш закрытый канал
    if chat_id != config.PRIVATE_CHANNEL_ID:
        return

    user = await db.get_user(user_id)
    has_access = user and user.get("purchased_guide")

    if has_access:
        # Юзер купил гайд — одобряем
        await update.approve()
        try:
            await update.bot.send_message(
                user_id,
                "✅ <b>Добро пожаловать в ULTIMATE GUIDE!</b>\n\n"
                "Твой запрос одобрен — ты теперь в канале.\n"
                "Внутри: гайд, база поставщиков и все бонусы.\n\n"
                "get rich or die tryin' 💀",
                parse_mode="HTML"
            )
        except Exception:
            pass  # Юзер мог заблокировать бота

        await db.log_event(user_id, "channel_join_approved")
    else:
        # Не нашли оплату — отклоняем
        await update.decline()
        try:
            await update.bot.send_message(
                user_id,
                "❌ Запрос на вступление отклонён.\n\n"
                "Доступ к каналу доступен только после покупки "
                "ULTIMATE GUIDE. Жми /start чтобы перейти к покупке.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        await db.log_event(user_id, "channel_join_declined")
