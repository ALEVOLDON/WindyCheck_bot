from aiogram import Dispatcher
from bot.handlers.start import router as start_router
from bot.handlers.spots import router as spots_router
from bot.handlers.weather import router as weather_router
from bot.handlers.tracking import router as tracking_router
from bot.handlers.alerts import router as alerts_router

def register_all_handlers(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(spots_router)
    dp.include_router(weather_router)
    dp.include_router(tracking_router)
    dp.include_router(alerts_router)
