"""
Раздел ULTIMATE GUIDE — продажа гайда через YooMoney.
Проверка платежа происходит по нажатию "Я оплатил".
"""
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from db import database as db
from utils.keyboards import (
    guide_menu, guide_reviews_menu, payment_buttons, back_to_main, main_menu
)
from utils.helpers import generate_payment_label, generate_yoomoney_link
from content import texts
from config import config

router = Router()


@router.callback_query(F.data == "guide")
async def show_guide(callback: CallbackQuery):
    """Описание ULTIMATE GUIDE."""
    await db.log_event(callback.from_user.id, "view_guide")

    await callback.message.edit_text(
        texts.GUIDE_DESCRIPTION,
        reply_markup=guide_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "guide_reviews")
async def show_reviews(callback: CallbackQuery):
    """Отзывы учеников."""
    await db.log_event(callback.from_user.id, "view_reviews")

    await callback.message.edit_text(
        texts.GUIDE_REVIEWS,
        reply_markup=guide_reviews_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "guide_buy")
async def initiate_payment(callback: CallbackQuery):
    """Создаёт платёж и показывает кнопки оплаты."""
    user_id = callback.from_user.id

    # Проверяем не купил ли уже
    user = await db.get_user(user_id)
    if user and user.get("purchased_guide"):
        await callback.answer("Ты уже купил гайд. Связь с админом если потерял доступ.", show_alert=True)
        return

    # Создаём label для отслеживания
    label = generate_payment_label(user_id)

    await db.create_payment(
        user_id=user_id,
        amount=config.PRICE_ULTIMATE_GUIDE,
        product="ultimate_guide",
        label=label
    )
    await db.log_event(user_id, "payment_initiated", {"label": label})

    pay_url = generate_yoomoney_link(
        amount=config.PRICE_ULTIMATE_GUIDE,
        label=label,
        wallet=config.YOOMONEY_WALLET
    )

    # Сохраняем label в callback data — будет нужен при проверке
    # Используем простую схему: храним последний label юзера в БД
    # (для MVP достаточно — у юзера только один активный платёж)
    await db.set_setting(f"last_label_{user_id}", label)

    await callback.message.edit_text(
        texts.GUIDE_BUY,
        reply_markup=payment_buttons(pay_url),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery, bot: Bot):
    """Проверяет оплату через YooMoney API и выдаёт инвайт-ссылку."""
    user_id = callback.from_user.id

    await callback.message.edit_text(
        texts.GUIDE_PAYMENT_CHECK,
        parse_mode="HTML"
    )
    await callback.answer()

    # Достаём последний label юзера
    label = await db.get_setting(f"last_label_{user_id}", "")
    if not label:
        await callback.message.edit_text(
            texts.GUIDE_PAYMENT_NOT_FOUND,
            reply_markup=back_to_main(),
            parse_mode="HTML"
        )
        return

    payment = await db.get_payment_by_label(label)
    if not payment:
        await callback.message.edit_text(
            texts.GUIDE_PAYMENT_NOT_FOUND,
            reply_markup=back_to_main(),
            parse_mode="HTML"
        )
        return

    # Проверяем через YooMoney API
    is_paid = await verify_payment_yoomoney(label, config.PRICE_ULTIMATE_GUIDE)

    if not is_paid:
        await callback.message.edit_text(
            texts.GUIDE_PAYMENT_NOT_FOUND,
            reply_markup=back_to_main(),
            parse_mode="HTML"
        )
        return

    # Оплата подтверждена — выдаём доступ
    await db.mark_payment_completed(label, "verified")
    await db.mark_purchased(user_id)
    await db.log_event(user_id, "guide_purchased")

    # Создаём одноразовую инвайт-ссылку в закрытый канал
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=config.PRIVATE_CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(days=7),
            name=f"User {user_id}"
        )
        invite_link = invite.invite_link
    except Exception as e:
        # Если не получилось — логируем и просим связаться
        await db.log_event(user_id, "invite_link_error", {"error": str(e)})
        await callback.message.edit_text(
            "✅ Оплата прошла, но возникла техническая проблема с автоматической выдачей доступа.\n\n"
            "Напиши @mmarsellus — добавлю тебя в канал вручную в течение часа.",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
        # Уведомляем админа
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"⚠️ Юзер {user_id} оплатил гайд, но invite-ссылка не создалась.\nОшибка: {e}"
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

    # Уведомляем админа о продаже
    try:
        await bot.send_message(
            config.ADMIN_ID,
            f"💰 НОВАЯ ПРОДАЖА!\n\n"
            f"Юзер: @{callback.from_user.username or 'без_username'} (ID: {user_id})\n"
            f"Продукт: ULTIMATE GUIDE\n"
            f"Сумма: {config.PRICE_ULTIMATE_GUIDE}₽"
        )
    except Exception:
        pass


async def verify_payment_yoomoney(label: str, amount: int) -> bool:
    """
    Проверяет оплату через YooMoney API.
    Если YOOMONEY_TOKEN не настроен — возвращает False (не подключено).
    """
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
                data={
                    "label": label,
                    "type": "deposition",
                    "records": "10",
                }
            ) as resp:
                if resp.status != 200:
                    return False

                data = await resp.json()
                operations = data.get("operations", [])

                for op in operations:
                    if (
                        op.get("label") == label
                        and op.get("status") == "success"
                        and op.get("direction") == "in"
                        and float(op.get("amount", 0)) >= amount * 0.95  # допуск 5% на комиссию
                    ):
                        return True
                return False
    except Exception:
        return False
