import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN, OPENWEATHER_API_KEY
from bot.database.db import init_db
from bot.services.weather_api import weather_service
from bot.services.alerts import check_alerts_loop
from bot.handlers import register_all_handlers

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    if not BOT_TOKEN:
        logger.error("❌ ОШИБКА: BOT_TOKEN не задан в файле .env!")
        return

    if not OPENWEATHER_API_KEY:
        logger.warning("⚠️ ПРЕДУПРЕЖДЕНИЕ: OPENWEATHER_API_KEY не задан в файле .env!")

    # Инициализация базы данных и миграция из user_data.json
    await init_db()

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Регистрация всех хэндлеров
    register_all_handlers(dp)

    # Инициализация HTTP сессии
    await weather_service.start()

    # Запуск фоновой задачи проверки алертов
    alert_task = asyncio.create_task(check_alerts_loop(bot))

    logger.info("🌬️ Wind Tracker Bot запущен!")
    logger.info("🏄‍♂️ Меню спотов Санкт-Петербурга и Ленобласти подключено.")
    logger.info("📅 Прогноз на неделю и инфо-графики доступны.")
    logger.info("🔔 Фоновая проверка уведомлений активна (каждые 30 мин)")

    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Завершение работы бота...")
        alert_task.cancel()
        await weather_service.stop()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
