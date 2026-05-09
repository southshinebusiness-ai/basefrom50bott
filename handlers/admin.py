"""
Админ-команды. Правка #5: добавлена /grant для ручной выдачи доступа.
"""
import asyncio
from datetime import datetime, timedelta
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
        f"📐 Курс юаня: <b>{rate}₽</b>\n\n"
        f"<i>Команды:\n"
        f"/set_rate 13.6 — обновить курс юаня\n"
        f"/grant USER_ID — выдать доступ к гайду вручную\n"
        f"/user USER_ID — инфа о юзере\n"
        f"/broadcast — рассылка</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("set_rate"))
async def cmd_set_rate(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/set_rate 13.6</code>", parse_mode="HTML")
        return
    try:
        rate = float(parts[1].replace(",", "."))
        if rate <= 0 or rate > 100:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Некорректный курс.", parse_mode="HTML")
        return
    await db.set_setting("yuan_rate", str(rate))
    await message.answer(f"✅ Курс юаня обновлён: <b>{rate}₽</b>", parse_mode="HTML")


@router.message(Command("grant"))
async def cmd_grant(message: Message, bot: Bot):
    """
    Правка #5: ручная выдача доступа к гайду.
    Использование: /grant USER_ID
    Например: /grant 128529278
    """
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "Использование: <code>/grant USER_ID</code>\n"
            "Например: <code>/grant 128529278</code>",
            parse_mode="HTML"
        )
        return

    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректный ID пользователя.", parse_mode="HTML")
        return

    user = await db.get_user(target_user_id)
    if not user:
        await message.answer(f"❌ Пользователь {target_user_id} не найден в БД.", parse_mode="HTML")
        return

    # Отмечаем как купившего
    await db.mark_purchased(target_user_id)
    await db.log_event(target_user_id, "guide_granted_manually", {"by_admin": message.from_user.id})

    # Создаём инвайт-ссылку
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(days=7),
            name=f"Grant for {target_user_id}"
        )
        invite_link = invite.invite_link

        # Отправляем ссылку пользователю
        await bot.send_message(
            target_user_id,
            f"✅ <b>Доступ к ULTIMATE GUIDE открыт!</b>\n\n"
            f"Вот твой персональный доступ к закрытому каналу:\n\n"
            f"👉 {invite_link}\n\n"
            f"Внутри: гайд, база поставщиков, бонусы.\n\n"
            f"get rich or die tryin' 💀",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        await message.answer(
            f"✅ Доступ выдан пользователю {target_user_id}\n"
            f"Ссылка отправлена: {invite_link}",
            disable_web_page_preview=True
        )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка создания ссылки: {e}\n\n"
            f"Добавь пользователя {target_user_id} в канал вручную.",
            parse_mode="HTML"
        )


@router.message(Command("user"))
async def cmd_user_info(message: Message):
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
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastStates.waiting_for_message)
    await message.answer(
        "📢 Пришли сообщение для рассылки.\nИли /cancel для отмены."
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("Отменено")


@router.message(BroadcastStates.waiting_for_message)
async def broadcast_preview(message: Message, state: FSMContext):
    await state.update_data(text=message.html_text)
    await state.set_state(BroadcastStates.waiting_for_confirm)
    user_count = len(await db.get_all_user_ids())
    await message.answer(
        f"📢 <b>ПРЕВЬЮ</b> — получателей: <b>{user_count}</b>",
        parse_mode="HTML"
    )
    await message.answer(message.html_text, parse_mode="HTML")
    await message.answer("Напиши <code>ОТПРАВИТЬ</code> или /cancel", parse_mode="HTML")


@router.message(BroadcastStates.waiting_for_confirm, F.text == "ОТПРАВИТЬ")
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data.get("text", "")
    await state.clear()
    user_ids = await db.get_all_user_ids()
    sent = failed = 0
    status_msg = await message.answer(f"⏳ Рассылка... 0/{len(user_ids)}")
    for i, uid in enumerate(user_ids, 1):
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            await asyncio.sleep(1)
            try:
                await status_msg.edit_text(f"⏳ Рассылка... {i}/{len(user_ids)}")
            except Exception:
                pass
    await message.answer(
        f"✅ <b>Готово</b>\nОтправлено: {sent}\nНе доставлено: {failed}",
        parse_mode="HTML"
    )


@router.message(BroadcastStates.waiting_for_confirm)
async def broadcast_wrong(message: Message):
    await message.answer("Напиши <code>ОТПРАВИТЬ</code> или /cancel", parse_mode="HTML")
