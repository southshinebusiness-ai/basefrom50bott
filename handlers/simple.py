"""
Хендлеры выкупа и контактов. Правки #13, #14.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from db import database as db
from utils.keyboards import buyout_menu, back_to_main
from content import texts
from config import config

router = Router()


@router.callback_query(F.data == "buyout")
async def show_buyout(callback: CallbackQuery):
    """Правки #13 (новый текст) и #14 (кнопка Сделать заказ)."""
    await db.log_event(callback.from_user.id, "view_buyout")
    await callback.message.edit_text(
        texts.BUYOUT_INFO,
        reply_markup=buyout_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "contacts")
async def show_contacts(callback: CallbackQuery):
    await db.log_event(callback.from_user.id, "view_contacts")

    youtube = config.YOUTUBE_LINK if config.YOUTUBE_LINK else "скоро"
    tiktok = config.TIKTOK_LINK if config.TIKTOK_LINK else "скоро"

    await callback.message.edit_text(
        texts.CONTACTS.format(youtube=youtube, tiktok=tiktok),
        reply_markup=back_to_main(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()
