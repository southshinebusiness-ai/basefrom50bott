"""
Раздел "Старт с РФ" — мини-курс с баннерами и лид-магнитом.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import database as db
from utils.keyboards import (
    start_course, lesson_nav, finish_course, check_subscription
)
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


async def delete_old_messages(bot: Bot, chat_id: int, state: FSMContext, text_msg_id: int):
    """Удаляет текстовое сообщение и сохранённое фото."""
    data = await state.get_data()

    # Удаляем предыдущий баннер
    prev_banner_id = data.get("banner_msg_id")
    if prev_banner_id:
        try:
            await bot.delete_message(chat_id, prev_banner_id)
        except Exception:
            pass

    # Удаляем текстовое сообщение
    try:
        await bot.delete_message(chat_id, text_msg_id)
    except Exception:
        pass


async def send_lesson(bot: Bot, chat_id: int, state: FSMContext, lesson_num: int):
    """Отправляет баннер + текст урока. chat_id сохраняется заранее."""

    # Баннер
    banner_file = LESSON_BANNERS.get(lesson_num)
    if banner_file:
        banner_path = IMAGES_DIR / banner_file
        if banner_path.exists():
            try:
                msg = await bot.send_photo(chat_id, FSInputFile(banner_path))
                await state.update_data(banner_msg_id=msg.message_id)
            except Exception:
                await state.update_data(banner_msg_id=None)
        else:
            await state.update_data(banner_msg_id=None)

    # Текст с кнопками — через bot.send_message напрямую
    await bot.send_message(
        chat_id,
        LESSON_TEXTS[lesson_num],
        reply_markup=lesson_nav(lesson_num, TOTAL_LESSONS),
        parse_mode="HTML"
    )


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
            reply_markup=check_subscription(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await delete_old_messages(bot, chat_id, state, callback.message.message_id)
    await state.set_state(CourseState.viewing)

    # Баннер интро
    banner_path = IMAGES_DIR / LESSON_BANNERS[0]
    if banner_path.exists():
        try:
            msg = await bot.send_photo(chat_id, FSInputFile(banner_path))
            await state.update_data(banner_msg_id=msg.message_id)
        except Exception:
            await state.update_data(banner_msg_id=None)

    await bot.send_message(
        chat_id,
        texts.START_RF_INTRO,
        reply_markup=start_course(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_sub")
async def recheck_subscription(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    is_subbed = await is_subscribed_to_channel(bot, user_id)
    await db.set_subscription_status(user_id, is_subbed)

    if is_subbed:
        await callback.answer(texts.SUBSCRIPTION_CONFIRMED, show_alert=True)
        await delete_old_messages(bot, chat_id, state, callback.message.message_id)

        banner_path = IMAGES_DIR / LESSON_BANNERS[0]
        if banner_path.exists():
            try:
                msg = await bot.send_photo(chat_id, FSInputFile(banner_path))
                await state.update_data(banner_msg_id=msg.message_id)
            except Exception:
                pass

        await bot.send_message(
            chat_id,
            texts.START_RF_INTRO,
            reply_markup=start_course(),
            parse_mode="HTML"
        )
    else:
        await callback.answer(
            "Не вижу твою подписку. Подпишись и жми снова.",
            show_alert=True
        )


@router.callback_query(F.data.startswith("lesson_"))
async def show_lesson(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Сохраняем chat_id ДО удаления, потом шлём через bot.send_message напрямую."""
    user_id    = callback.from_user.id
    chat_id    = callback.message.chat.id          # ← сохраняем до удаления
    msg_id     = callback.message.message_id
    lesson_num = int(callback.data.split("_")[1])

    if lesson_num not in LESSON_TEXTS:
        await callback.answer("Урок не найден", show_alert=True)
        return

    await db.update_lesson_progress(user_id, lesson_num)
    await db.log_event(user_id, "view_lesson", {"lesson": lesson_num})

    # Удаляем старые сообщения
    await delete_old_messages(bot, chat_id, state, msg_id)

    # Отправляем новый урок
    await send_lesson(bot, chat_id, state, lesson_num)

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
            chat_id,
            FSInputFile(pdf_path),
            caption=(
                "📥 <b>База поставщиков РФ — Легкий старт</b>\n\n"
                "Сохрани документ — все ссылки кликабельные."
            ),
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            chat_id,
            "📥 <b>База РФ поставщиков</b> скоро будет загружена.\n"
            "Пиши @mmarsellus если нужна срочно.",
            parse_mode="HTML"
        )

    await bot.send_message(
        chat_id,
        texts.COURSE_FINISH,
        reply_markup=finish_course(),
        parse_mode="HTML"
    )
    await callback.answer("PDF отправлен ✅")
