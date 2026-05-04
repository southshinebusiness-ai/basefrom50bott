"""
Раздел "Старт с РФ" — бесплатный мини-курс с лид-магнитом.
Перед выдачей материалов — проверка подписки на канал.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile

from db import database as db
from utils.keyboards import (
    start_course, next_lesson, finish_course, check_subscription, back_to_main
)
from utils.helpers import is_subscribed_to_channel
from content import texts

router = Router()


@router.callback_query(F.data == "start_rf")
async def show_start_rf(callback: CallbackQuery, bot: Bot):
    """Старт раздела — проверка подписки и показ интро."""
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
    """Юзер нажал 'Я подписался' — проверяем заново."""
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
            "Не вижу твою подписку. Подпишись на канал и жми снова.",
            show_alert=True
        )


# ============ УРОКИ ============

LESSON_TEXTS = {
    1: texts.LESSON_1,
    2: texts.LESSON_2,
    3: texts.LESSON_3,
    4: texts.LESSON_4,
    5: texts.LESSON_5,
}


@router.callback_query(F.data.startswith("lesson_"))
async def show_lesson(callback: CallbackQuery):
    """Показывает урок по номеру."""
    user_id = callback.from_user.id
    lesson_num = int(callback.data.split("_")[1])

    if lesson_num not in LESSON_TEXTS:
        await callback.answer("Урок не найден", show_alert=True)
        return

    await db.update_lesson_progress(user_id, lesson_num)
    await db.log_event(user_id, "view_lesson", {"lesson": lesson_num})

    text = LESSON_TEXTS[lesson_num]

    if lesson_num < 5:
        keyboard = next_lesson(lesson_num)
    else:
        # Последний урок — после него финал курса
        keyboard = finish_course()

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "get_pdfs")
async def send_pdfs(callback: CallbackQuery):
    """Отправляет финальные PDF после прохождения курса."""
    user_id = callback.from_user.id
    await db.log_event(user_id, "received_pdfs")

    pdf_dir = Path("content/pdfs")
    suppliers_pdf = pdf_dir / "suppliers_rf.pdf"
    course_pdf = pdf_dir / "course_full.pdf"

    if suppliers_pdf.exists():
        await callback.message.answer_document(
            FSInputFile(suppliers_pdf),
            caption="📥 База РФ поставщиков"
        )
    else:
        await callback.message.answer(
            "📥 База РФ поставщиков скоро будет загружена. Пиши @mmarsellus если срочно нужно."
        )

    if course_pdf.exists():
        await callback.message.answer_document(
            FSInputFile(course_pdf),
            caption="📥 Полный мини-курс одним файлом"
        )

    await callback.message.answer(
        texts.COURSE_FINISH,
        reply_markup=finish_course(),
        parse_mode="HTML"
    )
    await callback.answer("PDF отправлены ✅")
