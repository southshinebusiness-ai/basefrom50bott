"""
Работа с базой данных SQLite.
Хранит юзеров, события, платежи, настройки.
"""
import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from config import config


async def init_db():
    """Создаёт таблицы при первом запуске."""
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(config.DB_PATH) as db:
        # Юзеры бота
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subscribed_to_channel BOOLEAN DEFAULT 0,
                lesson_progress INTEGER DEFAULT 0,
                course_completed BOOLEAN DEFAULT 0,
                purchased_guide BOOLEAN DEFAULT 0,
                purchased_at TIMESTAMP
            )
        """)

        # Платежи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                product TEXT,
                status TEXT DEFAULT 'pending',
                label TEXT UNIQUE,
                operation_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                delivery_status TEXT NOT NULL DEFAULT 'pending',
                delivery_attempts INTEGER NOT NULL DEFAULT 0,
                delivery_started_at TIMESTAMP,
                delivery_sent_at TIMESTAMP,
                invite_link TEXT,
                last_delivery_error TEXT,
                last_checked_at TIMESTAMP
            )
        """)

        # Миграция существующей SQLite без потери платежей и пользователей.
        cursor = await db.execute("PRAGMA table_info(payments)")
        existing = {row[1] for row in await cursor.fetchall()}
        was_legacy = "delivery_status" not in existing
        new_columns = {
            "delivery_status": "TEXT NOT NULL DEFAULT 'pending'",
            "delivery_attempts": "INTEGER NOT NULL DEFAULT 0",
            "delivery_started_at": "TIMESTAMP",
            "delivery_sent_at": "TIMESTAMP",
            "invite_link": "TEXT",
            "last_delivery_error": "TEXT",
            "last_checked_at": "TIMESTAMP",
        }
        for name, sql_type in new_columns.items():
            if name not in existing:
                await db.execute(f"ALTER TABLE payments ADD COLUMN {name} {sql_type}")

        if was_legacy:
            # Не рассылаем приглашения повторно всем старым покупателям.
            # Старые оплаченные заказы доступны для восстановления вручную.
            await db.execute("""
                UPDATE payments SET delivery_status='legacy'
                WHERE status IN ('completed', 'success')
            """)

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status, created_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_operation ON payments(operation_id)"
        )

        # Настройки (курс юаня и пр.)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # События для аналитики
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Дефолтный курс юаня — 13.6
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("yuan_rate", "13.6")
        )

        await db.commit()


# ============ USERS ============

async def add_user(user_id: int, username: str, first_name: str):
    """Регистрация нового юзера или обновление существующего."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name))
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_lesson_progress(user_id: int, lesson: int):
    """Обновляет прогресс прохождения мини-курса."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET lesson_progress = ? WHERE user_id = ?",
            (lesson, user_id)
        )
        if lesson >= 5:
            await db.execute(
                "UPDATE users SET course_completed = 1 WHERE user_id = ?",
                (user_id,)
            )
        await db.commit()


async def mark_purchased(user_id: int):
    """Отмечает что юзер купил гайд."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET purchased_guide = 1, purchased_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))
        await db.commit()


async def set_subscription_status(user_id: int, is_subscribed: bool):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET subscribed_to_channel = ? WHERE user_id = ?",
            (1 if is_subscribed else 0, user_id)
        )
        await db.commit()


async def get_all_user_ids():
    """Возвращает все user_id для рассылки."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


# ============ SETTINGS ============

async def get_setting(key: str, default: str = "") -> str:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        await db.commit()


async def get_yuan_rate() -> float:
    return float(await get_setting("yuan_rate", "13.6"))


# ============ PAYMENTS ============

async def create_payment(user_id: int, amount: int, product: str, label: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO payments (user_id, amount, product, label)
            VALUES (?, ?, ?, ?)
        """, (user_id, amount, product, label))
        await db.commit()


async def confirm_payment(label: str, operation_id: str):
    """Атомарно подтверждает заказ и право пользователя на доступ.

    Не позволяет использовать один operation_id для разных заказов.
    Повторный webhook с тем же operation_id безопасен.
    """
    if not label or not operation_id:
        return None
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute("SELECT * FROM payments WHERE label = ?", (label,))
        row = await cur.fetchone()
        if not row:
            await conn.rollback()
            return None
        payment = dict(row)
        newly_confirmed = payment["status"] not in ("completed", "success")
        if payment["status"] in ("completed", "success"):
            if payment["operation_id"] != operation_id:
                await conn.rollback()
                return None
        else:
            cur = await conn.execute(
                "SELECT label FROM payments WHERE operation_id = ? AND label <> ?",
                (operation_id, label)
            )
            if await cur.fetchone():
                await conn.rollback()
                return None
            await conn.execute("""
                UPDATE payments SET status='completed', operation_id=?,
                    completed_at=CURRENT_TIMESTAMP
                WHERE label=? AND status='pending'
            """, (operation_id, label))

        await conn.execute("""
            INSERT INTO users (user_id, purchased_guide, purchased_at)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                purchased_guide=1,
                purchased_at=COALESCE(users.purchased_at, CURRENT_TIMESTAMP)
        """, (payment["user_id"],))
        await conn.commit()
        result = await get_payment_by_label(label)
        return {**result, "_newly_confirmed": newly_confirmed}


async def get_latest_payment(user_id: int):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM payments WHERE user_id=? AND product='ultimate_guide' "
            "ORDER BY id DESC LIMIT 1", (user_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def claim_delivery(label: str) -> dict | None:
    """Захватывает право отправить ссылку, не допуская параллельной рассылки."""
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute("""
            SELECT * FROM payments WHERE label=? AND status IN ('completed','success')
            AND (
                delivery_status IN ('pending', 'failed')
                OR (delivery_status='sending'
                    AND datetime(delivery_started_at, '+2 minutes') <= CURRENT_TIMESTAMP)
            )
        """, (label,))
        row = await cur.fetchone()
        if not row:
            await conn.rollback()
            return None
        await conn.execute("""
            UPDATE payments SET delivery_status='sending',
                delivery_started_at=CURRENT_TIMESTAMP,
                delivery_attempts=delivery_attempts+1
            WHERE label=?
        """, (label,))
        await conn.commit()
        return dict(row)


async def save_invite_link(label: str, link: str):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "UPDATE payments SET invite_link=? WHERE label=?", (link, label)
        )
        await conn.commit()


async def mark_delivery_sent(label: str):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("""
            UPDATE payments SET delivery_status='sent',
                delivery_sent_at=CURRENT_TIMESTAMP, last_delivery_error=NULL
            WHERE label=? AND delivery_status='sending'
        """, (label,))
        await conn.commit()


async def mark_delivery_failed(label: str, error: str):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute("""
            UPDATE payments SET delivery_status='failed', last_delivery_error=?
            WHERE label=? AND delivery_status='sending'
        """, (error[:300], label))
        await conn.commit()


async def get_pending_deliveries(limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("""
            SELECT * FROM payments WHERE status IN ('completed','success')
                AND delivery_attempts < 5
                AND (
                    delivery_status IN ('pending','failed')
                    OR (delivery_status='sending'
                        AND datetime(delivery_started_at, '+2 minutes') <= CURRENT_TIMESTAMP)
                )
            ORDER BY completed_at ASC LIMIT ?
        """, (limit,))
        return [dict(row) for row in await cur.fetchall()]


async def get_pending_for_reconciliation(limit: int = 10):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("""
            SELECT * FROM payments WHERE status='pending'
                AND created_at >= datetime('now', '-7 days')
                AND created_at <= datetime('now', '-30 seconds')
                AND (
                    last_checked_at IS NULL
                    OR last_checked_at <= datetime('now', '-5 minutes')
                )
            ORDER BY COALESCE(last_checked_at, '1970-01-01') ASC, id DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in await cur.fetchall()]


async def mark_payment_checked(label: str):
    async with aiosqlite.connect(config.DB_PATH) as conn:
        await conn.execute(
            "UPDATE payments SET last_checked_at=CURRENT_TIMESTAMP WHERE label=?",
            (label,)
        )
        await conn.commit()


async def get_payment_by_label(label: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM payments WHERE label = ?", (label,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ============ EVENTS ============

async def log_event(user_id: int, event_type: str, data: dict = None):
    """Логирует событие для аналитики."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            INSERT INTO events (user_id, event_type, data)
            VALUES (?, ?, ?)
        """, (user_id, event_type, json.dumps(data or {}, ensure_ascii=False)))
        await db.commit()


# ============ STATS ============

async def get_stats():
    """Статистика для админа."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        stats = {}

        cursor = await db.execute("SELECT COUNT(*) FROM users")
        stats['total_users'] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at > datetime('now', '-1 day')"
        )
        stats['new_today'] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE joined_at > datetime('now', '-7 days')"
        )
        stats['new_week'] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE course_completed = 1"
        )
        stats['course_completed'] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE purchased_guide = 1"
        )
        stats['purchased_guide'] = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'"
        )
        stats['total_revenue'] = (await cursor.fetchone())[0]

        return stats
