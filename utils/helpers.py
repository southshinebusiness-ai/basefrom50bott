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
        # Подписан если статус один из: creator, administrator, member
        return member.status in ("creator", "administrator", "member")
    except TelegramAPIError:
        # Если бот не админ канала или канал недоступен — считаем что не подписан
        return False


def calculate_price(price_yuan: float, weight_g: int, delivery_type: str, yuan_rate: float) -> dict:
    """
    Считает стоимость товара с доставкой до Москвы.
    Возвращает разбивку для красивого вывода.

    delivery_type: 'air' (500₽/кг), 'auto' (350₽/кг), 'rail' (280₽/кг)
    """
    DELIVERY_TARIFFS = {
        "air": (500, "Авиа", "✈️"),
        "auto": (350, "Авто", "🚛"),
        "rail": (280, "ЖД", "🚂"),
    }

    tariff, delivery_name, delivery_emoji = DELIVERY_TARIFFS[delivery_type]

    # Стоимость товара: цена в юанях + 8¥ доставка до карго склада
    product_cost = round((price_yuan + 8) * yuan_rate)

    # Комиссия карго 3%
    commission = round(product_cost * 0.03)

    # Доставка из Китая
    weight_kg = weight_g / 1000
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
    }


def generate_payment_label(user_id: int) -> str:
    """Уникальный label для платежа: bf50_USERID_TIMESTAMP."""
    import time
    return f"bf50_{user_id}_{int(time.time())}"


def generate_yoomoney_link(amount: int, label: str, wallet: str) -> str:
    """Генерит ссылку на быструю оплату YooMoney."""
    from urllib.parse import urlencode
    params = {
        "receiver": wallet,
        "quickpay-form": "shop",
        "targets": "Оплата ULTIMATE GUIDE",
        "paymentType": "AC",
        "sum": amount,
        "label": label,
    }
    return f"https://yoomoney.ru/quickpay/confirm?{urlencode(params)}"
