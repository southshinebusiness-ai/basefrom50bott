"""
Конфигурация бота.
Все секреты читаются из .env файла, который НЕ попадает в git.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Токен бота от @BotFather
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Telegram ID админа (твой ID)
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

    # Username основного канала (без @) для проверки подписки
    MAIN_CHANNEL_USERNAME: str = os.getenv("MAIN_CHANNEL_USERNAME", "basefrom50")

    # ID закрытого канала с материалами ULTIMATE GUIDE
    PRIVATE_CHANNEL_ID: int = int(os.getenv("PRIVATE_CHANNEL_ID", "-1003552231781"))

    # YooMoney
    YOOMONEY_WALLET: str = os.getenv("YOOMONEY_WALLET", "4100118793697883")
    YOOMONEY_TOKEN: str = os.getenv("YOOMONEY_TOKEN", "")

    # Цены продуктов в рублях
    PRICE_ULTIMATE_GUIDE: int = 5990
    PRICE_BUYOUT_SERVICE: int = 2200

    # Ссылки
    PERSONAL_LINK: str = "https://t.me/mmarsellus"
    MAIN_CHANNEL_LINK: str = "https://t.me/basefrom50"
    REVIEWS_CHANNEL_LINK: str = "https://t.me/basefrom50otz"
    YOUTUBE_LINK: str = os.getenv("YOUTUBE_LINK", "")
    TIKTOK_LINK: str = os.getenv("TIKTOK_LINK", "")

    # Файл базы данных
    DB_PATH: str = "data/bot.db"


config = Config()
