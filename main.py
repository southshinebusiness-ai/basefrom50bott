"""
Точка входа бота @basefrom50bot.
Запуск: python main.py
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from db import database
from handlers import main_menu, start_rf, calculator, guide, simple, admin


async def main():
    # Логирование в файл и в консоль
import os
    os.makedirs("data", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )

    # Проверка обязательных настроек
    if not config.BOT_TOKEN:
        print("❌ BOT_TOKEN не задан в .env файле")
        sys.exit(1)
    if not config.ADMIN_ID:
        print("❌ ADMIN_ID не задан в .env файле")
        sys.exit(1)

    # Инициализация БД
    await database.init_db()
    logging.info("База данных готова")

    # Создаём бота и диспетчер
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем хендлеры (порядок важен — admin первый чтобы команды перехватывались)
    dp.include_router(admin.router)
    dp.include_router(main_menu.router)
    dp.include_router(start_rf.router)
    dp.include_router(calculator.router)
    dp.include_router(guide.router)
    dp.include_router(simple.router)

    # Удаляем webhook если был и стартуем polling
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logging.info(f"Бот @{me.username} запущен. Polling started.")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
