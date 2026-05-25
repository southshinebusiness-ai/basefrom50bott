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


def calculate_price(price_yuan: float, weight_g: int, yuan_rate: float) -> dict:
    """
    Считает стоимость товара с доставкой до Москвы.
    Доставка: 3.5$/кг по курсу config.DOLLAR_RATE.
    """
    cargo_delivery = get_cargo_delivery_cost(price_yuan)
    product_cost   = round((price_yuan + cargo_delivery) * yuan_rate)
    commission     = round(product_cost * 0.03)
    weight_kg      = round(weight_g / 1000, 2)
    rate_per_kg    = round(3.5 * config.DOLLAR_RATE)   # ₽ за кг
    shipping       = round(weight_kg * rate_per_kg)
    total          = product_cost + commission + shipping

    return {
        "product_cost":   product_cost,
        "commission":     commission,
        "shipping":       shipping,
        "total":          total,
        "weight_kg":      weight_kg,
        "rate_per_kg":    rate_per_kg,
        "dollar_rate":    config.DOLLAR_RATE,
        "rate":           yuan_rate,
        "cargo_delivery": cargo_delivery,
    }


def calculate_cart_total(cart: list, yuan_rate: float) -> dict:
    """
    Считает итоговую стоимость корзины.
    cart: список {"category": str, "weight": int, "price_yuan": float}
    """
    total_yuan    = sum(item["price_yuan"] for item in cart)
    total_weight  = sum(item["weight"] for item in cart)
    cargo_del     = get_cargo_delivery_cost(total_yuan)
    product_cost  = round((total_yuan + cargo_del) * yuan_rate)
    commission    = round(product_cost * 0.03)
    weight_kg     = round(total_weight / 1000, 2)
    rate_per_kg   = round(3.5 * config.DOLLAR_RATE)
    shipping      = round(weight_kg * rate_per_kg)
    total         = product_cost + commission + shipping

    return {
        "total_product_cost": product_cost,
        "item_count":         len(cart),
        "total_weight_kg":    weight_kg,
        "commission":         commission,
        "shipping":           shipping,
        "total":              total,
        "rate_per_kg":        rate_per_kg,
        "dollar_rate":        config.DOLLAR_RATE,
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
