"""
Inline-клавиатуры бота.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from content import texts
from config import config


def main_menu() -> InlineKeyboardMarkup:
    """Главное меню — 5 кнопок."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_START_RF, callback_data="start_rf")],
        [InlineKeyboardButton(text=texts.BTN_CALCULATOR, callback_data="calc")],
        [InlineKeyboardButton(text=texts.BTN_GUIDE, callback_data="guide")],
        [InlineKeyboardButton(text=texts.BTN_BUYOUT, callback_data="buyout")],
        [InlineKeyboardButton(text=texts.BTN_CONTACTS, callback_data="contacts")],
    ])


def back_to_main() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def check_subscription() -> InlineKeyboardMarkup:
    """Кнопки 'Перейти на канал' + 'Я подписался'."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_GO_CHANNEL, url=config.MAIN_CHANNEL_LINK)],
        [InlineKeyboardButton(text=texts.BTN_CHECK_SUBSCRIPTION, callback_data="check_sub")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def start_course() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_START_COURSE, callback_data="lesson_1")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def next_lesson(current_lesson: int) -> InlineKeyboardMarkup:
    """Кнопка перехода к следующему уроку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_NEXT_LESSON, callback_data=f"lesson_{current_lesson + 1}")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def finish_course() -> InlineKeyboardMarkup:
    """Кнопки в конце курса."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_GET_PDF, callback_data="get_pdfs")],
        [InlineKeyboardButton(text=texts.BTN_GO_GUIDE, callback_data="guide")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


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


def calc_categories() -> InlineKeyboardMarkup:
    """Кнопки выбора категории товара."""
    rows = []
    # По 2 кнопки в ряд
    for i in range(0, len(CATEGORIES), 2):
        row = []
        for name, weight in CATEGORIES[i:i+2]:
            row.append(InlineKeyboardButton(
                text=f"{name} ({weight}г)",
                callback_data=f"cat_{name}_{weight}"
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calc_delivery() -> InlineKeyboardMarkup:
    """Выбор способа доставки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_DELIVERY_AIR, callback_data="delivery_air")],
        [InlineKeyboardButton(text=texts.BTN_DELIVERY_AUTO, callback_data="delivery_auto")],
        [InlineKeyboardButton(text=texts.BTN_DELIVERY_RAIL, callback_data="delivery_rail")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def calc_result_buttons() -> InlineKeyboardMarkup:
    """Кнопки после результата калькулятора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_CALC_AGAIN, callback_data="calc")],
        [InlineKeyboardButton(text=texts.BTN_GO_GUIDE, callback_data="guide")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def guide_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_VIEW_REVIEWS, callback_data="guide_reviews")],
        [InlineKeyboardButton(text=texts.BTN_BUY_GUIDE, callback_data="guide_buy")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def guide_reviews_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_BUY_GUIDE, callback_data="guide_buy")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def payment_buttons(pay_url: str) -> InlineKeyboardMarkup:
    """Кнопки 'Оплатить' (внешняя ссылка) + 'Я оплатил' (callback)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_PAY, url=pay_url)],
        [InlineKeyboardButton(text=texts.BTN_PAYMENT_DONE, callback_data="check_payment")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def buyout_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_WRITE_TO_OWNER, url=config.PERSONAL_LINK)],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])
