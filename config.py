"""
Конфигурация бота.
Все секреты читаются из .env файла / переменных Railway.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv
load_dotenv()

@dataclass
class Config:
    # Токен бота от @BotFather
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    # Telegram ID админа
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    # Username основного канала для проверки подписки
    MAIN_CHANNEL_USERNAME: str = os.getenv("MAIN_CHANNEL_USERNAME", "basefrom50")
    # ID закрытого канала с материалами ULTIMATE GUIDE
    PRIVATE_CHANNEL_ID: int = int(os.getenv("PRIVATE_CHANNEL_ID", "-1003552231781"))
    # YooMoney
    YOOMONEY_WALLET: str = os.getenv("YOOMONEY_WALLET", "4100118793697883")
    YOOMONEY_TOKEN: str = os.getenv("YOOMONEY_TOKEN", "")
    YOOMONEY_SECRET: str = os.getenv("YOOMONEY_SECRET", "")
    # Цены — читается из Railway переменной PRICE_ULTIMATE_GUIDE
    PRICE_ULTIMATE_GUIDE: int = int(os.getenv("PRICE_ULTIMATE_GUIDE", "5990"))
    # Курс доллара для расчёта доставки (3.5$/кг)
    DOLLAR_RATE: float = float(os.getenv("DOLLAR_RATE", "80.5"))
    YUAN_RATE:   float = float(os.getenv("YUAN_RATE", "12.0"))
    # Ссылки
    PERSONAL_LINK: str = "https://t.me/mmarsellus"
    MAIN_CHANNEL_LINK: str = "https://t.me/basefrom50"
    REVIEWS_CHANNEL_LINK: str = "https://t.me/basefrom50otz"
    YOUTUBE_LINK: str = os.getenv("YOUTUBE_LINK", "")
    TIKTOK_LINK: str = os.getenv("TIKTOK_LINK", "")
    # База данных
    DB_PATH: str = "data/bot.db"
    # Порт для веб-сервера
    PORT: int = int(os.getenv("PORT", "8080"))

config = Config()
