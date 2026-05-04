"""
Админ-команды (доступны только владельцу).
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import database as db
from config import config

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirm = State()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика бота."""
    if not is_admin(message.from_user.id):
        return

    stats = await db.get_stats()
    rate = await db.get_yuan_rate()

    text = (
        f"📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        f"👥 Всего юзеров: <b>{stats['total_users']}</b>\n"
        f"📈 Новых за день: <b>{stats['new_today']}</b>\n"
        f"📅 Новых за неделю: <b>{stats['new_week']}</b>\n\n"
        f"🎓 Прошли мини-курс: <b>{stats['course_completed']}</b>\n"
        f"💎 Купили гайд: <b>{stats['purchased_guide']}</b>\n\n"
        f"💰 Общая выручка: <b>{stats['total_revenue']:,}₽</b>\n\n"
        f"📐 Текущий курс юаня: <b>{rate}₽</b>\n\n"
        f"<i>Команды:\n"
        f"/set_rate 13.6 — обновить курс юаня\n"
        f"/broadcast — рассылка по всем юзерам\n"
        f"/user 12345 — инфа о юзере</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("set_rate"))
async def cmd_set_rate(message: Message):
    """Обновление курса юаня."""
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "Использование: <code>/set_rate 13.6</code>",
            parse_mode="HTML"
        )
        return

    try:
        rate = float(parts[1].replace(",", "."))
        if rate <= 0 or rate > 100:
            raise ValueError("invalid rate")
    except ValueError:
        await message.answer("❌ Некорректный курс. Пример: <code>/set_rate 13.6</code>", parse_mode="HTML")
        return

    await db.set_setting("yuan_rate", str(rate))
    await message.answer(f"✅ Курс юаня обновлён: <b>{rate}₽</b>", parse_mode="HTML")


@router.message(Command("user"))
async def cmd_user_info(message: Message):
    """Информация о конкретном юзере."""
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/user 12345678</code>", parse_mode="HTML")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректный ID")
        return

    user = await db.get_user(user_id)
    if not user:
        await message.answer("Юзер не найден")
        return

    text = (
        f"👤 <b>Юзер {user_id}</b>\n\n"
        f"Username: @{user.get('username') or '—'}\n"
        f"Имя: {user.get('first_name') or '—'}\n"
        f"Зарегистрирован: {user.get('joined_at')}\n"
        f"Подписан на канал: {'✅' if user.get('subscribed_to_channel') else '❌'}\n"
        f"Прогресс курса: {user.get('lesson_progress')}/5\n"
        f"Курс пройден: {'✅' if user.get('course_completed') else '❌'}\n"
        f"Купил гайд: {'✅' if user.get('purchased_guide') else '❌'}\n"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Запуск рассылки."""
    if not is_admin(message.from_user.id):
        return

    await state.set_state(BroadcastStates.waiting_for_message)
    await message.answer(
        "📢 Пришли сообщение для рассылки (можно с форматированием HTML).\n"
        "Или /cancel для отмены."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("Отменено")


@router.message(BroadcastStates.waiting_for_message)
async def broadcast_preview(message: Message, state: FSMContext):
    """Получили текст рассылки — показываем превью."""
    await state.update_data(text=message.html_text)
    await state.set_state(BroadcastStates.waiting_for_confirm)

    user_count = len(await db.get_all_user_ids())

    await message.answer(
        f"📢 <b>ПРЕВЬЮ РАССЫЛКИ</b>\n\n"
        f"Получателей: <b>{user_count}</b>\n\n"
        f"<i>Само сообщение ниже:</i>",
        parse_mode="HTML"
    )
    await message.answer(message.html_text, parse_mode="HTML")
    await message.answer(
        "Подтверди отправку: напиши <code>ОТПРАВИТЬ</code> или /cancel",
        parse_mode="HTML"
    )


@router.message(BroadcastStates.waiting_for_confirm, F.text == "ОТПРАВИТЬ")
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    """Подтверждение — рассылаем."""
    data = await state.get_data()
    text = data.get("text", "")
    await state.clear()

    user_ids = await db.get_all_user_ids()
    sent = 0
    failed = 0

    status_msg = await message.answer(f"⏳ Рассылка началась... 0/{len(user_ids)}")

    for i, uid in enumerate(user_ids, 1):
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

        # Лимит Telegram: ~30 сообщений в секунду. Делаем паузу.
        if i % 25 == 0:
            await asyncio.sleep(1)
            try:
                await status_msg.edit_text(f"⏳ Рассылка идёт... {i}/{len(user_ids)}")
            except Exception:
                pass

    await message.answer(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Отправлено: {sent}\n"
        f"Не доставлено: {failed}",
        parse_mode="HTML"
    )


@router.message(BroadcastStates.waiting_for_confirm)
async def broadcast_wrong_input(message: Message):
    """Если введено что-то кроме ОТПРАВИТЬ."""
    await message.answer("Напиши <code>ОТПРАВИТЬ</code> для подтверждения или /cancel", parse_mode="HTML")
