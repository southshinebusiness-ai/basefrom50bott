"""
Админ-команды.
/stats    — полная статистика
/funnel   — воронка конверсии
/today    — сводка за сегодня
/broadcast — рассылка (текст или фото+текст)
/grant    — выдать доступ вручную
/revoke   — забрать доступ
/user     — инфо о юзере
/set_rate — курс юаня
"""
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import database as db
from config import config

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


# ── FSM ───────────────────────────────────────────────────────
class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirm = State()


# ── ВСПОМОГАТЕЛЬНЫЕ ───────────────────────────────────────────
def pct(part: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{part / total * 100:.1f}%"

def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


async def get_full_stats() -> dict:
    """Собирает расширенную статистику из БД."""
    import aiosqlite
    db_path = getattr(config, 'DB_PATH', 'data/bot.db')

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        now   = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        week  = (now - timedelta(days=7)).isoformat()
        month = (now - timedelta(days=30)).isoformat()

        async def one(sql, *args):
            cur = await conn.execute(sql, args)
            row = await cur.fetchone()
            return row[0] if row else 0

        total       = await one("SELECT COUNT(*) FROM users")
        new_today   = await one("SELECT COUNT(*) FROM users WHERE joined_at >= ?", today)
        new_week    = await one("SELECT COUNT(*) FROM users WHERE joined_at >= ?", week)
        new_month   = await one("SELECT COUNT(*) FROM users WHERE joined_at >= ?", month)

        # Воронка курса
        started     = await one("SELECT COUNT(*) FROM users WHERE lesson_progress >= 1")
        completed   = await one("SELECT COUNT(*) FROM users WHERE lesson_progress >= 5 OR course_completed = 1")
        got_pdf     = await one("SELECT COUNT(DISTINCT user_id) FROM events WHERE event_type='received_pdfs'")

        # Воронка гайда
        opened_guide  = await one("SELECT COUNT(DISTINCT user_id) FROM events WHERE event_type='view_guide'")
        payment_init  = await one("SELECT COUNT(DISTINCT user_id) FROM events WHERE event_type='payment_initiated'")
        purchased     = await one("SELECT COUNT(*) FROM users WHERE purchased_guide = 1")

        # Выручка
        rev_total = await one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='success'")
        rev_today = await one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='success' AND created_at >= ?", today)
        rev_week  = await one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='success' AND created_at >= ?", week)
        rev_month = await one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='success' AND created_at >= ?", month)

        # Активность сегодня
        active_today = await one("SELECT COUNT(DISTINCT user_id) FROM events WHERE created_at >= ?", today)

    return {
        "total": total, "new_today": new_today,
        "new_week": new_week, "new_month": new_month,
        "started": started, "completed": completed, "got_pdf": got_pdf,
        "opened_guide": opened_guide, "payment_init": payment_init, "purchased": purchased,
        "rev_total": rev_total, "rev_today": rev_today,
        "rev_week": rev_week, "rev_month": rev_month,
        "active_today": active_today,
    }


# ── /stats ────────────────────────────────────────────────────
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    s = await get_full_stats()

    text = (
        "📊 <b>СТАТИСТИКА БОТА</b>\n\n"

        "👥 <b>Пользователи</b>\n"
        f"  Всего: <b>{fmt(s['total'])}</b>\n"
        f"  Сегодня пришли: <b>+{s['new_today']}</b>\n"
        f"  За неделю: <b>+{s['new_week']}</b>\n"
        f"  За месяц: <b>+{s['new_month']}</b>\n"
        f"  Активны сегодня: <b>{s['active_today']}</b>\n\n"

        "🎓 <b>Бесплатный курс</b>\n"
        f"  Начали: <b>{s['started']}</b> ({pct(s['started'], s['total'])})\n"
        f"  Прошли: <b>{s['completed']}</b> ({pct(s['completed'], s['total'])})\n"
        f"  Получили PDF: <b>{s['got_pdf']}</b> ({pct(s['got_pdf'], s['total'])})\n\n"

        "💎 <b>ULTIMATE GUIDE</b>\n"
        f"  Открыли раздел: <b>{s['opened_guide']}</b>\n"
        f"  Начали оплату: <b>{s['payment_init']}</b>\n"
        f"  Купили: <b>{s['purchased']}</b> ({pct(s['purchased'], s['total'])})\n"
        f"  Конверсия в продажу: <b>{pct(s['purchased'], s['opened_guide'])}</b>\n\n"

        "💰 <b>Выручка</b>\n"
        f"  Сегодня: <b>{fmt(int(s['rev_today']))}₽</b>\n"
        f"  Неделя: <b>{fmt(int(s['rev_week']))}₽</b>\n"
        f"  Месяц: <b>{fmt(int(s['rev_month']))}₽</b>\n"
        f"  Всего: <b>{fmt(int(s['rev_total']))}₽</b>\n\n"

        "<i>/funnel — воронка  /today — сводка\n"
        "/broadcast — рассылка\n"
        "/grant /revoke /user ID</i>"
    )
    await message.answer(text, parse_mode="HTML")


# ── /funnel ───────────────────────────────────────────────────
@router.message(Command("funnel"))
async def cmd_funnel(message: Message):
    if not is_admin(message.from_user.id):
        return

    s = await get_full_stats()
    t = s['total'] or 1

    def bar(n, total):
        filled = int(n / total * 10) if total else 0
        return "█" * filled + "░" * (10 - filled)

    text = (
        "🔽 <b>ВОРОНКА КОНВЕРСИИ</b>\n\n"
        f"Пришли в бот\n"
        f"<code>{bar(t,t)}</code> {fmt(t)} (100%)\n\n"
        f"Начали курс\n"
        f"<code>{bar(s['started'],t)}</code> {fmt(s['started'])} ({pct(s['started'],t)})\n\n"
        f"Прошли курс\n"
        f"<code>{bar(s['completed'],t)}</code> {fmt(s['completed'])} ({pct(s['completed'],t)})\n\n"
        f"Открыли GUIDE\n"
        f"<code>{bar(s['opened_guide'],t)}</code> {fmt(s['opened_guide'])} ({pct(s['opened_guide'],t)})\n\n"
        f"Начали оплату\n"
        f"<code>{bar(s['payment_init'],t)}</code> {fmt(s['payment_init'])} ({pct(s['payment_init'],t)})\n\n"
        f"Купили 💎\n"
        f"<code>{bar(s['purchased'],t)}</code> {fmt(s['purchased'])} ({pct(s['purchased'],t)})\n\n"
        f"Конверсия (все→покупка): <b>{pct(s['purchased'],t)}</b>\n"
        f"Конверсия (гайд→покупка): <b>{pct(s['purchased'],s['opened_guide'])}</b>\n"
        f"Конверсия (курс→покупка): <b>{pct(s['purchased'],s['completed'])}</b>"
    )
    await message.answer(text, parse_mode="HTML")


# ── /today ────────────────────────────────────────────────────
@router.message(Command("today"))
async def cmd_today(message: Message):
    if not is_admin(message.from_user.id):
        return

    s = await get_full_stats()
    text = (
        f"📅 <b>СЕГОДНЯ</b>\n\n"
        f"👤 Новых пользователей: <b>+{s['new_today']}</b>\n"
        f"🔥 Активных: <b>{s['active_today']}</b>\n"
        f"💰 Выручка: <b>{fmt(int(s['rev_today']))}₽</b>\n"
        f"💎 Продаж гайда: <b>{s['purchased']}</b> всего\n"
    )
    await message.answer(text, parse_mode="HTML")


# ── /broadcast ────────────────────────────────────────────────
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastStates.waiting_for_message)
    await message.answer(
        "📢 <b>РАССЫЛКА</b>\n\n"
        "Отправь сообщение для рассылки.\n"
        "Поддерживается: текст, фото + подпись.\n\n"
        "/cancel — отмена",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Отменено")


@router.message(BroadcastStates.waiting_for_message)
async def broadcast_preview(message: Message, state: FSMContext):
    user_count = len(await db.get_all_user_ids())

    # Сохраняем тип и данные сообщения
    if message.photo:
        photo_id = message.photo[-1].file_id
        caption  = message.html_text or ""
        await state.update_data(msg_type="photo", photo_id=photo_id, caption=caption)
        preview_text = f"📸 Фото + текст\nПолучателей: <b>{user_count}</b>"
    elif message.text:
        await state.update_data(msg_type="text", text=message.html_text)
        preview_text = f"📝 Текст\nПолучателей: <b>{user_count}</b>"
    else:
        await message.answer("❌ Поддерживаются только текст и фото. Попробуй ещё раз.")
        return

    await state.set_state(BroadcastStates.waiting_for_confirm)

    # Показываем превью
    await message.answer(f"👁 <b>ПРЕВЬЮ:</b> {preview_text}", parse_mode="HTML")
    if message.photo:
        await message.answer_photo(message.photo[-1].file_id, caption=message.caption)
    else:
        await message.answer(message.html_text, parse_mode="HTML")

    # Кнопки подтверждения
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Отправить ({user_count} чел.)", callback_data="broadcast_yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_no"),
        ]
    ])
    await message.answer("Подтверди рассылку:", reply_markup=kb)


@router.callback_query(BroadcastStates.waiting_for_confirm, F.data == "broadcast_no")
async def broadcast_cancel_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена")
    await callback.answer()


@router.callback_query(BroadcastStates.waiting_for_confirm, F.data == "broadcast_yes")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data     = await state.get_data()
    msg_type = data.get("msg_type")
    await state.clear()

    user_ids   = await db.get_all_user_ids()
    sent = failed = 0
    await callback.message.edit_text(f"⏳ Рассылка... 0/{len(user_ids)}")
    await callback.answer()

    for i, uid in enumerate(user_ids, 1):
        try:
            if msg_type == "photo":
                await bot.send_photo(uid, data["photo_id"], caption=data.get("caption") or None, parse_mode="HTML")
            else:
                await bot.send_message(uid, data["text"], parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            await asyncio.sleep(1)
            try:
                await callback.message.edit_text(f"⏳ Рассылка... {i}/{len(user_ids)}")
            except Exception:
                pass

    await callback.message.answer(
        f"✅ <b>Рассылка завершена</b>\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Не доставлено: <b>{failed}</b>",
        parse_mode="HTML"
    )


# ── /grant ────────────────────────────────────────────────────
@router.message(Command("grant"))
async def cmd_grant(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/grant USER_ID</code>", parse_mode="HTML")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректный ID", parse_mode="HTML")
        return

    user = await db.get_user(target_id)
    if not user:
        await message.answer(f"❌ Юзер {target_id} не найден. Пусть сначала напишет /start.", parse_mode="HTML")
        return

    await db.mark_purchased(target_id)
    await db.log_event(target_id, "guide_granted_manually", {"by_admin": message.from_user.id})

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            creates_join_request=True,
            expire_date=datetime.now() + timedelta(days=3),
            name=f"Grant {target_id}"
        )
        await bot.send_message(
            target_id,
            "✅ <b>Тебе открыт доступ к ULTIMATE GUIDE!</b>\n\n"
            "Жми ссылку → отправь запрос → бот одобрит автоматически:\n\n"
            f"👉 {invite.invite_link}\n\n"
            "get rich or die tryin' 💀",
            parse_mode="HTML", disable_web_page_preview=True
        )
        await message.answer(f"✅ Юзер {target_id} получил доступ. Ссылка отправлена.", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка ссылки: {e}\nЮзер {target_id} отмечен в БД.", parse_mode="HTML")


# ── /revoke ───────────────────────────────────────────────────
@router.message(Command("revoke"))
async def cmd_revoke(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/revoke USER_ID</code>", parse_mode="HTML")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Некорректный ID")
        return

    try:
        await bot.ban_chat_member(config.PRIVATE_CHANNEL_ID, target_id)
        await bot.unban_chat_member(config.PRIVATE_CHANNEL_ID, target_id)
    except Exception as e:
        await message.answer(f"⚠️ Не удалось кикнуть из канала: {e}", parse_mode="HTML")

    import aiosqlite
    async with aiosqlite.connect(getattr(config, 'DB_PATH', 'data/bot.db')) as c:
        await c.execute("UPDATE users SET purchased_guide=0, purchased_at=NULL WHERE user_id=?", (target_id,))
        await c.commit()

    await message.answer(f"✅ Доступ у {target_id} отозван.", parse_mode="HTML")


# ── /user ─────────────────────────────────────────────────────
@router.message(Command("user"))
async def cmd_user_info(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: <code>/user USER_ID</code>", parse_mode="HTML")
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
        f"Зарегистрирован: {str(user.get('joined_at','—'))[:16]}\n"
        f"Подписан на канал: {'✅' if user.get('subscribed_to_channel') else '❌'}\n"
        f"Прогресс курса: {user.get('lesson_progress', 0)}/5\n"
        f"Курс пройден: {'✅' if user.get('course_completed') else '❌'}\n"
        f"Купил гайд: {'✅' if user.get('purchased_guide') else '❌'}\n"
    )
    await message.answer(text, parse_mode="HTML")


# ── /set_rate ─────────────────────────────────────────────────
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
        await message.answer("❌ Некорректный курс.")
        return
    await db.set_setting("yuan_rate", str(rate))
    await message.answer(f"✅ Курс юаня: <b>{rate}₽</b>", parse_mode="HTML")
