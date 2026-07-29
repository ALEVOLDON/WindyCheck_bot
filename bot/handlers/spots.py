from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from datetime import datetime

from bot.constants import SPB_SPOTS
from bot.keyboards.inline import get_spots_keyboard, get_spot_actions_keyboard
from bot.services.weather_api import weather_service
from bot.database.db import set_user_last_city, record_wind_history
from bot.utils.formatting import wind_emoji, wind_direction, wind_description, spot_rating

router = Router()

@router.message(Command("spb"))
async def cmd_spb(message: types.Message):
    await message.answer(
        "🏄‍♂️ <b>Популярные ветровые споты Санкт-Петербурга и Ленобласти:</b>\n\n"
        "Выбери спот для получения текущего ветра, оценки катания, прогноза и карты Windy:",
        reply_markup=get_spots_keyboard(),
        parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data == "spb_spots_menu")
async def cb_spb_spots_menu(callback: types.CallbackQuery):
    await cmd_spb(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("spot:"))
async def cb_spot_select(callback: types.CallbackQuery):
    spot_key = callback.data.split(":", 1)[1]
    spot = SPB_SPOTS.get(spot_key)

    if not spot:
        await callback.answer("Спот не найден.")
        return

    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    data, err = await weather_service.get_current_wind(spot["search_city"], lat=spot["lat"], lon=spot["lon"])

    if err:
        await callback.message.answer(f"❌ {err}")
        await callback.answer()
        return

    user_id = callback.from_user.id
    await set_user_last_city(user_id, spot["name"])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await record_wind_history(user_id, spot["name"], data["speed"], data["deg"], now_str)

    map_url = f"https://www.windy.com/?{spot['lat']},{spot['lon']},10"
    rating = spot_rating(data["speed"])

    e = wind_emoji(data["speed"])
    d = wind_direction(data["deg"])
    desc = wind_description(data["speed"])

    msg = (
        f"🏄‍♂️ <b>Спот: {spot['name']}</b>\n"
        f"<i>{spot['desc']}</i>\n\n"
        f"{e} <b>Скорость ветра:</b> {data['speed']:.1f} м/с ({desc})\n"
        f"🧭 <b>Направление:</b> {d} ({data['deg']}°)\n"
    )
    if data.get("gust", 0) > 0:
        msg += f"⚡ <b>Порывы:</b> до {data['gust']:.1f} м/с\n"
    msg += (
        f"\n🌡️ <b>Температура:</b> {data['temp']:.1f}°C\n"
        f"📊 <b>Давление:</b> {data.get('pressure', 760)} мм рт.ст.\n"
        f"💧 <b>Влажность:</b> {data.get('humidity', 50)}%\n"
        f"☁️ {data['description'].capitalize()}\n"
        f"\n🏄‍♂️ <b>Оценка катания:</b> {rating}\n"
        f"📍 Координаты: {spot['lat']}, {spot['lon']}"
    )

    await callback.message.answer(msg, reply_markup=get_spot_actions_keyboard(map_url, spot_key), parse_mode=ParseMode.HTML)
    await callback.answer()
