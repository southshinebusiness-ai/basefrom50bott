"""
Раздел ULTIMATE GUIDE.
Оплата проверяется через YooMoney webhook (автоматически).
Кнопка "Я оплатил" как резервный вариант для редких случаев задержки.
"""
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db import database as db
from utils.keyboards import guide_menu, payment_buttons, back_to_main, main_menu
from utils.helpers import generate_payment_label, generate_yoomoney_link
from content import texts
from config import config

router = Router()


async def create_secure_invite(bot: Bot, user_id: int) -> str | None:
    """Создаёт invite-ссылку с запросом на вступление."""
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            creates_join_request=True,
            expire_date=datetime.now() + timedelta(days=3),
            name=f"User {user_id}"
        )
        return invite.invite_link
    except Exception as e:
        await db.log_event(user_id, "invite_link_error", {"error": str(e)})
        return None


@router.callback_query(F.data == "guide")
async def show_guide(callback: CallbackQuery):
    await db.log_event(callback.from_user.id, "view_guide")
    await callback.message.edit_text(
        texts.GUIDE_DESCRIPTION,
        reply_markup=guide_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "guide_buy")
async def initiate_payment(callback: CallbackQuery):
    """Создаёт платёж и показывает кнопку оплаты."""
    user_id = callback.from_user.id

    user = await db.get_user(user_id)
    if user and user.get("purchased_guide"):
        await callback.answer(
            "Ты уже купил гайд! Если потерял доступ — пиши @mmarsellus.",
            show_alert=True
        )
        return

    label = generate_payment_label(user_id)
    await db.create_payment(
        user_id=user_id,
        amount=config.PRICE_ULTIMATE_GUIDE,
        product="ultimate_guide",
        label=label
    )
    await db.log_event(user_id, "payment_initiated", {
        "label": label, "amount": config.PRICE_ULTIMATE_GUIDE
    })
    await db.set_setting(f"last_label_{user_id}", label)

    pay_url = generate_yoomoney_link(
        amount=config.PRICE_ULTIMATE_GUIDE,
        label=label,
        wallet=config.YOOMONEY_WALLET
    )

    await callback.message.edit_text(
        texts.GUIDE_BUY,
        reply_markup=payment_buttons(pay_url),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery, bot: Bot):
    """
    Резервная проверка по кнопке 'Я оплатил'.
    В норме webhook уже должен был выдать доступ автоматически.
    """
    user_id = callback.from_user.id

    await callback.answer()

    # Проверяем — может webhook уже обработал платёж
    user = await db.get_user(user_id)
    if user and user.get("purchased_guide"):
        # Доступ уже выдан через webhook — отправляем ссылку
        invite_link = await create_secure_invite(bot, user_id)

        try:
            await callback.message.delete()
        except Exception:
            pass

        if invite_link:
            await callback.message.answer(
                texts.GUIDE_PAYMENT_FOUND.format(invite_link=invite_link),
                reply_markup=main_menu(),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            await callback.message.answer(
                "✅ <b>Оплата подтверждена!</b>\n\n"
                "Возникла проблема с созданием ссылки.\n"
                "Напиши @mmarsellus — добавлю вручную.",
                reply_markup=main_menu(),
                parse_mode="HTML"
            )
        return

    # Webhook ещё не пришёл — просим подождать
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить ещё раз", callback_data="check_payment")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="guide_buy")],
    ])
    await callback.message.edit_text(
        "⏳ <b>Платёж ещё обрабатывается...</b>\n\n"
        "Обычно это занимает 10-30 секунд после оплаты.\n"
        "Попробуй нажать кнопку ещё раз через минуту.\n\n"
        "Если прошло больше 5 минут — пиши @mmarsellus.",
        reply_markup=kb,
        parse_mode="HTML"
    )
