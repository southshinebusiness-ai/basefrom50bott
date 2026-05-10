"""
Точка входа бота @basefrom50bot.
Запускает одновременно:
- Telegram bot (aiogram polling)
- HTTP web server (aiohttp) для приёма YooMoney webhook уведомлений
"""
import asyncio
import logging
import os
import socket
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from db import database
from handlers import main_menu, start_rf, calculator, guide, simple, admin, join_request
from handlers.yoomoney_webhook import handle_yoomoney_notify


def make_ipv4_session() -> AiohttpSession:
    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET
    return session


def create_web_app(bot: Bot) -> web.Application:
    """Создаёт aiohttp веб-приложение для приёма YooMoney уведомлений."""
    app = web.Application()
    app["bot"] = bot  # Передаём бота в контекст для отправки сообщений
    app.router.add_post("/yoomoney/notify", handle_yoomoney_notify)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))  # Healthcheck для Railway
    return app


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if not config.BOT_TOKEN:
        print("BOT_TOKEN не задан")
        sys.exit(1)
    if not config.ADMIN_ID:
        print("ADMIN_ID не задан")
        sys.exit(1)

    os.makedirs("data", exist_ok=True)
    await database.init_db()
    logging.info("База данных готова")

    # Создаём бота
    bot = Bot(
        token=config.BOT_TOKEN,
        session=make_ipv4_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Настраиваем диспетчер
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(join_request.router)
    dp.include_router(main_menu.router)
    dp.include_router(start_rf.router)
    dp.include_router(calculator.router)
    dp.include_router(guide.router)
    dp.include_router(simple.router)

    # Настраиваем веб-сервер для YooMoney webhook
    web_app = create_web_app(bot)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {config.PORT}")
    logging.info(f"YooMoney webhook: http://0.0.0.0:{config.PORT}/yoomoney/notify")

    # Запускаем бота
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logging.info(f"Бот @{me.username} запущен. Polling started.")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
