"""
Раздел "Старт с РФ" — мини-курс с баннерами и лид-магнитом.
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

IMAGES_DIR = Path("content/images")
PDFS_DIR   = Path("content/pdfs")

LESSON_BANNERS = {
    0: "banner_main_final.png",   # интро
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


async def send_banner(callback: CallbackQuery, lesson_num: int):
    """Отправляет баннер перед уроком если файл существует."""
    banner_file = LESSON_BANNERS.get(lesson_num)
    if not banner_file:
        return
    banner_path = IMAGES_DIR / banner_file
    if banner_path.exists():
        await callback.message.answer_photo(FSInputFile(banner_path))


@router.callback_query(F.data == "start_rf")
async def show_start_rf(callback: CallbackQuery, bot: Bot):
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

    # Удаляем старое сообщение и отправляем баннер + текст
    try:
        await callback.message.delete()
    except Exception:
        pass

    await send_banner(callback, 0)
    await callback.message.answer(
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
        try:
            await callback.message.delete()
        except Exception:
            pass
        await send_banner(callback, 0)
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
async def show_lesson(callback: CallbackQuery):
    """Удаляет старое сообщение, отправляет баннер + текст урока."""
    user_id    = callback.from_user.id
    lesson_num = int(callback.data.split("_")[1])

    if lesson_num not in LESSON_TEXTS:
        await callback.answer("Урок не найден", show_alert=True)
        return

    await db.update_lesson_progress(user_id, lesson_num)
    await db.log_event(user_id, "view_lesson", {"lesson": lesson_num})

    # Удаляем предыдущее сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Баннер
    await send_banner(callback, lesson_num)

    # Текст урока с кнопками
    await callback.message.answer(
        LESSON_TEXTS[lesson_num],
        reply_markup=lesson_nav(lesson_num, TOTAL_LESSONS),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "get_pdfs")
async def send_pdfs(callback: CallbackQuery):
    """Отправляет PDF после прохождения курса."""
    user_id = callback.from_user.id
    await db.log_event(user_id, "received_pdfs")

    try:
        await callback.message.delete()
    except Exception:
        pass

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

    from utils.keyboards import finish_course
    await callback.message.answer(
        texts.COURSE_FINISH,
        reply_markup=finish_course(),
        parse_mode="HTML"
    )
    await callback.answer("PDF отправлен ✅")
