"""
Калькулятор стоимости.
Баннер отправляется при открытии и НЕ удаляется во время расчётов.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import database as db
from utils.keyboards import (
    calc_mode_choice, calc_categories, calc_result_buttons
)
from utils.helpers import calculate_price, calculate_cart_total
from content import texts

router = Router()
BANNER = Path("content/images/banner_calc_final.png")


class CalcStates(StatesGroup):
    choosing_category = State()
    entering_price    = State()
    entering_weight   = State()
    entering_manual_price = State()


async def _send_calc_banner(bot: Bot, chat_id: int, state: FSMContext):
    """Отправляет баннер калькулятора один раз при открытии."""
    data = await state.get_data()
    if data.get("calc_banner_id"):
        return  # баннер уже есть — не дублируем
    if BANNER.exists():
        try:
            msg = await bot.send_photo(chat_id, FSInputFile(BANNER))
            await state.update_data(calc_banner_id=msg.message_id)
        except Exception:
            pass


async def _delete_calc_banner(bot: Bot, chat_id: int, state: FSMContext):
    """Удаляет баннер калькулятора (при выходе из раздела)."""
    data = await state.get_data()
    banner_id = data.get("calc_banner_id")
    if banner_id:
        try:
            await bot.delete_message(chat_id, banner_id)
        except Exception:
            pass
        await state.update_data(calc_banner_id=None)


# ── СТАРТ КАЛЬКУЛЯТОРА ─────────────────────────────────────────

@router.callback_query(F.data == "calc")
async def show_calc(callback: CallbackQuery, state: FSMContext, bot: Bot):
    chat_id = callback.message.chat.id

    # Сначала читаем данные, ПОТОМ чистим state
    data = await state.get_data()
    await state.clear()
    await db.log_event(callback.from_user.id, "open_calculator")

    # Удаляем все старые баннеры
    for key in ("banner_msg_id", "calc_banner_id"):
        bid = data.get(key)
        if bid:
            try:
                await bot.delete_message(chat_id, bid)
            except Exception:
                pass

    try:
        await bot.delete_message(chat_id, callback.message.message_id)
    except Exception:
        pass

    # Отправляем баннер калькулятора
    await _send_calc_banner(bot, chat_id, state)

    await bot.send_message(
        chat_id, texts.CALC_INTRO,
        reply_markup=calc_mode_choice(), parse_mode="HTML"
    )
    await callback.answer()


# ── РЕЖИМ ПО КАТЕГОРИИ ─────────────────────────────────────────

@router.callback_query(F.data == "calc_cat")
async def calc_by_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcStates.choosing_category)
    data = await state.get_data()
    cart = data.get("cart", [])
    await callback.message.edit_text(
        texts.CALC_CHOOSE_CATEGORY,
        reply_markup=calc_categories(cart), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(CalcStates.choosing_category, F.data.startswith("cat_"))
async def category_chosen(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    name, weight = parts[1], int(parts[2])
    await state.update_data(
        current_category=name, current_weight=weight,
        prompt_msg_id=callback.message.message_id,
        prompt_chat_id=callback.message.chat.id,
    )
    await state.set_state(CalcStates.entering_price)
    await callback.message.edit_text(
        texts.CALC_ENTER_PRICE.format(category=name, weight=weight),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CalcStates.entering_price)
async def cart_price_received(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    prompt_id   = data.get("prompt_msg_id")
    prompt_chat = data.get("prompt_chat_id")
    if prompt_id and prompt_chat:
        try:
            await message.bot.delete_message(prompt_chat, prompt_id)
        except Exception:
            pass

    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0 or price > 100000:
            raise ValueError()
    except (ValueError, AttributeError):
        await message.answer("❌ Введи число в юанях. Например <code>98</code>", parse_mode="HTML")
        return

    category = data.get("current_category", "Товар")
    weight   = data.get("current_weight", 500)
    cart     = data.get("cart", [])
    cart.append({"category": category, "weight": weight, "price_yuan": price})
    await state.update_data(cart=cart)
    await state.set_state(CalcStates.choosing_category)

    await message.answer(
        texts.CALC_CHOOSE_CATEGORY,
        reply_markup=calc_categories(cart), parse_mode="HTML"
    )


@router.callback_query(CalcStates.choosing_category, F.data == "calc_compute")
async def calc_compute(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data      = await state.get_data()
    cart      = data.get("cart", [])
    chat_id   = callback.message.chat.id
    if not cart:
        await callback.answer("Корзина пуста!", show_alert=True)
        return
    yuan_rate = await db.get_yuan_rate()
    result    = calculate_cart_total(cart, yuan_rate)
    text      = texts.CALC_RESULT_CART.format(
        total_product_cost=f"{result['total_product_cost']:,}".replace(",", " "),
        item_count=result["item_count"],
        total_weight_kg=result["total_weight_kg"],
        commission=f"{result['commission']:,}".replace(",", " "),
        shipping=f"{result['shipping']:,}".replace(",", " "),
        dollar_rate=result["dollar_rate"],
        total=f"{result['total']:,}".replace(",", " "),
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await _delete_calc_banner(bot, chat_id, state)
    await state.clear()
    await bot.send_message(chat_id, text, reply_markup=calc_result_buttons(), parse_mode="HTML")
    await callback.answer()


# ── РУЧНОЙ РЕЖИМ ───────────────────────────────────────────────

@router.callback_query(F.data == "calc_manual")
async def calc_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcStates.entering_weight)
    # Сохраняем ID промпта чтобы удалить при вводе
    await state.update_data(
        prompt_msg_id=callback.message.message_id,
        prompt_chat_id=callback.message.chat.id
    )
    await callback.message.edit_text(texts.CALC_MANUAL_WEIGHT, parse_mode="HTML")
    await callback.answer()


@router.message(CalcStates.entering_weight)
async def manual_weight_received(message: Message, state: FSMContext):
    # Удаляем сообщение юзера
    try:
        await message.delete()
    except Exception:
        pass
    # Удаляем промпт бота "Введи вес"
    data = await state.get_data()
    prompt_id   = data.get("prompt_msg_id")
    prompt_chat = data.get("prompt_chat_id")
    if prompt_id and prompt_chat:
        try:
            await message.bot.delete_message(prompt_chat, prompt_id)
        except Exception:
            pass

    try:
        weight = int(message.text.strip())
        if weight <= 0 or weight > 50000:
            raise ValueError()
    except (ValueError, AttributeError):
        await message.answer("❌ Введи вес в граммах. Например <code>600</code>", parse_mode="HTML")
        return

    # Отправляем промпт цены и сохраняем его ID
    price_prompt = await message.answer(
        texts.CALC_MANUAL_PRICE.format(weight=weight), parse_mode="HTML"
    )
    await state.update_data(
        manual_weight=weight,
        delivery_mode="manual",
        prompt_msg_id=price_prompt.message_id,
        prompt_chat_id=message.chat.id
    )
    await state.set_state(CalcStates.entering_manual_price)


@router.message(CalcStates.entering_manual_price)
async def manual_price_received(message: Message, state: FSMContext):
    # Удаляем сообщение юзера
    try:
        await message.delete()
    except Exception:
        pass
    # Удаляем промпт бота "Введи цену"
    data = await state.get_data()
    prompt_id   = data.get("prompt_msg_id")
    prompt_chat = data.get("prompt_chat_id")
    if prompt_id and prompt_chat:
        try:
            await message.bot.delete_message(prompt_chat, prompt_id)
        except Exception:
            pass

    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0 or price > 100000:
            raise ValueError()
    except (ValueError, AttributeError):
        await message.answer("❌ Введи цену в юанях. Например <code>98</code>", parse_mode="HTML")
        return

    # Считаем сразу — без выбора доставки
    data    = await state.get_data()
    weight  = data.get("manual_weight")
    yuan_rate = await db.get_yuan_rate()
    result  = calculate_price(price, weight, yuan_rate)
    text    = texts.CALC_RESULT_SINGLE.format(
        product_cost=f"{result['product_cost']:,}".replace(",", " "),
        price_yuan=int(price) if price == int(price) else price,
        rate=result["rate"],
        cargo_delivery=result["cargo_delivery"],
        commission=f"{result['commission']:,}".replace(",", " "),
        shipping=f"{result['shipping']:,}".replace(",", " "),
        weight_kg=result["weight_kg"],
        dollar_rate=result["dollar_rate"],
        total=f"{result['total']:,}".replace(",", " "),
    )
    await _delete_calc_banner(message.bot, message.chat.id, state)
    await state.clear()
    await message.answer(text, reply_markup=calc_result_buttons(), parse_mode="HTML")


# ── РЕЗУЛЬТАТ ──────────────────────────────────────────────────

@router.callback_query(F.data.in_(DELIVERY_MAP.keys()))
async def delivery_chosen(callback: CallbackQuery, state: FSMContext, bot: Bot):
    delivery_key  = DELIVERY_MAP[callback.data]
    data          = await state.get_data()
    delivery_mode = data.get("delivery_mode", "manual")
    yuan_rate     = await db.get_yuan_rate()
    chat_id       = callback.message.chat.id

    try:
        if delivery_mode == "cart":
            cart = data.get("cart", [])
            if not cart:
                await callback.answer("Корзина пуста!", show_alert=True)
                return
            result = calculate_cart_total(cart, delivery_key, yuan_rate)
            text = texts.CALC_RESULT_CART.format(
                total_product_cost=f"{result['total_product_cost']:,}".replace(",", " "),
                item_count=result["item_count"],
                total_weight_kg=result["total_weight_kg"],
                commission=f"{result['commission']:,}".replace(",", " "),
                delivery_emoji=result["delivery_emoji"],
                delivery_name=result["delivery_name"],
                shipping=f"{result['shipping']:,}".replace(",", " "),
                tariff=result["tariff"],
                total=f"{result['total']:,}".replace(",", " "),
            )
        else:
            weight = data.get("manual_weight")
            price  = data.get("manual_price")
            if weight is None or price is None:
                await callback.answer("Данные потерялись. Начни заново.", show_alert=True)
                await state.clear()
                return
            result = calculate_price(price, weight, delivery_key, yuan_rate)
            text = texts.CALC_RESULT_SINGLE.format(
                product_cost=f"{result['product_cost']:,}".replace(",", " "),
                price_yuan=int(price) if price == int(price) else price,
                rate=result["rate"],
                cargo_delivery=result["cargo_delivery"],
                commission=f"{result['commission']:,}".replace(",", " "),
                delivery_emoji=result["delivery_emoji"],
                delivery_name=result["delivery_name"],
                shipping=f"{result['shipping']:,}".replace(",", " "),
                weight_kg=result["weight_kg"],
                tariff=result["tariff"],
                total=f"{result['total']:,}".replace(",", " "),
            )

        # Удаляем баннер калькулятора после результата
        await _delete_calc_banner(bot, chat_id, state)
        await state.clear()

        await callback.message.edit_text(
            text, reply_markup=calc_result_buttons(), parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        await db.log_event(callback.from_user.id, "calc_error", {"error": str(e)})
        await callback.answer(f"Ошибка расчёта: {e}", show_alert=True)
