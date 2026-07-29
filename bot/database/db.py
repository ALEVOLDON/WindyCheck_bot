import os
import json
import logging
import aiosqlite
from config import DB_PATH, DATA_FILE_JSON

logger = logging.getLogger(__name__)

async def init_db():
    """Инициализация таблиц базы данных SQLite."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                last_city TEXT DEFAULT 'Санкт-Петербург',
                alerts_enabled INTEGER DEFAULT 0,
                alerts_threshold REAL DEFAULT 15.0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_cities (
                user_id INTEGER,
                city TEXT,
                PRIMARY KEY (user_id, city)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wind_history (
                user_id INTEGER,
                city TEXT,
                timestamp TEXT,
                speed REAL,
                deg INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS last_alerts (
                user_id INTEGER,
                city TEXT,
                timestamp TEXT,
                PRIMARY KEY (user_id, city)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weekly_cache (
                user_id INTEGER,
                city TEXT,
                timestamp TEXT,
                text TEXT,
                PRIMARY KEY (user_id, city)
            )
        """)
        await db.commit()
    logger.info("База данных SQLite инициализирована.")
    await migrate_from_json()

async def migrate_from_json():
    """Автоматическая миграция старых данных из user_data.json в user_data.db при первом запуске."""
    if not os.path.exists(DATA_FILE_JSON):
        return

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            count = (await cursor.fetchone())[0]
            if count > 0:
                return  # База уже содержит пользователей

            logger.info("Обнаружен файл user_data.json, начинаем миграцию в SQLite...")
            with open(DATA_FILE_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)

            for uid_str, u_dict in data.items():
                uid = int(uid_str)
                last_city = u_dict.get("last_city", "Санкт-Петербург")
                alerts = u_dict.get("alerts", {})
                alerts_enabled = 1 if alerts.get("enabled") else 0
                alerts_threshold = alerts.get("threshold", 15.0)

                await db.execute(
                    "INSERT OR REPLACE INTO users (user_id, last_city, alerts_enabled, alerts_threshold) VALUES (?, ?, ?, ?)",
                    (uid, last_city, alerts_enabled, alerts_threshold)
                )

                for city in u_dict.get("cities", []):
                    await db.execute(
                        "INSERT OR IGNORE INTO user_cities (user_id, city) VALUES (?, ?)",
                        (uid, city)
                    )

                for city_key, hist_list in u_dict.get("wind_history", {}).items():
                    for entry in hist_list:
                        if len(entry) == 3:
                            ts_str, speed, deg = entry
                            await db.execute(
                                "INSERT INTO wind_history (user_id, city, timestamp, speed, deg) VALUES (?, ?, ?, ?, ?)",
                                (uid, city_key, ts_str, speed, deg)
                            )

                for city_key, ts_str in u_dict.get("last_alert", {}).items():
                    await db.execute(
                        "INSERT OR REPLACE INTO last_alerts (user_id, city, timestamp) VALUES (?, ?, ?)",
                        (uid, city_key, ts_str)
                    )

                for city_key, cache_dict in u_dict.get("weekly_cache", {}).items():
                    if isinstance(cache_dict, dict):
                        await db.execute(
                            "INSERT OR REPLACE INTO weekly_cache (user_id, city, timestamp, text) VALUES (?, ?, ?, ?)",
                            (uid, city_key, cache_dict.get("timestamp", ""), cache_dict.get("text", ""))
                        )

            await db.commit()
            logger.info("Миграция данных из user_data.json прошла успешно!")
    except Exception as e:
        logger.error(f"Ошибка миграции из json: {e}")

# ----- ОПЕРАЦИИ С ПОЛЬЗОВАТЕЛЯМИ И ИЗБРАННЫМ -----

async def ensure_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def get_user_last_city(user_id: int) -> str:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT last_city FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row and row[0] else "Санкт-Петербург"

async def set_user_last_city(user_id: int, city: str):
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET last_city = ? WHERE user_id = ?", (city, user_id))
        await db.commit()

async def get_user_cities(user_id: int) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT city FROM user_cities WHERE user_id = ?", (user_id,))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

async def add_user_city(user_id: int, city: str) -> bool:
    await ensure_user(user_id)
    cities = await get_user_cities(user_id)
    if any(c.lower() == city.lower() for c in cities):
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO user_cities (user_id, city) VALUES (?, ?)", (user_id, city))
        await db.commit()
    return True

async def remove_user_city(user_id: int, city: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_cities WHERE user_id = ? AND LOWER(city) = LOWER(?)", (user_id, city))
        await db.commit()

async def get_user_alerts(user_id: int) -> dict:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT alerts_enabled, alerts_threshold FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return {"enabled": bool(row[0]), "threshold": row[1]}
        return {"enabled": False, "threshold": 15.0}

async def set_user_alerts(user_id: int, enabled: bool, threshold: float = None):
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        if threshold is not None:
            await db.execute("UPDATE users SET alerts_enabled = ?, alerts_threshold = ? WHERE user_id = ?",
                             (1 if enabled else 0, threshold, user_id))
        else:
            await db.execute("UPDATE users SET alerts_enabled = ? WHERE user_id = ?",
                             (1 if enabled else 0, user_id))
        await db.commit()

async def record_wind_history(user_id: int, city: str, speed: float, deg: int, ts_str: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO wind_history (user_id, city, timestamp, speed, deg) VALUES (?, ?, ?, ?, ?)",
                         (user_id, city.lower(), ts_str, speed, deg))
        # Ограничиваем историю 50 записями на город
        await db.execute("""
            DELETE FROM wind_history WHERE rowid NOT IN (
                SELECT rowid FROM wind_history WHERE user_id = ? AND city = ?
                ORDER BY rowid DESC LIMIT 50
            ) AND user_id = ? AND city = ?
        """, (user_id, city.lower(), user_id, city.lower()))
        await db.commit()

async def get_wind_history(user_id: int, city: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT timestamp, speed, deg FROM wind_history WHERE user_id = ? AND city = ? ORDER BY rowid ASC",
                                   (user_id, city.lower()))
        return await cursor.fetchall()

async def get_weekly_cache(user_id: int, city: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT timestamp, text FROM weekly_cache WHERE user_id = ? AND city = ?",
                                   (user_id, city.lower()))
        row = await cursor.fetchone()
        if row:
            return {"timestamp": row[0], "text": row[1]}
        return None

async def set_weekly_cache(user_id: int, city: str, ts_str: str, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO weekly_cache (user_id, city, timestamp, text) VALUES (?, ?, ?, ?)",
                         (user_id, city.lower(), ts_str, text))
        await db.commit()

async def get_active_alert_users() -> list[dict]:
    """Получает всех пользователей с включенными уведомлениями и их список городов."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, alerts_threshold FROM users WHERE alerts_enabled = 1")
        users = await cursor.fetchall()
        result = []
        for uid, threshold in users:
            c_cursor = await db.execute("SELECT city FROM user_cities WHERE user_id = ?", (uid,))
            cities = [r[0] for r in await c_cursor.fetchall()]
            result.append({"user_id": uid, "threshold": threshold, "cities": cities})
        return result

async def get_last_alert_time(user_id: int, city: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT timestamp FROM last_alerts WHERE user_id = ? AND city = ?",
                                   (user_id, city.lower()))
        row = await cursor.fetchone()
        return row[0] if row else None

async def set_last_alert_time(user_id: int, city: str, ts_str: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO last_alerts (user_id, city, timestamp) VALUES (?, ?, ?)",
                         (user_id, city.lower(), ts_str))
        await db.commit()
