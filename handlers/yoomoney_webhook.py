"""
Обработчик HTTP-уведомлений от YooMoney.

Когда юзер оплачивает → YooMoney делает POST на наш сервер.
Мы проверяем подпись, находим юзера по label, выдаём доступ автоматически.
"""
import hashlib
import logging
from datetime import datetime, timedelta

from aiohttp import web

from db import database as db
from config import config

logger = logging.getLogger(__name__)


def verify_signature(data: dict, secret: str) -> bool:
    """
    Проверяет подпись YooMoney уведомления.
    Строка для хэша: поля через & в определённом порядке.
    """
    string_to_hash = "&".join([
        data.get("notification_type", ""),
        data.get("operation_id", ""),
        data.get("amount", ""),
        data.get("currency", ""),
        data.get("datetime", ""),
        data.get("sender", ""),
        data.get("codepro", ""),
        secret,
        data.get("label", ""),
    ])
    expected = hashlib.sha1(string_to_hash.encode("utf-8")).hexdigest()
    received = data.get("sha1_hash", "")
    return expected == received


def extract_user_id_from_label(label: str) -> int | None:
    """
    Извлекает user_id из label вида bf50_USER_ID_TIMESTAMP.
    """
    try:
        parts = label.split("_")
        if len(parts) >= 3 and parts[0] == "bf50":
            return int(parts[1])
    except (ValueError, IndexError):
        pass
    return None


async def handle_yoomoney_notify(request: web.Request) -> web.Response:
    """
    Принимает POST-уведомление от YooMoney и автоматически
    выдаёт доступ к гайду юзеру который оплатил.
    """
    try:
        data = dict(await request.post())
        logger.info(f"YooMoney webhook: {data}")

        # Проверяем подпись
        if not verify_signature(data, config.YOOMONEY_SECRET):
            logger.warning("YooMoney webhook: неверная подпись!")
            return web.Response(status=400, text="bad signature")

        label = data.get("label", "")
        amount = float(data.get("amount", 0))
        operation_id = data.get("operation_id", "")

        logger.info(f"Оплата подтверждена: label={label}, amount={amount}")

        # Находим юзера по label
        user_id = extract_user_id_from_label(label)
        if not user_id:
            logger.warning(f"Не удалось извлечь user_id из label: {label}")
            return web.Response(status=200, text="ok")

        # Проверяем что уже не выдавали доступ по этому label
        payment = await db.get_payment_by_label(label)
        if payment and payment.get("status") == "completed":
            logger.info(f"Платёж {label} уже обработан, пропускаем")
            return web.Response(status=200, text="ok")

        # Отмечаем оплату в БД
        await db.mark_payment_completed(label, operation_id)
        await db.mark_purchased(user_id)
        await db.log_event(user_id, "guide_purchased_webhook", {
            "label": label, "amount": amount, "operation_id": operation_id
        })

        # Получаем бота из контекста приложения
        bot = request.app["bot"]

        # Создаём invite-ссылку с join request
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=config.PRIVATE_CHANNEL_ID,
                creates_join_request=True,
                expire_date=datetime.now() + timedelta(days=3),
                name=f"Payment {user_id}"
            )
            invite_link = invite.invite_link

            await bot.send_message(
                user_id,
                f"✅ <b>Оплата получена! Welcome, manigg!</b>\n\n"
                f"Жми на ссылку → нажми 'Отправить запрос' → "
                f"бот автоматически одобрит вступление:\n\n"
                f"👉 {invite_link}\n\n"
                f"get rich or die tryin' 💀",
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        except Exception as e:
            logger.error(f"Ошибка отправки доступа юзеру {user_id}: {e}")
            # Сообщаем админу
            try:
                await bot.send_message(
                    config.ADMIN_ID,
                    f"⚠️ Юзер {user_id} оплатил, но не удалось отправить ссылку.\n"
                    f"Ошибка: {e}\n"
                    f"Используй /grant {user_id}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return web.Response(status=200, text="ok")

        # Уведомляем админа о продаже
        try:
            await bot.send_message(
                config.ADMIN_ID,
                f"💰 <b>НОВАЯ ПРОДАЖА!</b>\n\n"
                f"Юзер ID: {user_id}\n"
                f"Сумма: {amount}₽\n"
                f"Label: {label}",
                parse_mode="HTML"
            )
        except Exception:
            pass

        return web.Response(status=200, text="ok")

    except Exception as e:
        logger.error(f"Ошибка обработки YooMoney webhook: {e}")
        return web.Response(status=200, text="ok")  # Всегда 200 чтобы YooMoney не ретраил
