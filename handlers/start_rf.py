"""
Раздел "Старт с РФ" — мини-курс с баннерами и лид-магнитом.
Фиксы: удаление фото при переходе, блокер на уроке 5.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile, Message
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


async def delete_previous_messages(callback: CallbackQuery, state: FSMContext):
    """Удаляет текстовое сообщение и предыдущее фото (если было)."""
    data = await state.get_data()

    # Удаляем баннер предыдущего урока
    prev_banner_id = data.get("banner_msg_id")
    if prev_banner_id:
        try:
            await callback.bot.delete_message(
                callback.message.chat.id, prev_banner_id
            )
        except Exception:
            pass

    # Удаляем текстовое сообщение с кнопками
    try:
        await callback.message.delete()
    except Exception:
        pass


async def send_banner(callback: CallbackQuery, state: FSMContext, lesson_num: int):
    """Отправляет баннер и сохраняет его ID в state."""
    banner_file = LESSON_BANNERS.get(lesson_num)
    if not banner_file:
        await state.update_data(banner_msg_id=None)
        return

    banner_path = IMAGES_DIR / banner_file
    if not banner_path.exists():
        await state.update_data(banner_msg_id=None)
        return

    try:
        msg = await callback.message.answer_photo(FSInputFile(banner_path))
        await state.update_data(banner_msg_id=msg.message_id)
    except Exception:
        await state.update_data(banner_msg_id=None)


@router.callback_query(F.data == "start_rf")
async def show_start_rf(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    await db.log_event(user_id, "open_start_rf")

    is_subbed = await is_subscribed_to_channel(bot, user_id)
    await db.set_subscription_status(user_id, is_subbed)

    if not is_subbed:
        from config import config
        await callback.message.edit_text(
            texts.NOT_SUBSCRIBED,
            reply_markup=check_subscription(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await delete_previous_messages(callback, state)
    await state.set_state(CourseState.viewing)

    await send_banner(callback, state, 0)
    await callback.message.answer(
        texts.START_RF_INTRO,
        reply_markup=start_course(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_sub")
async def recheck_subscription(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id   = callback.from_user.id
    is_subbed = await is_subscribed_to_channel(bot, user_id)
    await db.set_subscription_status(user_id, is_subbed)

    if is_subbed:
        await callback.answer(texts.SUBSCRIPTION_CONFIRMED, show_alert=True)
        await delete_previous_messages(callback, state)
        await send_banner(callback, state, 0)
        await callback.message.answer(
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
async def show_lesson(callback: CallbackQuery, state: FSMContext):
    """Переход между уроками — удаляет старые сообщения, шлёт баннер + текст."""
    user_id    = callback.from_user.id
    lesson_num = int(callback.data.split("_")[1])

    if lesson_num not in LESSON_TEXTS:
        await callback.answer("Урок не найден", show_alert=True)
        return

    await db.update_lesson_progress(user_id, lesson_num)
    await db.log_event(user_id, "view_lesson", {"lesson": lesson_num})

    # Удаляем фото и текст предыдущего урока
    await delete_previous_messages(callback, state)

    # Баннер нового урока
    await send_banner(callback, state, lesson_num)

    # Текст с кнопками
    try:
        await callback.message.answer(
            LESSON_TEXTS[lesson_num],
            reply_markup=lesson_nav(lesson_num, TOTAL_LESSONS),
            parse_mode="HTML"
        )
    except Exception as e:
        await db.log_event(user_id, "lesson_send_error", {"lesson": lesson_num, "error": str(e)})
        await callback.message.answer(
            LESSON_TEXTS[lesson_num],
            reply_markup=lesson_nav(lesson_num, TOTAL_LESSONS),
        )

    await callback.answer()


@router.callback_query(F.data == "get_pdfs")
async def send_pdfs(callback: CallbackQuery, state: FSMContext):
    """Отправляет PDF после прохождения курса."""
    user_id = callback.from_user.id
    await db.log_event(user_id, "received_pdfs")

    await delete_previous_messages(callback, state)
    await state.clear()

    pdf_path = PDFS_DIR / "basefrom50_start_rf.pdf"
    if pdf_path.exists():
        await callback.message.answer_document(
            FSInputFile(pdf_path),
            caption=(
                "📥 <b>База поставщиков РФ — Легкий старт</b>\n\n"
                "Сохрани документ — все ссылки кликабельные."
            ),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            "📥 <b>База РФ поставщиков</b> скоро будет загружена.\n"
            "Пиши @mmarsellus если нужна срочно.",
            parse_mode="HTML"
        )

    await callback.message.answer(
        texts.COURSE_FINISH,
        reply_markup=finish_course(),
        parse_mode="HTML"
    )
    await callback.answer("PDF отправлен ✅")
