"""
Раздел ULTIMATE GUIDE. Правки #3, #4, #5.
"""
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from db import database as db
from utils.keyboards import guide_menu, payment_buttons, back_to_main, main_menu
from utils.helpers import generate_payment_label, generate_yoomoney_link
from content import texts
from config import config

router = Router()

# Правка #5: тестовая цена 10₽ (поменять на 5990 после тестирования)
TEST_PRICE = 10


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
    """Правка #5: использует TEST_PRICE=10₽."""
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
        amount=TEST_PRICE,
        product="ultimate_guide",
        label=label
    )
    await db.log_event(user_id, "payment_initiated", {"label": label, "amount": TEST_PRICE})
    await db.set_setting(f"last_label_{user_id}", label)

    pay_url = generate_yoomoney_link(
        amount=TEST_PRICE,
        label=label,
        wallet=config.YOOMONEY_WALLET
    )

    await callback.message.edit_text(
        texts.GUIDE_BUY,
        # Правка #4: кнопка Назад → guide_buy (чтобы снова нажать "Я оплатил")
        reply_markup=payment_buttons(pay_url),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery, bot: Bot):
    """Проверяет оплату через YooMoney API."""
    user_id = callback.from_user.id

    await callback.message.edit_text(
        texts.GUIDE_PAYMENT_CHECK,
        parse_mode="HTML"
    )
    await callback.answer()

    label = await db.get_setting(f"last_label_{user_id}", "")
    if not label:
        await callback.message.edit_text(
            texts.GUIDE_PAYMENT_NOT_FOUND,
            reply_markup=back_to_main(),
            parse_mode="HTML"
        )
        return

    is_paid = await verify_payment_yoomoney(label, TEST_PRICE)

    if not is_paid:
        # Правка #4: кнопка Назад чтобы снова попробовать
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_payment")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="guide_buy")],
        ])
        await callback.message.edit_text(
            texts.GUIDE_PAYMENT_NOT_FOUND,
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    # Оплата подтверждена
    await db.mark_payment_completed(label, "verified")
    await db.mark_purchased(user_id)
    await db.log_event(user_id, "guide_purchased")

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(days=7),
            name=f"User {user_id}"
        )
        invite_link = invite.invite_link
    except Exception as e:
        await db.log_event(user_id, "invite_link_error", {"error": str(e)})
        await callback.message.edit_text(
            "✅ Оплата прошла! Возникла техническая проблема с выдачей доступа.\n\n"
            "Напиши @mmarsellus — добавлю в канал вручную в течение часа.",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"⚠️ Юзер {user_id} оплатил, но invite-ссылка не создалась.\nОшибка: {e}"
            )
        except Exception:
            pass
        return

    await callback.message.edit_text(
        texts.GUIDE_PAYMENT_FOUND.format(invite_link=invite_link),
        reply_markup=main_menu(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    try:
        await bot.send_message(
            config.ADMIN_ID,
            f"💰 НОВАЯ ПРОДАЖА!\n\n"
            f"Юзер: @{callback.from_user.username or 'без_username'} (ID: {user_id})\n"
            f"Продукт: ULTIMATE GUIDE\n"
            f"Сумма: {TEST_PRICE}₽"
        )
    except Exception:
        pass


async def verify_payment_yoomoney(label: str, amount: int) -> bool:
    if not config.YOOMONEY_TOKEN:
        return False
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://yoomoney.ru/api/operation-history",
                headers={
                    "Authorization": f"Bearer {config.YOOMONEY_TOKEN}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"label": label, "type": "deposition", "records": "10"}
            ) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                for op in data.get("operations", []):
                    if (
                        op.get("label") == label
                        and op.get("status") == "success"
                        and op.get("direction") == "in"
                        and float(op.get("amount", 0)) >= amount * 0.95
                    ):
                        return True
                return False
    except Exception:
        return False
