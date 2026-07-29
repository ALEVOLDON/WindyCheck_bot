from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils.location import resolve_location
from bot.utils.formatting import wind_emoji, wind_direction
from bot.services.weather_api import weather_service
from bot.database.db import (
    get_user_cities, add_user_city, remove_user_city, record_wind_history
)
from bot.keyboards.inline import get_back_home_keyboard

router = Router()

@router.message(Command("track"))
async def cmd_track(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи город: /track Москва")
        return

    city = args[1].strip()
    uid = message.from_user.id
    search_city, lat, lon, display_title = resolve_location(city)
    data, err = await weather_service.get_current_wind(search_city, lat=lat, lon=lon)
    if err:
        await message.answer(f"❌ {err}")
        return

    added = await add_user_city(uid, display_title)
    if added:
        await message.answer(
            f"✅ <b>{display_title}</b> добавлен в избранное!\n\n"
            f"Используй /mywind для быстрого просмотра.",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(f"⚠️ <b>{display_title}</b> уже в избранном.", parse_mode=ParseMode.HTML)

@router.message(Command("untrack"))
async def cmd_untrack(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id

    if len(args) < 2:
        cities = await get_user_cities(uid)
        if not cities:
            await message.answer("📭 Нет отслеживаемых городов.")
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {c}", callback_data=f"untrack:{c}")]
            for c in cities
        ] + [[InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]])
        await message.answer("Выбери город для удаления:", reply_markup=kb)
        return

    city = args[1].strip()
    await remove_user_city(uid, city)
    await message.answer(f"✅ «{city}» удалён из списка.")

@router.message(Command("mywind"))
async def cmd_mywind(message: types.Message):
    uid = message.from_user.id
    cities = await get_user_cities(uid)

    if not cities:
        await message.answer(
            "📭 Нет сохранённых городов.\n"
            "Добавить: /track Санкт-Петербург"
        )
        return

    await message.answer("🔄 Загружаю данные...")
    await message.bot.send_chat_action(message.chat.id, "typing")

    results = []
    for city in cities:
        search_city, lat, lon, display_title = resolve_location(city)
        data, err = await weather_service.get_current_wind(search_city, lat=lat, lon=lon)
        if data:
            e = wind_emoji(data["speed"])
            results.append(
                f"{e} <b>{display_title}</b>: "
                f"{data['speed']:.1f} м/с, {wind_direction(data['deg'])}"
            )
            now_str = data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            await record_wind_history(uid, display_title, data["speed"], data["deg"], now_str)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить все", callback_data="refresh_all")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])

    if results:
        await message.answer(
            "📍 <b>Твои избранные города:</b>\n\n" + "\n".join(results),
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("❌ Ошибка загрузки данных.")

# ----- CALLBACKS TRACKING -----

@router.callback_query(F.data == "my_tracking")
async def cb_my_tracking(callback: types.CallbackQuery):
    await cmd_mywind(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("track:"))
async def cb_track(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    search_city, lat, lon, display_title = resolve_location(city)
    added = await add_user_city(uid, display_title)

    if added:
        await callback.answer(f"✅ {display_title} добавлен!")
    else:
        await callback.answer(f"⚠️ Уже в избранном!")

@router.callback_query(F.data.startswith("untrack:"))
async def cb_untrack(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await remove_user_city(uid, city)
    await callback.answer(f"❌ {city} удалён!")
    await cmd_mywind(callback.message)

@router.callback_query(F.data == "refresh_all")
async def cb_refresh_all(callback: types.CallbackQuery):
    await cmd_mywind(callback.message)
    await callback.answer("Обновлено!")
