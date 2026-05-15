"""
Inline-клавиатуры бота.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from content import texts
from config import config


def main_menu() -> InlineKeyboardMarkup:
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


def check_subscription() -> InlineKeyboardMarkup:
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


# Правка #1: кнопки навигации по урокам (назад + вперёд)
def lesson_nav(lesson_num: int, total: int = 5) -> InlineKeyboardMarkup:
    """
    Для уроков 1..total-1: кнопка вперёд (и назад если не первый).
    Для последнего урока: кнопка назад + получить PDF.
    """
    rows = []

    if lesson_num < total:
        # Промежуточный урок
        nav_row = []
        if lesson_num > 1:
            nav_row.append(InlineKeyboardButton(
                text="← Назад",
                callback_data=f"lesson_{lesson_num - 1}"
            ))
        nav_row.append(InlineKeyboardButton(
            text="Дальше →",
            callback_data=f"lesson_{lesson_num + 1}"
        ))
        rows.append(nav_row)
    else:
        # Последний урок
        rows.append([InlineKeyboardButton(text="← Назад", callback_data=f"lesson_{lesson_num - 1}")])
        rows.append([InlineKeyboardButton(text=texts.BTN_GET_PDF, callback_data="get_pdfs")])
        rows.append([InlineKeyboardButton(text=texts.BTN_GO_GUIDE, callback_data="guide")])

    rows.append([InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def finish_course() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_GET_PDF, callback_data="get_pdfs")],
        [InlineKeyboardButton(text=texts.BTN_GO_GUIDE, callback_data="guide")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def calc_mode_choice() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_CALC_BY_CATEGORY, callback_data="calc_cat")],
        [InlineKeyboardButton(text=texts.BTN_CALC_MANUAL, callback_data="calc_manual")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


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
    if cart is None:
        cart = []

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

    if cart:
        total = len(cart)
        rows.append([InlineKeyboardButton(
            text=f"🧮 Расчет ({total} поз.)",
            callback_data="calc_compute"
        )])

    rows.append([InlineKeyboardButton(text=texts.BTN_BACK, callback_data="calc")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calc_delivery(back_target: str = "calc") -> InlineKeyboardMarkup:
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


def guide_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_VIEW_REVIEWS, url="https://t.me/basefrom50otz")],
        [InlineKeyboardButton(text=texts.BTN_BUY_GUIDE, callback_data="guide_buy")],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])


def payment_buttons(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_PAY, url=pay_url)],
        [InlineKeyboardButton(text=texts.BTN_PAYMENT_DONE, callback_data="check_payment")],
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data="guide")],  # назад к описанию гайда
    ])


def buyout_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_WRITE_TO_OWNER, url=config.PERSONAL_LINK)],
        [InlineKeyboardButton(text=texts.BTN_BACK_MAIN, callback_data="main_menu")],
    ])
