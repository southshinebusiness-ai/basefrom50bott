"""Read-only fallback to YooMoney wallet API (operation-history scope)."""
import logging

import aiohttp

from config import config
from utils.yoomoney import validate_history_operation

logger = logging.getLogger(__name__)
HISTORY_URL = "https://yoomoney.ru/api/operation-history"


class YooMoneyAPIError(Exception):
    pass


async def find_confirmed_operation(payment: dict) -> dict | None:
    """Ищет только входящую завершённую операцию по точному label заказа.

    При отсутствии токена fallback недоступен. Не выдаём доступ без
    подтверждения в официальном API кошелька.
    """
    if not config.YOOMONEY_TOKEN:
        raise YooMoneyAPIError("YOOMONEY_TOKEN не настроен")

    timeout = aiohttp.ClientTimeout(total=10)
    headers = {"Authorization": f"Bearer {config.YOOMONEY_TOKEN}"}
    data = {"label": payment["label"], "records": "100"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # На случай нескольких записей с тем же label поддерживаем пагинацию.
            for _ in range(3):
                async with session.post(
                    HISTORY_URL, headers=headers, data=data
                ) as response:
                    if response.status != 200:
                        raise YooMoneyAPIError(
                            f"ЮMoney API HTTP {response.status}"
                        )
                    result = await response.json(content_type=None)

                if not isinstance(result, dict) or result.get("error"):
                    raise YooMoneyAPIError(
                        f"ЮMoney API: {result.get('error', 'invalid response') if isinstance(result, dict) else 'invalid response'}"
                    )
                operations = result.get("operations")
                if not isinstance(operations, list):
                    raise YooMoneyAPIError("ЮMoney API вернул некорректную историю")
                for operation in operations:
                    if isinstance(operation, dict) and validate_history_operation(operation, payment):
                        return operation

                next_record = result.get("next_record")
                if next_record is None:
                    return None
                data["start_record"] = str(next_record)
        return None
    except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
        logger.warning("YooMoney history request failed: %s", type(exc).__name__)
        raise YooMoneyAPIError("Временная ошибка API ЮMoney") from exc
