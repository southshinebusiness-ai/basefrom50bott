"""
Раздел ULTIMATE GUIDE.
Оплата проверяется через YooMoney webhook (автоматически).
Кнопка "Я оплатил" как резервный вариант для редких случаев задержки.
"""
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from pathlib import Path
from html import escape

from db import database as db
from utils.keyboards import guide_menu, payment_buttons, tribute_payment_buttons, back_to_main, main_menu
from utils.helpers import generate_payment_label, generate_yoomoney_link
from content import texts, marketing_texts
from config import config

router = Router()


def offer_notice() -> str:
    """Ссылка на оферту в Telegram HTML, без неработающего placeholder."""
    if not config.OFFER_URL.startswith(("https://", "http://")):
        return ""
    return (
        "Оплачивая доступ, ты принимаешь условия "
        f'<a href="{escape(config.OFFER_URL, quote=True)}">публичной оферты</a>.'
    )


def guide_description() -> str:
    description = marketing_texts.GUIDE_DESCRIPTION
    if config.TRIBUTE_PAYMENT_URL:
        price = f"{config.PRICE_ULTIMATE_GUIDE:,}".replace(",", " ")
        description = description.replace("1 990 ₽", f"{price} ₽")
    notice = offer_notice()
    return f"{description}\n\n{notice}" if notice else description


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


async def send_guide_screen(bot: Bot, chat_id: int, user_id: int, state: FSMContext):
    """Показывает экран ULTIMATE GUIDE без привязки к CallbackQuery."""
    await db.log_event(user_id, "view_guide")

    # Удаляем баннер любого раздела
    try:
        data = await state.get_data()
        for key in ("banner_msg_id", "calc_banner_id"):
            bid = data.get(key)
            if bid:
                try:
                    await bot.delete_message(chat_id, bid)
                except Exception:
                    pass
        await state.update_data(banner_msg_id=None, calc_banner_id=None)
    except Exception:
        pass

    banner = Path("content/images/banner_guide_ultimate_20261025.jpg")
    if banner.exists():
        try:
            msg = await bot.send_photo(chat_id, FSInputFile(banner))
            await state.update_data(banner_msg_id=msg.message_id)
        except Exception:
            pass

    await bot.send_message(
        chat_id,
        guide_description(),
        reply_markup=guide_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "guide")
async def show_guide(callback: CallbackQuery, bot: Bot, state: FSMContext):
    chat_id = callback.message.chat.id

    try:
        await callback.message.delete()
    except Exception:
        pass

    await send_guide_screen(
        bot=bot,
        chat_id=chat_id,
        user_id=callback.from_user.id,
        state=state,
    )
    await callback.answer()


@router.callback_query(F.data == "guide_buy")
async def initiate_payment(callback: CallbackQuery):
    """Создаёт платёж и показывает кнопку оплаты."""
    user_id = callback.from_user.id

    user = await db.get_user(user_id)
    if user and user.get("purchased_guide"):
        await callback.answer(
            "Ты уже купил гайд! Если потерял доступ — пиши @basefrom50man.",
            show_alert=True
        )
        return

    if config.TRIBUTE_PAYMENT_URL:
        # Tribute подтверждает платёж и управляет доступом к тестовому каналу.
        # Не создаём фиктивный платёж YooMoney и не обещаем его проверку.
        await db.log_event(user_id, "tribute_checkout_initiated", {
            "amount": config.PRICE_ULTIMATE_GUIDE,
        })
        price = f"{config.PRICE_ULTIMATE_GUIDE:,}".replace(",", " ")
        notice = offer_notice()
        await callback.message.edit_text(
            f"💎 <b>ULTIMATE GUIDE</b>\n\n"
            f"Разовая оплата — <b>{price} ₽</b>. Доступ без продления.\n\n"
            "Оплата и предоставление доступа проходят через Tribute.\n\n"
            + (f"{notice}\n\n" if notice else "")
            + "После оплаты перейди в закрытый канал по инструкции Tribute.",
            reply_markup=tribute_payment_buttons(config.TRIBUTE_PAYMENT_URL),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await callback.answer()
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
            payment_found_text = texts.GUIDE_PAYMENT_FOUND.format(invite_link=invite_link)
            payment_found_text = payment_found_text.replace("@mmarsellus", "@basefrom50man")
            await callback.message.answer(
                payment_found_text,
                reply_markup=main_menu(),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            await callback.message.answer(
                "✅ <b>Оплата подтверждена!</b>\n\n"
                "Возникла проблема с созданием ссылки.\n"
                "Напиши @basefrom50man — добавлю вручную.",
                reply_markup=main_menu(),
                parse_mode="HTML"
            )
        return

    # Webhook ещё не пришёл — просим подождать
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить ещё раз", callback_data="check_payment")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="guide_buy")],
    ])
    try:
        await callback.message.edit_text(
            "⏳ <b>Платёж ещё обрабатывается...</b>\n\n"
            "Обычно это занимает 10-30 секунд после оплаты.\n"
            "Попробуй нажать кнопку ещё раз через минуту.\n\n"
            "Если прошло больше 5 минут — пиши @basefrom50man.",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        pass  # Сообщение уже такое же — ничего не делаем
