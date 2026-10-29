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
from utils.keyboards import guide_menu, payment_buttons, back_to_main, main_menu
from utils.helpers import generate_payment_label, generate_yoomoney_link
from utils.payment_delivery import deliver_paid_access
from utils.payment_worker import reconcile_payment
from utils.yoomoney_api import YooMoneyAPIError
from content import texts, marketing_texts
from config import config

router = Router()


def priced_text(text: str) -> str:
    """Цена в описании должна совпадать с суммой реального платежа."""
    price = f"{config.PRICE_ULTIMATE_GUIDE:,}".replace(",", " ")
    return text.replace("1 990 ₽", f"{price} ₽")


def offer_notice() -> str:
    """Ненавязчивая ссылка на опубликованную оферту перед покупкой."""
    url = config.OFFER_URL
    if not url.startswith("https://"):
        return ""
    return (
        "Оплачивая доступ, ты принимаешь условия "
        f'<a href="{escape(url, quote=True)}">публичной оферты</a>.'
    )


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
        priced_text(marketing_texts.GUIDE_DESCRIPTION) + (
            "\n\n" + offer_notice() if offer_notice() else ""
        ),
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
async def initiate_payment(callback: CallbackQuery, bot: Bot):
    """Создаёт платёж и показывает кнопку оплаты."""
    user_id = callback.from_user.id

    user = await db.get_user(user_id)
    if user and user.get("purchased_guide"):
        invite_link = await create_secure_invite(bot, user_id)
        await callback.answer()
        if invite_link:
            await callback.message.answer(
                "✅ <b>У тебя уже есть оплаченный доступ.</b>\n\n"
                f"Вот новая ссылка для вступления:\n👉 {invite_link}",
                parse_mode="HTML", disable_web_page_preview=True
            )
        else:
            await callback.message.answer(
                "Доступ уже оплачен, но создать ссылку не получилось. "
                "Напиши @basefrom50man."
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
        priced_text(texts.GUIDE_BUY) + (
            "\n\n" + offer_notice() if offer_notice() else ""
        ),
        reply_markup=payment_buttons(pay_url),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery, bot: Bot):
    """Проверяет локальный статус, затем историю кошелька по уникальному label."""
    user_id = callback.from_user.id
    await callback.answer()

    payment = await db.get_latest_payment(user_id)
    user = await db.get_user(user_id)

    # Ранее купленный гайд, в том числе вручную выданный доступ.
    if user and user.get("purchased_guide"):
        if payment and payment.get("status") in ("completed", "success") and (
            payment.get("delivery_status") in ("pending", "failed")
        ):
            if await deliver_paid_access(bot, payment["label"]):
                await callback.message.answer(
                    "✅ Оплата подтверждена. Ссылка на канал отправлена отдельным сообщением."
                )
                return

        invite_link = await create_secure_invite(bot, user_id)
        if invite_link:
            await callback.message.answer(
                texts.GUIDE_PAYMENT_FOUND.format(invite_link=invite_link)
                .replace("@mmarsellus", "@basefrom50man"),
                reply_markup=main_menu(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        else:
            await callback.message.answer(
                "✅ Оплата подтверждена, но ссылка пока не создаётся. "
                "Напиши @basefrom50man, доступ сохранился."
            )
        return

    if not payment:
        await callback.message.answer(
            "Не вижу начатого заказа. Открой ULTIMATE GUIDE и нажми кнопку покупки."
        )
        return

    if config.YOOMONEY_TOKEN:
        try:
            if await reconcile_payment(bot, payment):
                await callback.message.answer(
                    "✅ Платёж найден в ЮMoney! "
                    "Приглашение в закрытый канал отправлено отдельным сообщением. "
                    "Если не получил — напиши @basefrom50man."
                )
                return
        except YooMoneyAPIError:
            await callback.message.answer(
                "⚠️ Сейчас не удалось связаться с ЮMoney для проверки. "
                "Попробуй ещё раз через минуту. Если оплатил — "
                "деньги не пропали, напиши @basefrom50man."
            )
            return
    else:
        await callback.message.answer(
            "⏳ Ожидаю автоматическое подтверждение ЮMoney. "
            "Резервная проверка пока недоступна. "
            "Если оплатил и прошло больше 5 минут — напиши @basefrom50man."
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Проверить ещё раз", callback_data="check_payment")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="guide")],
    ])
    try:
        await callback.message.edit_text(
            "⏳ <b>Платёж пока не найден в ЮMoney.</b>\n\n"
            "Если ты только что оплатил, подожди 30–60 секунд "
            "и нажми «Проверить ещё раз».\n\n"
            "Если прошло больше 5 минут — пиши @basefrom50man.",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception:
        pass
