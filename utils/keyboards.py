"""
Inline-клавиатуры бота. Обновлено по правкам #1, #3, #4, #9, #10, #11, #14
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from content import texts
from config import config


# =============================================================
# ГЛАВНОЕ МЕНЮ (правка #1)
# =============================================================

def main_menu() -> InlineKeyboardMarkup:
    """
    Структура:
    Row 1: 🚀 Быстрый старт с РФ 🚀
    Row 2: 🤝 Услуга выкупа | 📦 Калькулятор
    Row 3: 💬 Отзывы | 📢 Основной канал
    Row 4: 📓 ULTIMATE GUIDE 📓
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_START_RF, callback_data="start_rf")],
        [
            InlineKeyboardButton(text=texts.BTN_BUYOUT, callback_data="buyout"),
            InlineKeyboardButton(text=texts.BTN_CALCULATOR, callback_data="calc"),
        ],
        [
            InlineKeyboardButton(text=texts.BTN_REVIEWS_CHANNEL, url="https://t.me/basefrom50otz"),
            InlineKeyboardButton(text=texts.BTN_MAIN_CHANNEL, url="https://t.me/basefrom50"),
        ],
        [InlineKeyboardButton(text=texts.BTN_GUIDE, callback_data="guide")],
    ])


def back_to_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


# =============================================================
# ПОДПИСКА НА КАНАЛ
# =============================================================

def check_subscription() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_GO_CHANNEL, url=config.MAIN_CHANNEL_LINK)],
        [InlineKeyboardButton(text=texts.BTN_CHECK_SUBSCRIPTION, callback_data="check_sub")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


# =============================================================
# СТАРТ С РФ
# =============================================================

def start_course() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_START_COURSE, callback_data="lesson_1")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def next_lesson(current_lesson: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_NEXT_LESSON, callback_data=f"lesson_{current_lesson + 1}")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def finish_course() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_GET_PDF, callback_data="get_pdfs")],
        [InlineKeyboardButton(text=texts.BTN_GO_GUIDE, callback_data="guide")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


# =============================================================
# КАЛЬКУЛЯТОР (правки #9, #10, #11)
# =============================================================

def calc_mode_choice() -> InlineKeyboardMarkup:
    """Выбор режима калькулятора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_CALC_BY_CATEGORY, callback_data="calc_cat")],
        [InlineKeyboardButton(text=texts.BTN_CALC_MANUAL, callback_data="calc_manual")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


# Категории товаров с дефолтным весом
CATEGORIES = [
    ("Футболка", 300),
    ("Лонгслив", 400),
    ("Свитшот", 500),
    ("Худи", 600),
    ("Зипка", 700),
    ("Шорты", 350),
    ("Штаны", 500),
    ("Ветровка", 700),
    ("Куртка", 1500),
    ("Кроссовки", 1500),
]


def calc_categories(cart: list = None) -> InlineKeyboardMarkup:
    """
    Кнопки выбора категории товара.
    Если в корзине есть товары — показывает счётчики и кнопку Расчет.
    """
    if cart is None:
        cart = []

    # Считаем количество каждой категории в корзине
    counts = {}
    for item in cart:
        cat = item["category"]
        counts[cat] = counts.get(cat, 0) + 1

    rows = []
    for i in range(0, len(CATEGORIES), 2):
        row = []
        for name, weight in CATEGORIES[i:i + 2]:
            count = counts.get(name, 0)
            label = f"{name} ({weight}г)"
            if count > 0:
                label += f" [{count}]"
            row.append(InlineKeyboardButton(
                text=label,
                callback_data=f"cat_{name}_{weight}"
            ))
        rows.append(row)

    # Кнопка Расчет — только если корзина не пустая
    if cart:
        total = len(cart)
        rows.append([InlineKeyboardButton(
            text=f"🧮 Расчет ({total} поз.)",
            callback_data="calc_compute"
        )])

    # Правка #10: кнопка Назад → возврат к калькулятору
    rows.append([InlineKeyboardButton(text=texts.BTN_BACK, callback_data="calc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calc_delivery(back_target: str = "calc") -> InlineKeyboardMarkup:
    """
    Выбор способа доставки.
    back_target: куда возвращает кнопка Назад.
    Правка #9: кнопка Назад → возврат к калькулятору.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_DELIVERY_AIR, callback_data="delivery_air")],
        [InlineKeyboardButton(text=texts.BTN_DELIVERY_AUTO, callback_data="delivery_auto")],
        [InlineKeyboardButton(text=texts.BTN_DELIVERY_RAIL, callback_data="delivery_rail")],
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data=back_target)],
    ])


def calc_result_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_CALC_AGAIN, callback_data="calc")],
        [InlineKeyboardButton(text=texts.BTN_GO_GUIDE, callback_data="guide")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


# =============================================================
# ULTIMATE GUIDE (правки #3, #4)
# =============================================================

def guide_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        # Правка #3: кнопка ведёт на URL канала отзывов
        [InlineKeyboardButton(text=texts.BTN_VIEW_REVIEWS, url="https://t.me/basefrom50otz")],
        # Правка #3: текст кнопки с тире
        [InlineKeyboardButton(text=texts.BTN_BUY_GUIDE, callback_data="guide_buy")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def payment_buttons(pay_url: str) -> InlineKeyboardMarkup:
    """
    Правка #4: кнопка Назад вместо Главного меню —
    возвращает на экран покупки чтобы снова нажать "Я оплатил".
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_PAY, url=pay_url)],
        [InlineKeyboardButton(text=texts.BTN_PAYMENT_DONE, callback_data="check_payment")],
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data="guide_buy")],
    ])


# =============================================================
# УСЛУГА ВЫКУПА (правка #14)
# =============================================================

def buyout_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        # Правка #14: текст кнопки "Сделать заказ"
        [InlineKeyboardButton(text=texts.BTN_WRITE_TO_OWNER, url=config.PERSONAL_LINK)],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])
