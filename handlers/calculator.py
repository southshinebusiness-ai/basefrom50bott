"""
Калькулятор стоимости товара с доставкой.
Правки #6-#12: корзина, счётчики, удаление сообщений, кнопки Назад.
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
    choosing_category = State()      # выбор категории + корзина
    entering_price = State()         # ввод цены для категории
    entering_weight = State()        # ручной режим - вес
    entering_manual_price = State()  # ручной режим - цена
    choosing_delivery = State()      # выбор доставки (и режима)


# =============================================================
# СТАРТ КАЛЬКУЛЯТОРА
# =============================================================

@router.callback_query(F.data == "calc")
async def show_calc(callback: CallbackQuery, state: FSMContext):
    """Главный экран калькулятора — выбор режима."""
    await state.clear()
    await db.log_event(callback.from_user.id, "open_calculator")

    await callback.message.edit_text(
        texts.CALC_INTRO,
        reply_markup=calc_mode_choice(),
        parse_mode="HTML"
    )
    await callback.answer()


# =============================================================
# РЕЖИМ ПО КАТЕГОРИИ — КОРЗИНА (#11, #12)
# =============================================================

@router.callback_query(F.data == "calc_cat")
async def calc_by_category(callback: CallbackQuery, state: FSMContext):
    """Показывает список категорий с корзиной."""
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
    """Юзер выбрал категорию — сохраняем, просим цену."""
    parts = callback.data.split("_")
    category_name = parts[1]
    weight = int(parts[2])

    await state.update_data(
        current_category=category_name,
        current_weight=weight,
        prompt_msg_id=None
    )
    await state.set_state(CalcStates.entering_price)

    # Сохраняем ID этого сообщения чтобы удалить после ввода
    prompt = await callback.message.edit_text(
        texts.CALC_ENTER_PRICE.format(category=category_name, weight=weight),
        parse_mode="HTML"
    )
    # prompt уже является исходным сообщением которое edit_text изменил
    await callback.answer()


@router.message(CalcStates.entering_price)
async def cart_price_received(message: Message, state: FSMContext):
    """Получили цену для категории — добавляем в корзину, удаляем сообщения."""
    # Правка #12: удаляем сообщение юзера
    try:
        await message.delete()
    except Exception:
        pass

    try:
        price_text = message.text.strip().replace(",", ".")
        price = float(price_text)
        if price <= 0 or price > 100000:
            raise ValueError("invalid")
    except (ValueError, AttributeError):
        err = await message.answer(
            "❌ Введи число — цену в юанях. Например <code>98</code>",
            parse_mode="HTML"
        )
        # Удалим ошибку через 3 секунды (не критично, пропустим)
        return

    data = await state.get_data()
    category = data.get("current_category", "Товар")
    weight = data.get("current_weight", 500)

    # Добавляем в корзину
    cart = data.get("cart", [])
    cart.append({
        "category": category,
        "weight": weight,
        "price_yuan": price
    })
    await state.update_data(cart=cart)
    await state.set_state(CalcStates.choosing_category)

    # Возвращаемся к выбору категорий с обновлёнными счётчиками
    await message.answer(
        texts.CALC_CHOOSE_CATEGORY,
        reply_markup=calc_categories(cart),
        parse_mode="HTML"
    )


@router.callback_query(CalcStates.choosing_category, F.data == "calc_compute")
async def calc_compute(callback: CallbackQuery, state: FSMContext):
    """Юзер нажал Расчет — переходим к выбору доставки."""
    await state.set_state(CalcStates.choosing_delivery)
    await state.update_data(delivery_mode="cart")

    await callback.message.edit_text(
        texts.CALC_CHOOSE_DELIVERY,
        # Правка #9: Назад → обратно к категориям
        reply_markup=calc_delivery(back_target="calc_cat"),
        parse_mode="HTML"
    )
    await callback.answer()


# =============================================================
# РУЧНОЙ РЕЖИМ
# =============================================================

@router.callback_query(F.data == "calc_manual")
async def calc_manual(callback: CallbackQuery, state: FSMContext):
    """Ручной режим — просим вес."""
    await state.set_state(CalcStates.entering_weight)
    await callback.message.edit_text(
        texts.CALC_MANUAL_WEIGHT,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CalcStates.entering_weight)
async def manual_weight_received(message: Message, state: FSMContext):
    """Получили вес — правка #12: удаляем сообщение юзера."""
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
    """Получили цену в ручном режиме — правка #12: удаляем сообщение."""
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
        # Правка #9: Назад → к началу калькулятора
        reply_markup=calc_delivery(back_target="calc"),
        parse_mode="HTML"
    )


# =============================================================
# РЕЗУЛЬТАТ РАСЧЁТА (#7, #8)
# =============================================================

DELIVERY_MAP = {
    "delivery_air": "air",
    "delivery_auto": "auto",
    "delivery_rail": "rail",
}


@router.callback_query(F.data.in_(DELIVERY_MAP.keys()))
async def delivery_chosen(callback: CallbackQuery, state: FSMContext):
    """Выбрана доставка — считаем и показываем результат."""
    delivery_key = DELIVERY_MAP[callback.data]
    data = await state.get_data()
    delivery_mode = data.get("delivery_mode", "manual")

    yuan_rate = await db.get_yuan_rate()

    if delivery_mode == "cart":
        # Расчёт по корзине
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
            total=f"{result['total']:,}".replace(",", " "),
        )

        await db.log_event(callback.from_user.id, "calc_result_cart", {
            "items": len(cart),
            "total": result["total"],
            "delivery": delivery_key,
        })

    else:
        # Расчёт одного товара (ручной режим)
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
            "price": price,
            "weight": weight,
            "delivery": delivery_key,
            "total": result["total"],
        })

    await state.clear()

    await callback.message.edit_text(
        text,
        reply_markup=calc_result_buttons(),
        parse_mode="HTML"
    )
    await callback.answer()
