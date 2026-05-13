"""
Раздел "Старт с РФ" — мини-курс с лид-магнитом.
Правки #1 (кнопка назад в уроках), #4 (удаление сообщений после курса).
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile

from db import database as db
from utils.keyboards import (
    start_course, lesson_nav, finish_course, check_subscription, back_to_main
)
from utils.helpers import is_subscribed_to_channel
from content import texts

router = Router()
TOTAL_LESSONS = 5


@router.callback_query(F.data == "start_rf")
async def show_start_rf(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    await db.log_event(user_id, "open_start_rf")

    is_subbed = await is_subscribed_to_channel(bot, user_id)
    await db.set_subscription_status(user_id, is_subbed)

    if not is_subbed:
        from config import config
        await callback.message.edit_text(
            texts.NOT_SUBSCRIBED.format(channel_link=f"@{config.MAIN_CHANNEL_USERNAME}"),
            reply_markup=check_subscription(),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        texts.START_RF_INTRO,
        reply_markup=start_course(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_sub")
async def recheck_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    is_subbed = await is_subscribed_to_channel(bot, user_id)
    await db.set_subscription_status(user_id, is_subbed)

    if is_subbed:
        await callback.answer(texts.SUBSCRIPTION_CONFIRMED, show_alert=True)
        await callback.message.edit_text(
            texts.START_RF_INTRO,
            reply_markup=start_course(),
            parse_mode="HTML"
        )
    else:
        await callback.answer(
            "Не вижу твою подписку. Подпишись и жми снова.",
            show_alert=True
        )


LESSON_TEXTS = {
    1: texts.LESSON_1,
    2: texts.LESSON_2,
    3: texts.LESSON_3,
    4: texts.LESSON_4,
    5: texts.LESSON_5,
}


@router.callback_query(F.data.startswith("lesson_"))
async def show_lesson(callback: CallbackQuery):
    """Навигация вперёд И назад по урокам."""
    user_id = callback.from_user.id
    lesson_num = int(callback.data.split("_")[1])

    if lesson_num not in LESSON_TEXTS:
        await callback.answer("Урок не найден", show_alert=True)
        return

    await db.update_lesson_progress(user_id, lesson_num)
    await db.log_event(user_id, "view_lesson", {"lesson": lesson_num})

    keyboard = lesson_nav(lesson_num, TOTAL_LESSONS)
    await callback.message.edit_text(
        LESSON_TEXTS[lesson_num],
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "get_pdfs")
async def send_pdfs(callback: CallbackQuery):
    """Отправляет PDF после прохождения курса."""
    user_id = callback.from_user.id
    await db.log_event(user_id, "received_pdfs")

    # Удаляем сообщение с кнопкой
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Отправляем PDF с базой поставщиков
    pdf_path = Path("content/pdfs/basefrom50_start_rf.pdf")

    if pdf_path.exists():
        await callback.message.answer_document(
            FSInputFile(pdf_path),
            caption=(
                "📥 <b>База поставщиков РФ — Легкий старт</b>\n\n"
                "Сохрани документ себе — все ссылки кликабельные."
            ),
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            "📥 <b>База РФ поставщиков</b> скоро будет загружена.\n"
            "Пиши @mmarsellus если нужна срочно.",
            parse_mode="HTML"
        )

    # Финальное сообщение
    from utils.keyboards import finish_course
    await callback.message.answer(
        texts.COURSE_FINISH,
        reply_markup=finish_course(),
        parse_mode="HTML"
    )

    await callback.answer("PDF отправлен ✅")
