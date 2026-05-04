"""
Калькулятор стоимости товара с доставкой.
Использует FSM (машину состояний) для пошагового ввода.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import database as db
from utils.keyboards import (
    calc_mode_choice, calc_categories, calc_delivery, calc_result_buttons, back_to_main
)
from utils.helpers import calculate_price
from content import texts

router = Router()


class CalcStates(StatesGroup):
    """Состояния для калькулятора."""
    waiting_for_price = State()       # ждём цену в юанях
    waiting_for_weight = State()      # ждём вес (только в ручном режиме)
    waiting_for_manual_price = State()  # после веса ждём цену
    waiting_for_delivery = State()    # ждём выбор доставки


@router.callback_query(F.data == "calc")
async def show_calc(callback: CallbackQuery, state: FSMContext):
    """Открытие калькулятора — выбор режима."""
    await state.clear()
    await db.log_event(callback.from_user.id, "open_calculator")

    await callback.message.edit_text(
        texts.CALC_INTRO,
        reply_markup=calc_mode_choice(),
        parse_mode="HTML"
    )
    await callback.answer()


# ============ РЕЖИМ ПО КАТЕГОРИИ ============

@router.callback_query(F.data == "calc_cat")
async def calc_by_category(callback: CallbackQuery):
    """Показывает список категорий товаров."""
    await callback.message.edit_text(
        texts.CALC_CHOOSE_CATEGORY,
        reply_markup=calc_categories(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def category_chosen(callback: CallbackQuery, state: FSMContext):
    """Юзер выбрал категорию — сохраняем вес, просим цену."""
    parts = callback.data.split("_")
    category_name = parts[1]
    weight = int(parts[2])

    await state.update_data(weight=weight, category=category_name)
    await state.set_state(CalcStates.waiting_for_price)

    await callback.message.edit_text(
        texts.CALC_ENTER_PRICE.format(category=category_name, weight=weight),
        parse_mode="HTML"
    )
    await callback.answer()


# ============ РЕЖИМ ВРУЧНУЮ ============

@router.callback_query(F.data == "calc_manual")
async def calc_manual(callback: CallbackQuery, state: FSMContext):
    """Ручной режим — сначала просим вес."""
    await state.set_state(CalcStates.waiting_for_weight)
    await callback.message.edit_text(
        texts.CALC_MANUAL_WEIGHT,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(CalcStates.waiting_for_weight)
async def manual_weight_received(message: Message, state: FSMContext):
    """Получили вес в ручном режиме — просим цену."""
    try:
        weight = int(message.text.strip())
        if weight <= 0 or weight > 50000:
            raise ValueError("invalid weight")
    except ValueError:
        await message.answer("❌ Введи целое число — вес в граммах. Например <code>600</code>", parse_mode="HTML")
        return

    await state.update_data(weight=weight, category="Товар")
    await state.set_state(CalcStates.waiting_for_manual_price)

    await message.answer(
        texts.CALC_MANUAL_PRICE.format(weight=weight),
        parse_mode="HTML"
    )


# ============ ПОЛУЧЕНИЕ ЦЕНЫ И ПОКАЗ ВЫБОРА ДОСТАВКИ ============

@router.message(CalcStates.waiting_for_price)
@router.message(CalcStates.waiting_for_manual_price)
async def price_received(message: Message, state: FSMContext):
    """Получили цену в юанях — переходим к выбору доставки."""
    try:
        # Поддерживаем дробные числа: 98 или 98.5 или 98,5
        price_text = message.text.strip().replace(",", ".")
        price = float(price_text)
        if price <= 0 or price > 100000:
            raise ValueError("invalid price")
    except ValueError:
        await message.answer("❌ Введи число — цену в юанях. Например <code>98</code> или <code>98.5</code>", parse_mode="HTML")
        return

    await state.update_data(price=price)
    await state.set_state(CalcStates.waiting_for_delivery)

    await message.answer(
        texts.CALC_CHOOSE_DELIVERY,
        reply_markup=calc_delivery(),
        parse_mode="HTML"
    )


# ============ РАСЧЁТ И РЕЗУЛЬТАТ ============

DELIVERY_MAP = {
    "delivery_air": "air",
    "delivery_auto": "auto",
    "delivery_rail": "rail",
}


@router.callback_query(F.data.in_(DELIVERY_MAP.keys()))
async def delivery_chosen(callback: CallbackQuery, state: FSMContext):
    """Доставка выбрана — считаем результат и показываем."""
    delivery_key = DELIVERY_MAP[callback.data]

    data = await state.get_data()
    weight = data.get("weight")
    price = data.get("price")

    if weight is None or price is None:
        await callback.answer("Ошибка: данные расчёта потерялись. Начни заново.", show_alert=True)
        await state.clear()
        return

    yuan_rate = await db.get_yuan_rate()
    result = calculate_price(price, weight, delivery_key, yuan_rate)

    await db.log_event(callback.from_user.id, "calc_result", {
        "price": price,
        "weight": weight,
        "delivery": delivery_key,
        "total": result["total"]
    })

    text = texts.CALC_RESULT.format(
        product_cost=f"{result['product_cost']:,}".replace(",", " "),
        price_yuan=int(price) if price.is_integer() else price,
        rate=result["rate"],
        commission=f"{result['commission']:,}".replace(",", " "),
        delivery_emoji=result["delivery_emoji"],
        delivery_name=result["delivery_name"],
        shipping=f"{result['shipping']:,}".replace(",", " "),
        weight_kg=result["weight_kg"],
        tariff=result["tariff"],
        total=f"{result['total']:,}".replace(",", " "),
    )

    await callback.message.edit_text(
        text,
        reply_markup=calc_result_buttons(),
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()
