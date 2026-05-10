"""
Вспомогательные функции.
"""
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from config import config


async def is_subscribed_to_channel(bot: Bot, user_id: int) -> bool:
    """Проверяет подписан ли юзер на основной канал."""
    try:
        member = await bot.get_chat_member(
            chat_id=f"@{config.MAIN_CHANNEL_USERNAME}",
            user_id=user_id
        )
        return member.status in ("creator", "administrator", "member")
    except TelegramAPIError:
        return False


def get_cargo_delivery_cost(price_yuan: float) -> int:
    """
    Стоимость доставки от поставщика до склада карго.
    Правка #8: 10¥ до 1000 юаней, 20¥ от 2000 юаней.
    """
    if price_yuan >= 2000:
        return 20
    return 10


def calculate_price(price_yuan: float, weight_g: int, delivery_type: str, yuan_rate: float) -> dict:
    """
    Считает стоимость товара с доставкой до Москвы.
    delivery_type: 'air' (500₽/кг), 'auto' (350₽/кг), 'rail' (280₽/кг)
    """
    DELIVERY_TARIFFS = {
        "air": (500, "Авиа", "✈️"),
        "auto": (350, "Авто", "🚛"),
        "rail": (280, "ЖД", "🚂"),
    }

    tariff, delivery_name, delivery_emoji = DELIVERY_TARIFFS[delivery_type]

    # Правка #8: стоимость доставки до карго зависит от суммы заказа
    cargo_delivery = get_cargo_delivery_cost(price_yuan)

    # Стоимость товара
    product_cost = round((price_yuan + cargo_delivery) * yuan_rate)

    # Комиссия карго 3%
    commission = round(product_cost * 0.03)

    # Доставка из Китая
    weight_kg = round(weight_g / 1000, 2)
    shipping = round(weight_kg * tariff)

    # Итого
    total = product_cost + commission + shipping

    return {
        "product_cost": product_cost,
        "commission": commission,
        "shipping": shipping,
        "total": total,
        "weight_kg": weight_kg,
        "tariff": tariff,
        "delivery_name": delivery_name,
        "delivery_emoji": delivery_emoji,
        "rate": yuan_rate,
        "cargo_delivery": cargo_delivery,
    }


def calculate_cart_total(cart: list, delivery_type: str, yuan_rate: float) -> dict:
    """
    Считает итоговую стоимость всей корзины.
    cart: список {"category": str, "weight": int, "price_yuan": float}
    """
    DELIVERY_TARIFFS = {
        "air": (500, "Авиа", "✈️"),
        "auto": (350, "Авто", "🚛"),
        "rail": (280, "ЖД", "🚂"),
    }

    tariff, delivery_name, delivery_emoji = DELIVERY_TARIFFS[delivery_type]

    total_product_cost = 0
    total_weight_g = 0

    for item in cart:
        cargo_delivery = get_cargo_delivery_cost(item["price_yuan"])
        item_cost = round((item["price_yuan"] + cargo_delivery) * yuan_rate)
        total_product_cost += item_cost
        total_weight_g += item["weight"]

    commission = round(total_product_cost * 0.03)
    total_weight_kg = round(total_weight_g / 1000, 2)
    shipping = round(total_weight_kg * tariff)
    total = total_product_cost + commission + shipping

    return {
        "total_product_cost": total_product_cost,
        "commission": commission,
        "shipping": shipping,
        "total": total,
        "total_weight_kg": total_weight_kg,
        "item_count": len(cart),
        "tariff": tariff,
        "delivery_name": delivery_name,
        "delivery_emoji": delivery_emoji,
    }


def generate_payment_label(user_id: int) -> str:
    import time
    return f"bf50_{user_id}_{int(time.time())}"


def generate_yoomoney_link(amount: int, label: str, wallet: str) -> str:
    from urllib.parse import urlencode
    params = {
        "receiver": wallet,
        "quickpay-form": "shop",
        "targets": "Оплата ULTIMATE GUIDE",
        "paymentType": "AC",
        "sum": amount,
        "label": label,
    }
    # Важно: confirm.xml (не просто confirm) триггерит HTTP-уведомления
    return f"https://yoomoney.ru/quickpay/confirm.xml?{urlencode(params)}"
