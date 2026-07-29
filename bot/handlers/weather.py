from datetime import datetime, timedelta
from collections import defaultdict
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.enums import ParseMode

from bot.utils.location import resolve_location
from bot.utils.formatting import format_wind, wind_emoji, wind_direction, spot_rating
from bot.services.weather_api import weather_service
from bot.services.chart_builder import create_detailed_infographic_chart, create_wind_rose
from bot.database.db import (
    get_user_last_city, set_user_last_city, record_wind_history,
    get_wind_history, get_weekly_cache, set_weekly_cache
)
from bot.keyboards.inline import get_weather_actions_keyboard, get_back_home_keyboard, get_start_keyboard

router = Router()

async def show_city_wind(user_id: int, city: str, send_func):
    search_city, lat, lon, display_title = resolve_location(city)
    data, err = await weather_service.get_current_wind(search_city, lat=lat, lon=lon)
    if err:
        await send_func(f"❌ {err}")
        return

    await set_user_last_city(user_id, display_title)
    now_str = data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
    await record_wind_history(user_id, data["city"], data["speed"], data["deg"], now_str)

    await send_func(
        format_wind(data),
        reply_markup=get_weather_actions_keyboard(display_title),
        parse_mode=ParseMode.HTML
    )

async def show_city_week_forecast(user_id: int, city: str, send_func):
    search_city, lat, lon, display_title = resolve_location(city)
    now = datetime.now()
    cache = await get_weekly_cache(user_id, display_title)

    if cache:
        try:
            cache_time = datetime.strptime(cache["timestamp"], "%Y-%m-%d %H:%M:%S")
            if now - cache_time < timedelta(hours=12):
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📊 Подробный график", callback_data=f"chart:{display_title}")],
                    [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")]
                ])
                await send_func(cache["text"], reply_markup=kb, parse_mode=ParseMode.HTML)
                return
        except Exception:
            pass

    raw_forecasts, city_name, err = await weather_service.get_forecast_raw(search_city, lat=lat, lon=lon)
    if err:
        await send_func(f"❌ {err}")
        return

    daily_data = defaultdict(list)
    for f in raw_forecasts:
        day_str = f["time"].strftime("%d.%m (%a)")
        daily_data[day_str].append(f)

    title_name = display_title if display_title else city_name
    lines = [f"📅 <b>Прогноз погоды и ветра на неделю: {title_name}</b>\n<i>(Перепроверка раз в день)</i>\n"]

    for day_str, items in list(daily_data.items())[:6]:
        speeds = [item["speed"] for item in items]
        gusts = [item.get("gust", 0) for item in items]
        temps = [item["temp"] for item in items]
        degs = [item["deg"] for item in items]

        avg_speed = sum(speeds) / len(speeds)
        max_speed = max(speeds)
        max_gust = max(gusts) if gusts else 0
        min_temp = min(temps)
        max_temp = max(temps)
        prev_deg = degs[len(degs)//2]

        e = wind_emoji(avg_speed)
        d = wind_direction(prev_deg)
        desc = items[0]["description"].capitalize()
        rating = spot_rating(avg_speed)

        day_text = (
            f"<b>{day_str}</b> {e}\n"
            f"  💨 Ветер: <b>{min(speeds):.1f} - {max_speed:.1f} м/с</b> (ср. {avg_speed:.1f}), {d}\n"
        )
        if max_gust > max_speed:
            day_text += f"  ⚡ Порывы: до <b>{max_gust:.1f} м/с</b>\n"
        day_text += f"  🌡️ Температура: <b>{min_temp:.0f}°C ... {max_temp:.0f}°C</b> ({desc})\n"
        day_text += f"  <i>{rating}</i>\n"
        lines.append(day_text)

    full_text = "\n".join(lines)
    await set_weekly_cache(user_id, display_title, now.strftime("%Y-%m-%d %H:%M:%S"), full_text)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📊 Подробный график", callback_data=f"chart:{display_title}")],
        [types.InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")]
    ])
    await send_func(full_text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def show_city_chart(user_id: int, city: str, send_photo_func, send_text_func):
    search_city, lat, lon, display_title = resolve_location(city)
    raw_forecasts, city_name, err = await weather_service.get_forecast_raw(search_city, lat=lat, lon=lon)
    if err or not raw_forecasts:
        await send_text_func(f"❌ {err or 'Не удалось получить данные для графика.'}")
        return

    title_name = display_title if display_title else city_name
    chart_buf = await create_detailed_infographic_chart(raw_forecasts[:16], title_name)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📅 На неделю", callback_data=f"week:{display_title}")],
        [types.InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])

    await send_photo_func(
        types.BufferedInputFile(chart_buf.getvalue(), filename="chart.png"),
        caption=f"📊 <b>Информативный график метео-анализа: {title_name}</b>\n(Скорость, Порывы, Пороговые линии, Температура, Давление)",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

async def show_city_forecast_24h(user_id: int, city: str, send_photo_func, send_text_func):
    search_city, lat, lon, display_title = resolve_location(city)
    raw_forecasts, city_name, err = await weather_service.get_forecast_raw(search_city, lat=lat, lon=lon)
    if err:
        await send_text_func(f"❌ {err}")
        return

    title_name = display_title if display_title else city_name
    forecasts = raw_forecasts[:8]  # 24 часа
    text = f"📅 <b>Прогноз ветра: {title_name}</b> (24 часа)\n\n"
    for f in forecasts:
        e = wind_emoji(f["speed"])
        d = wind_direction(f["deg"])
        text += (
            f"{e} <b>{f['time'].strftime('%H:%M')}</b> — "
            f"{f['speed']:.1f} м/с, {d}"
        )
        if f.get("gust", 0) > 0:
            text += f" (порывы {f['gust']:.1f})"
        text += f", {f['temp']:.0f}°C\n"

    chart_buf = await create_detailed_infographic_chart(forecasts, title_name)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data=f"week:{display_title}")],
        [types.InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])

    if chart_buf:
        await send_photo_func(
            types.BufferedInputFile(chart_buf.getvalue(), filename="forecast.png"),
            caption=text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    else:
        await send_text_func(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def show_city_map(user_id: int, city: str, send_func):
    search_city, lat, lon, display_title = resolve_location(city)
    data, err = await weather_service.get_current_wind(search_city, lat=lat, lon=lon)
    if err:
        await send_func(f"❌ {err}")
        return

    spot_lat = data["lat"] if lat is None else lat
    spot_lon = data["lon"] if lon is None else lon
    map_url = f"https://www.windy.com/?{spot_lat},{spot_lon},9"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🗺️ Открыть карту Windy.com", url=map_url)],
        [types.InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])

    await send_func(
        f"🗺️ <b>Интерактивная карта ветров: {display_title}</b>\n\n"
        f"📍 Координаты: {spot_lat:.4f}, {spot_lon:.4f}\n"
        f"Нажми кнопку ниже для перехода на интерактивную карту Windy.com.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

# ----- КОМАНДЫ ПОВОДЫ И ПРОГНОЗЫ -----

@router.message(Command("wind"))
async def cmd_wind(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else await get_user_last_city(uid)
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_wind(uid, city, message.answer)

@router.message(Command("week"))
async def cmd_week(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else await get_user_last_city(uid)
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_week_forecast(uid, city, message.answer)

@router.message(Command("forecast"))
async def cmd_forecast(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else await get_user_last_city(uid)
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_forecast_24h(uid, city, message.answer_photo, message.answer)

@router.message(Command("chart"))
async def cmd_chart(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else await get_user_last_city(uid)
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    await show_city_chart(uid, city, message.answer_photo, message.answer)

@router.message(Command("rose"))
async def cmd_rose(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else await get_user_last_city(uid)
    search_city, lat, lon, display_title = resolve_location(city)
    history = await get_wind_history(uid, search_city) or await get_wind_history(uid, display_title)
    rose_buf = await create_wind_rose(history, display_title)

    if not rose_buf:
        await message.answer(
            f"🧭 Недостаточно данных для розы ветров «{display_title}».\n"
            f"Запроси ветер несколько раз: /wind {display_title}"
        )
        return

    await message.answer_photo(
        types.BufferedInputFile(rose_buf.getvalue(), filename="rose.png"),
        caption=f"🧭 <b>Роза ветров: {display_title}</b>\n\nПоказывает преобладающие направления ветра.",
        reply_markup=get_back_home_keyboard(), parse_mode=ParseMode.HTML
    )

@router.message(Command("map"))
async def cmd_map(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else await get_user_last_city(uid)
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_map(uid, city, message.answer)

# ----- CALLBACKS ПОВОДЫ И ПРОГНОЗЫ -----

@router.callback_query(F.data == "check_wind")
async def cb_check_wind(callback: types.CallbackQuery):
    await callback.message.answer("🌬️ Напиши город: /wind [город] или выбери /spb")
    await callback.answer()

@router.callback_query(F.data == "charts_menu")
async def cb_charts_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    city = await get_user_last_city(uid)
    await show_city_chart(uid, city, callback.message.answer_photo, callback.message.answer)
    await callback.answer()

@router.callback_query(F.data == "week_prompt")
async def cb_week_prompt(callback: types.CallbackQuery):
    uid = callback.from_user.id
    city = await get_user_last_city(uid)
    await show_city_week_forecast(uid, city, callback.message.answer)
    await callback.answer()

@router.callback_query(F.data.startswith("week:"))
async def cb_week_city(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_week_forecast(uid, city, callback.message.answer)
    await callback.answer()

@router.callback_query(F.data.startswith("refresh:"))
async def cb_refresh(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    search_city, lat, lon, display_title = resolve_location(city)
    data, err = await weather_service.get_current_wind(search_city, lat=lat, lon=lon)
    if data:
        uid = callback.from_user.id
        now_str = data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        await record_wind_history(uid, display_title, data["speed"], data["deg"], now_str)
        await callback.message.edit_text(
            format_wind(data),
            reply_markup=get_weather_actions_keyboard(display_title),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.message.answer(f"❌ {err}")
    await callback.answer("Обновлено!")

@router.callback_query(F.data.startswith("chart:"))
async def cb_chart(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_chart(uid, city, callback.message.answer_photo, callback.message.answer)
    await callback.answer()

@router.callback_query(F.data.startswith("forecast:"))
async def cb_forecast(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_forecast_24h(uid, city, callback.message.answer_photo, callback.message.answer)
    await callback.answer()

@router.callback_query(F.data.startswith("map:"))
async def cb_map(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_map(uid, city, callback.message.answer)
    await callback.answer()
