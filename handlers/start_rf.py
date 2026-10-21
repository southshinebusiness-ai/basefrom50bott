"""Бесплатный гайд — мгновенная выдача PDF без мини-курса."""
import base64
import hashlib
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from db import database as db
from config import config

router = Router()

# Старый сжатый PDF оставляем только как резерв.
PDF_PATH = Path("content/pdfs/basefrom50_free_guide.pdf")
LEGACY_PDF_PATH = Path("content/pdfs/basefrom50_start_rf.pdf")

# Полноразмерный V3 хранится в репозитории частями в base64, чтобы не пережимать
# изображения. При первом запросе собираем исходный PDF побайтно в /tmp.
FULL_QUALITY_PARTS_DIR = Path("content/pdfs/basefrom50_free_guide_parts")
FULL_QUALITY_CACHE_PATH = Path("/tmp/basefrom50_free_guide_v3.pdf")
FULL_QUALITY_SIZE = 19981090
FULL_QUALITY_SHA256 = "3ef746a16c4502c87b54802af87cc8cbba2b725ed31c31d07d884cc21566c0c0"


def _is_valid_full_quality_pdf(path: Path) -> bool:
    try:
        if not path.exists() or path.stat().st_size != FULL_QUALITY_SIZE:
            return False
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest == FULL_QUALITY_SHA256
    except Exception:
        return False


def _get_full_quality_guide() -> Path | None:
    """Собирает точную V3-версию из частей и возвращает путь к ней."""
    if _is_valid_full_quality_pdf(FULL_QUALITY_CACHE_PATH):
        return FULL_QUALITY_CACHE_PATH

    try:
        parts = sorted(FULL_QUALITY_PARTS_DIR.glob("part_*.b64"))
        if not parts:
            return None

        encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
        pdf_bytes = base64.b64decode(encoded, validate=True)

        if len(pdf_bytes) != FULL_QUALITY_SIZE:
            return None
        if hashlib.sha256(pdf_bytes).hexdigest() != FULL_QUALITY_SHA256:
            return None

        FULL_QUALITY_CACHE_PATH.write_bytes(pdf_bytes)
        return FULL_QUALITY_CACHE_PATH
    except Exception:
        return None


def after_guide_menu() -> InlineKeyboardMarkup:
    """Следующий шаг после выдачи бесплатного гайда."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 ULTIMATE GUIDE", callback_data="guide")],
        [InlineKeyboardButton(text="📲 Основной канал", url=config.MAIN_CHANNEL_LINK)],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")],
    ])


async def _send_free_guide(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    await db.log_event(user_id, "free_guide_opened")

    # Удаляем старый баннер и сообщение меню, чтобы выдача выглядела чисто.
    data = await state.get_data()
    for key in ("banner_msg_id", "calc_banner_id"):
        msg_id = data.get(key)
        if msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()

    # В первую очередь отправляем исходный V3 без пережатия.
    guide_path = _get_full_quality_guide()
    if guide_path is None:
        guide_path = PDF_PATH if PDF_PATH.exists() else LEGACY_PDF_PATH

    if not guide_path.exists():
        await bot.send_message(
            chat_id,
            "Не удалось загрузить бесплатный гайд. Попробуй чуть позже.",
        )
        await db.log_event(user_id, "free_guide_missing")
        await callback.answer()
        return

    await bot.send_document(
        chat_id,
        FSInputFile(guide_path, filename="BASE_FROM_50_FREE_GUIDE.pdf"),
        caption=(
            "📖 <b>Бесплатный гайд BASE FROM 50</b>\n\n"
            "Как покупать вещи из Китая напрямую — без российских посредников и лишней наценки.\n\n"
            "<b>Ссылки на товары из гайда:</b>\n"
            '<a href="https://item.taobao.com/item.htm?id=1086416018195&amp;skuId=6306416471756">Куртка Jaded London</a>\n'
            '<a href="https://item.taobao.com/item.htm?id=941099471173&amp;skuId=5840465488524">Кеды Maison Margiela</a>\n'
            '<a href="https://item.taobao.com/item.htm?id=925791280757&amp;skuId=5803951976591">Худи True Religion</a>'
        ),
        parse_mode="HTML",
    )
    await db.log_event(user_id, "free_guide_sent")

    await bot.send_message(
        chat_id,
        "Гайд у тебя ✅\n\n"
        "Если хочешь не просто понять принцип, а получить готовую систему — "
        "поставщиков, площадки, доставку, калькуляторы и материалы — открой <b>ULTIMATE GUIDE</b>.",
        reply_markup=after_guide_menu(),
        parse_mode="HTML",
    )
    await callback.answer("Гайд отправлен ✅")


@router.callback_query(F.data == "free_guide")
async def send_free_guide(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await _send_free_guide(callback, bot, state)


# Совместимость со старыми сообщениями бота:
# прежняя кнопка "start_rf" теперь тоже сразу выдаёт новый бесплатный гайд.
@router.callback_query(F.data == "start_rf")
async def legacy_start_rf(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await _send_free_guide(callback, bot, state)
