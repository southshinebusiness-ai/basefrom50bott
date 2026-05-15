"""
Раздел "Старт с РФ" — мини-курс с баннерами и лид-магнитом.
Все кнопки inline — не зависит от keyboards.py.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import database as db
from utils.helpers import is_subscribed_to_channel
from content import texts

router = Router()
TOTAL_LESSONS = 5
IMAGES_DIR    = Path("content/images")
PDFS_DIR      = Path("content/pdfs")

LESSON_BANNERS = {
    0: "banner_main_final.png",
    1: "banner_01_final.png",
    2: "banner_02_final.png",
    3: "banner_03_final.png",
    4: "banner_04_final.png",
    5: "banner_05_final.png",
}

LESSON_TEXTS = {
    1: texts.LESSON_1,
    2: texts.LESSON_2,
    3: texts.LESSON_3,
    4: texts.LESSON_4,
    5: texts.LESSON_5,
}


class CourseState(StatesGroup):
    viewing = State()


# ── КЛАВИАТУРЫ (inline, без зависимостей от keyboards.py) ─────

def kb_start_course() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Начать урок 1", callback_data="lesson_1")],
        [InlineKeyboardButton(text="⬅️ Главное меню",  callback_data="main_menu")],
    ])

def kb_check_sub() -> InlineKeyboardMarkup:
    from config import config
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Перейти на канал", url=f"https://t.me/{config.MAIN_CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="✅ Я подписался",    callback_data="check_sub")],
        [InlineKeyboardButton(text="⬅️ Главное меню",   callback_data="main_menu")],
    ])

def kb_lesson(lesson_num: int) -> InlineKeyboardMarkup:
    rows = []
    if lesson_num < TOTAL_LESSONS:
        nav = []
        if lesson_num > 1:
            nav.append(InlineKeyboardButton(text="← Назад", callback_data=f"lesson_{lesson_num - 1}"))
        nav.append(InlineKeyboardButton(text="Дальше →", callback_data=f"lesson_{lesson_num + 1}"))
        rows.append(nav)
    else:
        # Последний урок
        rows.append([InlineKeyboardButton(text="← Назад",            callback_data=f"lesson_{lesson_num - 1}")])
        rows.append([InlineKeyboardButton(text="📥 Получить PDF",     callback_data="get_pdfs")])
        rows.append([InlineKeyboardButton(text="💎 ULTIMATE GUIDE",   callback_data="guide")])
    rows.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_finish() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Получить PDF",   callback_data="get_pdfs")],
        [InlineKeyboardButton(text="💎 ULTIMATE GUIDE", callback_data="guide")],
        [InlineKeyboardButton(text="⬅️ Главное меню",  callback_data="main_menu")],
    ])


# ── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ───────────────────────────────────

async def delete_old_messages(bot: Bot, chat_id: int, state: FSMContext, text_msg_id: int):
    data = await state.get_data()
    prev_banner_id = data.get("banner_msg_id")
    if prev_banner_id:
        try:
            await bot.delete_message(chat_id, prev_banner_id)
        except Exception:
            pass
    try:
        await bot.delete_message(chat_id, text_msg_id)
    except Exception:
        pass


async def send_banner(bot: Bot, chat_id: int, state: FSMContext, lesson_num: int):
    banner_file = LESSON_BANNERS.get(lesson_num)
    if not banner_file:
        return
    banner_path = IMAGES_DIR / banner_file
    if not banner_path.exists():
        return
    try:
        msg = await bot.send_photo(chat_id, FSInputFile(banner_path))
        await state.update_data(banner_msg_id=msg.message_id)
    except Exception:
        await state.update_data(banner_msg_id=None)


# ── ХЕНДЛЕРЫ ─────────────────────────────────────────────────

@router.callback_query(F.data == "start_rf")
async def show_start_rf(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    await db.log_event(user_id, "open_start_rf")

    is_subbed = await is_subscribed_to_channel(bot, user_id)
    await db.set_subscription_status(user_id, is_subbed)

    if not is_subbed:
        await callback.message.edit_text(
            texts.NOT_SUBSCRIBED,
            reply_markup=kb_check_sub(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await delete_old_messages(bot, chat_id, state, callback.message.message_id)
    await state.set_state(CourseState.viewing)
    await send_banner(bot, chat_id, state, 0)
    await bot.send_message(chat_id, texts.START_RF_INTRO, reply_markup=kb_start_course(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "check_sub")
async def recheck_subscription(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id   = callback.from_user.id
    chat_id   = callback.message.chat.id
    is_subbed = await is_subscribed_to_channel(bot, user_id)
    await db.set_subscription_status(user_id, is_subbed)

    if is_subbed:
        await callback.answer(texts.SUBSCRIPTION_CONFIRMED, show_alert=True)
        await delete_old_messages(bot, chat_id, state, callback.message.message_id)
        await send_banner(bot, chat_id, state, 0)
        await bot.send_message(chat_id, texts.START_RF_INTRO, reply_markup=kb_start_course(), parse_mode="HTML")
    else:
        await callback.answer("Не вижу твою подписку. Подпишись и жми снова.", show_alert=True)


@router.callback_query(F.data.startswith("lesson_"))
async def show_lesson(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id    = callback.from_user.id
    chat_id    = callback.message.chat.id
    msg_id     = callback.message.message_id
    lesson_num = int(callback.data.split("_")[1])

    if lesson_num not in LESSON_TEXTS:
        await callback.answer("Урок не найден", show_alert=True)
        return

    await db.update_lesson_progress(user_id, lesson_num)
    await db.log_event(user_id, "view_lesson", {"lesson": lesson_num})

    await delete_old_messages(bot, chat_id, state, msg_id)
    await send_banner(bot, chat_id, state, lesson_num)

    try:
        await bot.send_message(
            chat_id,
            LESSON_TEXTS[lesson_num],
            reply_markup=kb_lesson(lesson_num),
            parse_mode="HTML"
        )
    except Exception as e:
        try:
            await bot.send_message(
                chat_id,
                LESSON_TEXTS[lesson_num],
                reply_markup=kb_lesson(lesson_num),
            )
        except Exception:
            await bot.send_message(chat_id, f"Ошибка загрузки урока {lesson_num}. Пиши @mmarsellus")
        from config import config
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"❌ Ошибка урок {lesson_num}:\n{str(e)[:500]}",
            )
        except Exception:
            pass

    await callback.answer()


@router.callback_query(F.data == "get_pdfs")
async def send_pdfs(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    msg_id  = callback.message.message_id
    await db.log_event(user_id, "received_pdfs")

    await delete_old_messages(bot, chat_id, state, msg_id)
    await state.clear()

    pdf_path = PDFS_DIR / "basefrom50_start_rf.pdf"
    if pdf_path.exists():
        await bot.send_document(
            chat_id, FSInputFile(pdf_path),
            caption="📥 <b>База поставщиков РФ — Легкий старт</b>\n\nСохрани — все ссылки кликабельные.",
            parse_mode="HTML"
        )
    else:
        await bot.send_message(chat_id, "📥 База скоро будет загружена. Пиши @mmarsellus.", parse_mode="HTML")

    await bot.send_message(chat_id, texts.COURSE_FINISH, reply_markup=kb_finish(), parse_mode="HTML")
    await callback.answer("PDF отправлен ✅")
