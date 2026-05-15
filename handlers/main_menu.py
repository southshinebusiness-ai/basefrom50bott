"""
Главное меню. Отправляет баннер при открытии.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from db import database as db
from utils.keyboards import main_menu
from content import texts

router = Router()
BANNER = Path("content/images/banner_menu_final.png")


async def _send_menu(bot: Bot, chat_id: int, state: FSMContext):
    """Удаляет все баннеры (menu, calc, buyout), шлёт новый + меню."""
    data = await state.get_data()
    # Удаляем все возможные баннеры из разных разделов
    for key in ("banner_msg_id", "calc_banner_id"):
        bid = data.get(key)
        if bid:
            try:
                await bot.delete_message(chat_id, bid)
            except Exception:
                pass

    banner_id = None
    if BANNER.exists():
        try:
            msg = await bot.send_photo(chat_id, FSInputFile(BANNER))
            banner_id = msg.message_id
        except Exception:
            pass

    await state.update_data(banner_msg_id=banner_id)
    await bot.send_message(
        chat_id, texts.WELCOME,
        reply_markup=main_menu(), parse_mode="HTML"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or ""
    )
    await db.log_event(message.from_user.id, "start")
    await _send_menu(bot, message.chat.id, state)


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext, bot: Bot):
    chat_id = callback.message.chat.id
    # Удаляем текущее сообщение (текстовое)
    try:
        await bot.delete_message(chat_id, callback.message.message_id)
    except Exception:
        pass
    await _send_menu(bot, chat_id, state)
    await callback.answer()
