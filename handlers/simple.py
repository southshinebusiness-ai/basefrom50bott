"""
Выкуп и контакты. Отправляет баннер при открытии.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from db import database as db
from utils.keyboards import buyout_menu, back_to_main
from content import texts
from config import config

router = Router()
BANNER = Path("content/images/banner_buyout_final.png")


@router.callback_query(F.data == "buyout")
async def show_buyout(callback: CallbackQuery, bot: Bot, state: FSMContext):
    chat_id = callback.message.chat.id
    await db.log_event(callback.from_user.id, "view_buyout")

    # Удаляем старый баннер и текущее сообщение
    data = await state.get_data()
    old_banner = data.get("banner_msg_id")
    if old_banner:
        try:
            await bot.delete_message(chat_id, old_banner)
        except Exception:
            pass
    try:
        await bot.delete_message(chat_id, callback.message.message_id)
    except Exception:
        pass

    # Новый баннер
    banner_id = None
    if BANNER.exists():
        try:
            msg = await bot.send_photo(chat_id, FSInputFile(BANNER))
            banner_id = msg.message_id
        except Exception:
            pass
    await state.update_data(banner_msg_id=banner_id)

    await bot.send_message(
        chat_id, texts.BUYOUT_INFO,
        reply_markup=buyout_menu(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "contacts")
async def show_contacts(callback: CallbackQuery):
    await db.log_event(callback.from_user.id, "view_contacts")
    youtube = config.YOUTUBE_LINK if config.YOUTUBE_LINK else "скоро"
    tiktok  = config.TIKTOK_LINK  if config.TIKTOK_LINK  else "скоро"
    await callback.message.edit_text(
        texts.CONTACTS.format(youtube=youtube, tiktok=tiktok),
        reply_markup=back_to_main(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()
