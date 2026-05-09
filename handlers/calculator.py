"""
Калькулятор стоимости товара с доставкой.
Правки #2 (удаление промпт-сообщений), #3 (фикс tariff в формате).
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import database as db
from utils.keyboards import (
    calc_mode_choice, calc_categories, calc_delivery, calc_result_buttons
)
from utils.helpers import calculate_price, calculate_cart_total
from content import texts

router = Router()


class CalcStates(StatesGroup):
    choosing_category = State()
    entering_price = State()
    entering_weight = State()
    entering_manual_price = State()
    choosing_delivery = State()


# =============================================================
# СТАРТ КАЛЬКУЛЯТОРА
# =============================================================

@router.callback_query(F.data == "calc")
async def show_calc(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await db.log_event(callback.from_user.id, "open_calculator")
    await callback.message.edit_text(
        texts.CALC_INTRO,
        reply_markup=calc_mode_choice(),
        parse_mode="HTML"
    )
    await callback.answer()


# =============================================================
# РЕЖИМ ПО КАТЕГОРИИ — КОРЗИНА
# =============================================================

@router.callback_query(F.data == "calc_cat")
async def calc_by_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcStates.choosing_category)
    data = await state.get_data()
    cart = data.get("cart", [])
    await callback.message.edit_text(
        texts.CALC_CHOOSE_CATEGORY,
        reply_markup=calc_categories(cart),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(CalcStates.choosing_category, F.data.startswith("cat_"))
async def category_chosen(callback: CallbackQuery, state: FSMContext):
    """Юзер выбрал категорию — сохраняем и просим цену."""
    parts = callback.data.split("_")
    category_name = parts[1]
    weight = int(parts[2])

    await state.update_data(
        current_category=category_name,
        current_weight=weight,
        # Правка #2: сохраняем ID сообщения чтобы удалить его после ввода цены
        prompt_msg_id=callback.message.message_id,
        prompt_chat_id=callback.message.chat.id,
    )
    await state.set_state(CalcStates.entering_price)

    await callback.message.edit_text(
        texts.CALC_ENTER_PRICE.format(category=category_name, weight=weight),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CalcStates.entering_price)
async def cart_price_received(message: Message, state: FSMContext):
    """Получили цену — добавляем в корзину, удаляем сообщения."""
    # Правка #2: удаляем сообщение юзера
    try:
        await message.delete()
    except Exception:
        pass

    # Правка #2: удаляем промпт-сообщение бота "Введи цену"
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_msg_id")
    prompt_chat_id = data.get("prompt_chat_id")
    if prompt_msg_id and prompt_chat_id:
        try:
            await message.bot.delete_message(prompt_chat_id, prompt_msg_id)
        except Exception:
            pass

    try:
        price_text = message.text.strip().replace(",", ".")
        price = float(price_text)
        if price <= 0 or price > 100000:
            raise ValueError()
    except (ValueError, AttributeError):
        err = await message.answer(
            "❌ Введи число — цену в юанях. Например <code>98</code>",
            parse_mode="HTML"
        )
        return

    category = data.get("current_category", "Товар")
    weight = data.get("current_weight", 500)

    cart = data.get("cart", [])
    cart.append({
        "category": category,
        "weight": weight,
        "price_yuan": price
    })
    await state.update_data(cart=cart)
    await state.set_state(CalcStates.choosing_category)

    # Отправляем новое сообщение с обновлёнными категориями
    await message.answer(
        texts.CALC_CHOOSE_CATEGORY,
        reply_markup=calc_categories(cart),
        parse_mode="HTML"
    )


@router.callback_query(CalcStates.choosing_category, F.data == "calc_compute")
async def calc_compute(callback: CallbackQuery, state: FSMContext):
    """Юзер нажал Расчет — переходим к выбору доставки."""
    await state.update_data(delivery_mode="cart")
    await state.set_state(CalcStates.choosing_delivery)

    await callback.message.edit_text(
        texts.CALC_CHOOSE_DELIVERY,
        reply_markup=calc_delivery(back_target="calc_cat"),
        parse_mode="HTML"
    )
    await callback.answer()


# =============================================================
# РУЧНОЙ РЕЖИМ
# =============================================================

@router.callback_query(F.data == "calc_manual")
async def calc_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CalcStates.entering_weight)
    await callback.message.edit_text(
        texts.CALC_MANUAL_WEIGHT,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CalcStates.entering_weight)
async def manual_weight_received(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass

    try:
        weight = int(message.text.strip())
        if weight <= 0 or weight > 50000:
            raise ValueError()
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введи целое число — вес в граммах. Например <code>600</code>",
            parse_mode="HTML"
        )
        return

    await state.update_data(manual_weight=weight, delivery_mode="manual")
    await state.set_state(CalcStates.entering_manual_price)

    await message.answer(
        texts.CALC_MANUAL_PRICE.format(weight=weight),
        parse_mode="HTML"
    )


@router.message(CalcStates.entering_manual_price)
async def manual_price_received(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception:
        pass

    try:
        price_text = message.text.strip().replace(",", ".")
        price = float(price_text)
        if price <= 0 or price > 100000:
            raise ValueError()
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введи число — цену в юанях. Например <code>98</code>",
            parse_mode="HTML"
        )
        return

    await state.update_data(manual_price=price, delivery_mode="manual")
    await state.set_state(CalcStates.choosing_delivery)

    await message.answer(
        texts.CALC_CHOOSE_DELIVERY,
        reply_markup=calc_delivery(back_target="calc"),
        parse_mode="HTML"
    )


# =============================================================
# РЕЗУЛЬТАТ РАСЧЁТА
# =============================================================

DELIVERY_MAP = {
    "delivery_air": "air",
    "delivery_auto": "auto",
    "delivery_rail": "rail",
}


@router.callback_query(F.data.in_(DELIVERY_MAP.keys()))
async def delivery_chosen(callback: CallbackQuery, state: FSMContext):
    """Выбрана доставка — считаем результат."""
    delivery_key = DELIVERY_MAP[callback.data]
    data = await state.get_data()
    delivery_mode = data.get("delivery_mode", "manual")

    yuan_rate = await db.get_yuan_rate()

    try:
        if delivery_mode == "cart":
            cart = data.get("cart", [])
            if not cart:
                await callback.answer("Корзина пуста!", show_alert=True)
                return

            result = calculate_cart_total(cart, delivery_key, yuan_rate)

            # Правка #3: добавлен tariff= который раньше вызывал KeyError
            text = texts.CALC_RESULT_CART.format(
                total_product_cost=f"{result['total_product_cost']:,}".replace(",", " "),
                item_count=result["item_count"],
                total_weight_kg=result["total_weight_kg"],
                commission=f"{result['commission']:,}".replace(",", " "),
                delivery_emoji=result["delivery_emoji"],
                delivery_name=result["delivery_name"],
                shipping=f"{result['shipping']:,}".replace(",", " "),
                tariff=result["tariff"],  # ← БЫЛ ПРОПУЩЕН — ОТСЮДА СПИННЕР
                total=f"{result['total']:,}".replace(",", " "),
            )

            await db.log_event(callback.from_user.id, "calc_result_cart", {
                "items": len(cart), "total": result["total"], "delivery": delivery_key,
            })

        else:
            weight = data.get("manual_weight")
            price = data.get("manual_price")

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

            await db.log_event(callback.from_user.id, "calc_result", {
                "price": price, "weight": weight,
                "delivery": delivery_key, "total": result["total"],
            })

        await state.clear()
        await callback.message.edit_text(
            text,
            reply_markup=calc_result_buttons(),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        await db.log_event(callback.from_user.id, "calc_error", {"error": str(e)})
        await callback.answer(f"Ошибка расчёта: {e}", show_alert=True)
