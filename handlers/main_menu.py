"""
Хендлер главного меню. Правка #1: новый текст и кнопки.
"""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from db import database as db
from utils.keyboards import main_menu
from content import texts

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or ""
    )
    await db.log_event(message.from_user.id, "start")

    await message.answer(
        texts.WELCOME,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        texts.WELCOME,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()
