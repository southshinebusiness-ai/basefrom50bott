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
                completed_at TIMESTAMP
            )
        """)

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


async def mark_payment_completed(label: str, operation_id: str):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute("""
            UPDATE payments
            SET status = 'completed',
                operation_id = ?,
                completed_at = CURRENT_TIMESTAMP
            WHERE label = ?
        """, (operation_id, label))
        await db.commit()


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
