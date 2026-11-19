"""
Главное меню. Отправляет баннер при открытии.
"""
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from config import config

from db import database as db
from utils.keyboards import main_menu
from content import texts

router = Router()
BANNER = Path("content/images/banner_menu_final.png")

# Telegram uploads from the admin are stored next to the persistent bot DB,
# so a service restart or source update does not erase the chosen banner.
CUSTOM_BANNER_PNG = Path(config.DB_PATH).parent / "menu_banner_custom.png"
CUSTOM_BANNER_JPG = Path(config.DB_PATH).parent / "menu_banner_custom.jpg"


def active_banner() -> Path:
    for path in (CUSTOM_BANNER_PNG, CUSTOM_BANNER_JPG, BANNER):
        if path.is_file():
            return path
    return BANNER


async def _save_admin_banner(message: Message, bot: Bot):
    if not message.from_user or message.from_user.id != config.ADMIN_ID:
        return
    attachment = message.document or (message.photo[-1] if message.photo else None)
    if attachment is None:
        await message.answer(
            "Пришли картинку PNG/JPG как фото или файл с подписью /setmenu. "
            "Также можно ответить командой /setmenu на картинку."
        )
        return
    if message.document and message.document.file_size and message.document.file_size > 10_000_000:
        await message.answer("Файл слишком большой (максимум 10 МБ).")
        return

    CUSTOM_BANNER_PNG.parent.mkdir(parents=True, exist_ok=True)
    tmp = CUSTOM_BANNER_PNG.with_suffix(".uploading")
    try:
        await bot.download(attachment, destination=tmp)
        with tmp.open("rb") as f:
            signature = f.read(8)
        if signature.startswith(bytes.fromhex("89504e470d0a1a0a")):
            target, other = CUSTOM_BANNER_PNG, CUSTOM_BANNER_JPG
        elif signature.startswith(bytes.fromhex("ffd8ff")):
            target, other = CUSTOM_BANNER_JPG, CUSTOM_BANNER_PNG
        else:
            await message.answer("Поддерживаются только изображения PNG или JPG.")
            return
        tmp.replace(target)
        other.unlink(missing_ok=True)
    except Exception:
        await message.answer("Не удалось сохранить баннер. Попробуй отправить ещё раз.")
        raise
    finally:
        tmp.unlink(missing_ok=True)
    await message.answer("Готово! Картинка главного меню заменена. Открой /start для проверки.")


@router.message(F.photo, F.caption == "/setmenu")
@router.message(F.document, F.caption == "/setmenu")
async def set_menu_from_caption(message: Message, bot: Bot):
    await _save_admin_banner(message, bot)


@router.message(Command("setmenu"))
async def set_menu_from_reply(message: Message, bot: Bot):
    if not message.from_user or message.from_user.id != config.ADMIN_ID:
        return
    await _save_admin_banner(message.reply_to_message or message, bot)



async def _send_menu(bot: Bot, chat_id: int, state: FSMContext):
    """Удаляет все баннеры (menu, calc, buyout), шлёт новый + меню."""
    data = await state.get_data()
    # Удаляем все возможные баннеры из разных разделов
    for key in ("banner_msg_id", "calc_banner_id"):
        bid = data.get(key)
        if bid:
            try:
                await bot.delete_message(chat_id, bid)
            except Exception:
                pass

    banner_id = None
    banner = active_banner()
    if banner.exists():
        try:
            msg = await bot.send_photo(chat_id, FSInputFile(banner))
            banner_id = msg.message_id
        except Exception:
            # If the custom banner is damaged, fall back to the original.
            if banner != BANNER and BANNER.exists():
                try:
                    msg = await bot.send_photo(chat_id, FSInputFile(BANNER))
                    banner_id = msg.message_id
                except Exception:
                    pass

    await state.update_data(banner_msg_id=banner_id)
    await bot.send_message(
        chat_id, texts.WELCOME,
        reply_markup=main_menu(), parse_mode="HTML"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or ""
    )
    payload = ""
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            payload = parts[1].strip()

    if payload:
        await db.log_event(message.from_user.id, "start", {"payload": payload})
    else:
        await db.log_event(message.from_user.id, "start")

    if payload == "ultimate_guide":
        # Кликабельная кнопка в PDF должна вести сразу в ULTIMATE,
        # а не возвращать пользователя в главное меню.
        from handlers.guide import send_guide_screen
        await send_guide_screen(
            bot=bot,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            state=state,
        )
        return

    await _send_menu(bot, message.chat.id, state)


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext, bot: Bot):
    chat_id = callback.message.chat.id
    # Удаляем текущее сообщение (текстовое)
    try:
        await bot.delete_message(chat_id, callback.message.message_id)
    except Exception:
        pass
    await _send_menu(bot, chat_id, state)
    await callback.answer()
