"""Бесплатный гайд — мгновенная выдача PDF без мини-курса."""
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from db import database as db
from config import config

router = Router()
PDF_PATH = Path("content/pdfs/basefrom50_free_guide.pdf")


def after_guide_menu() -> InlineKeyboardMarkup:
    """Следующий шаг после выдачи бесплатного гайда."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 ULTIMATE GUIDE", callback_data="guide")],
        [InlineKeyboardButton(text="📲 Основной канал", url=config.MAIN_CHANNEL_LINK)],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")],
    ])


async def _send_free_guide(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    await db.log_event(user_id, "free_guide_opened")

    # Удаляем старый баннер и сообщение меню, чтобы выдача выглядела чисто.
    data = await state.get_data()
    for key in ("banner_msg_id", "calc_banner_id"):
        msg_id = data.get(key)
        if msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()

    if not PDF_PATH.exists():
        await bot.send_message(
            chat_id,
            "Не удалось загрузить бесплатный гайд. Попробуй чуть позже.",
        )
        await db.log_event(user_id, "free_guide_missing")
        await callback.answer()
        return

    await bot.send_document(
        chat_id,
        FSInputFile(PDF_PATH),
        caption=(
            "📖 <b>Бесплатный гайд BASE FROM 50</b>\n\n"
            "Как покупать вещи из Китая напрямую — без российских посредников и лишней наценки.\n\n"
            "Сохрани файл: внутри ссылки и кнопка перехода в ULTIMATE кликабельны."
        ),
        parse_mode="HTML",
    )
    await db.log_event(user_id, "free_guide_sent")

    await bot.send_message(
        chat_id,
        "Гайд у тебя ✅\n\n"
        "Если хочешь не просто понять принцип, а получить готовую систему — "
        "поставщиков, площадки, доставку, калькуляторы и материалы — открой <b>ULTIMATE GUIDE</b>.",
        reply_markup=after_guide_menu(),
        parse_mode="HTML",
    )
    await callback.answer("Гайд отправлен ✅")


@router.callback_query(F.data == "free_guide")
async def send_free_guide(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await _send_free_guide(callback, bot, state)


# Совместимость со старыми сообщениями бота:
# прежняя кнопка "start_rf" теперь тоже сразу выдаёт новый бесплатный гайд.
@router.callback_query(F.data == "start_rf")
async def legacy_start_rf(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await _send_free_guide(callback, bot, state)
