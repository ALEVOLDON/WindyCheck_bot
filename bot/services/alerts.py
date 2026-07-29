import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.enums import ParseMode

from bot.database.db import (
    get_active_alert_users,
    get_last_alert_time,
    set_last_alert_time
)
from bot.services.weather_api import weather_service
from bot.utils.location import resolve_location
from bot.utils.formatting import wind_direction

logger = logging.getLogger(__name__)

async def check_alerts_loop(bot: Bot):
    """Каждые 30 минут проверяет ветер в избранных городах подпписанных пользователей."""
    logger.info("Фоновая проверка уведомлений запущена.")
    while True:
        try:
            await asyncio.sleep(1800) # 30 минут
            if not bot:
                continue

            now = datetime.now()
            users = await get_active_alert_users()

            for u in users:
                uid = u["user_id"]
                threshold = u["threshold"]

                for city in u["cities"]:
                    try:
                        last_alert_str = await get_last_alert_time(uid, city)
                        if last_alert_str:
                            last_alert_time = datetime.strptime(last_alert_str, "%Y-%m-%d %H:%M:%S")
                            if now - last_alert_time < timedelta(hours=3):
                                continue

                        search_city, lat, lon, display_title = resolve_location(city)
                        wind_data, err = await weather_service.get_current_wind(search_city, lat=lat, lon=lon)

                        if wind_data and wind_data["speed"] >= threshold:
                            await bot.send_message(
                                uid,
                                f"🚨 <b>ВНИМАНИЕ! Сильный ветер!</b>\n\n"
                                f"🌬️ <b>{display_title}</b>\n"
                                f"💨 Скорость: <b>{wind_data['speed']:.1f} м/с</b>\n"
                                f"🧭 Направление: {wind_direction(wind_data['deg'])}\n"
                                f"⚡ Порывы: до {wind_data.get('gust', 0):.1f} м/с\n\n"
                                f"Порог: {threshold} м/с\n"
                                f"🕐 {now.strftime('%H:%M:%S')}",
                                parse_mode=ParseMode.HTML
                            )
                            await set_last_alert_time(uid, city, now.strftime("%Y-%m-%d %H:%M:%S"))
                    except Exception as e:
                        logger.error(f"Alert error for user {uid}, city {city}: {e}")
        except asyncio.CancelledError:
            logger.info("Фоновая задача check_alerts остановлена.")
            break
        except Exception as e:
            logger.error(f"Ошибка в цикле check_alerts_loop: {e}")
