import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import asyncio
import logging
import io
import os
import sys
import base64
from datetime import datetime, timedelta
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import aiohttp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

# ===== НАСТРОЙКИ =====
TOKEN = os.getenv("BOT_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Хранилище данных
user_data = defaultdict(lambda: {
    "cities": [],
    "last_city": None,
    "wind_history": defaultdict(list),  # city -> [(timestamp, speed, deg)]
    "alerts": {"enabled": False, "threshold": 15},  # порог скорости для уведомлений
    "daily_forecast": False,
    "alert_cities": []
})

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO)

# ===== ИНИЦИАЛИЗАЦИЯ =====
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===== ФУНКЦИИ РАБОТЫ С ПОГОДОЙ =====

async def get_current_wind(city: str):
    """Текущий ветер."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ru"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                d = await resp.json()
                wind = d.get("wind", {})
                return {
                    "city": d["name"], "country": d["sys"]["country"],
                    "speed": wind.get("speed", 0), "gust": wind.get("gust", 0),
                    "deg": wind.get("deg", 0), "temp": d["main"]["temp"],
                    "description": d["weather"][0]["description"],
                    "lat": d["coord"]["lat"], "lon": d["coord"]["lon"],
                    "timestamp": datetime.now()
                }
            return None

async def get_forecast(city: str):
    """Прогноз на 5 дней (каждые 3 часа)."""
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {"q": city, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ru"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                d = await resp.json()
                forecasts = []
                for item in d["list"][:8]:  # ближайшие 24 часа
                    wind = item.get("wind", {})
                    forecasts.append({
                        "time": datetime.fromtimestamp(item["dt"]),
                        "speed": wind.get("speed", 0),
                        "deg": wind.get("deg", 0),
                        "gust": wind.get("gust", 0),
                        "temp": item["main"]["temp"],
                        "description": item["weather"][0]["description"]
                    })
                return forecasts
            return None

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def wind_emoji(speed: float) -> str:
    if speed < 1: return "😶"
    elif speed < 5: return "🍃"
    elif speed < 10: return "🌬️"
    elif speed < 15: return "💨"
    elif speed < 20: return "🌪️"
    else: return "🌀"

def wind_direction(deg: int) -> str:
    dirs = ["⬆️ С", "↗️ СВ", "➡️ В", "↘️ ЮВ", "⬇️ Ю", "↙️ ЮЗ", "⬅️ З", "↖️ СЗ"]
    return dirs[round(deg / 45) % 8]

def wind_description(speed: float) -> str:
    levels = [
        (0.3, "Штиль"), (1.6, "Тихий"), (3.4, "Лёгкий"), (5.5, "Слабый"),
        (8.0, "Умеренный"), (10.8, "Свежий"), (13.9, "Сильный"), (17.2, "Крепкий"),
        (20.8, "Очень крепкий"), (24.5, "Шторм"), (28.5, "Сильный шторм"),
        (32.7, "Жестокий шторм"), (999, "Ураган")
    ]
    for limit, name in levels:
        if speed < limit:
            return name
    return "Ураган"

def format_wind(data: dict) -> str:
    e = wind_emoji(data["speed"])
    d = wind_direction(data["deg"])
    desc = wind_description(data["speed"])
    msg = (
        f"{e} <b>Ветер в {data['city']}, {data['country']}</b>\n\n"
        f"💨 <b>Скорость:</b> {data['speed']:.1f} м/с ({desc})\n"
        f"🧭 <b>Направление:</b> {d} ({data['deg']}°)\n"
    )
    if data.get("gust", 0) > 0:
        msg += f"⚡ <b>Порывы:</b> до {data['gust']:.1f} м/с\n"
    msg += (
        f"\n🌡️ Температура: {data['temp']:.1f}°C\n"
        f"☁️ {data['description'].capitalize()}\n"
        f"\n🕐 {data['timestamp'].strftime('%H:%M:%S')}"
    )
    return msg

# ===== ГРАФИКИ =====

async def create_wind_chart(user_id: int, city: str) -> io.BytesIO:
    """Создаёт график изменения ветра."""
    history = user_data[user_id]["wind_history"].get(city.lower(), [])
    if len(history) < 2:
        return None
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), dpi=100)
    
    times = [h[0] for h in history]
    speeds = [h[1] for h in history]
    degs = [h[2] for h in history]
    
    # График скорости
    ax1.plot(times, speeds, 'b-', linewidth=2, marker='o', markersize=4)
    ax1.fill_between(times, speeds, alpha=0.3)
    ax1.set_ylabel('Скорость (м/с)', fontsize=12)
    ax1.set_title(f'🌬️ История ветра: {city}', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    # График направления
    ax2.scatter(times, degs, c='orange', s=50, alpha=0.7)
    ax2.set_ylabel('Направление (°)', fontsize=12)
    ax2.set_xlabel('Время', fontsize=12)
    ax2.set_ylim(0, 360)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

async def create_forecast_chart(forecasts: list, city: str) -> io.BytesIO:
    """График прогноза ветра."""
    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    
    times = [f["time"] for f in forecasts]
    speeds = [f["speed"] for f in forecasts]
    gusts = [f.get("gust", 0) for f in forecasts]
    
    ax.plot(times, speeds, 'b-', linewidth=2, marker='o', label='Скорость', markersize=6)
    if any(g > 0 for g in gusts):
        ax.plot(times, gusts, 'r--', linewidth=1.5, marker='^', label='Порывы', markersize=5, alpha=0.7)
    
    ax.fill_between(times, speeds, alpha=0.2)
    ax.set_ylabel('Скорость (м/с)', fontsize=12)
    ax.set_xlabel('Время', fontsize=12)
    ax.set_title(f'📊 Прогноз ветра: {city} (24ч)', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

# ===== КАРТА ВЕТРОВ =====

async def get_wind_map_url(lat: float, lon: float) -> str:
    """Генерирует URL карты ветров (OpenWeatherMap)."""
    # Используем OpenWeatherMap Weather Maps 1.0
    return f"https://tile.openweathermap.org/map/wind_new/5/{int((lon+180)/360*32)}/{int((90-lat)/180*16)}.png?appid={OPENWEATHER_API_KEY}"

async def create_wind_rose(history: list, city: str) -> io.BytesIO:
    """Создаёт розу ветров."""
    if len(history) < 3:
        return None
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'), dpi=100)
    
    # Разбиваем направления по секторам
    degs = [h[2] for h in history]
    speeds = [h[1] for h in history]
    
    # Создаём гистограмму по направлениям
    bins = range(0, 361, 45)
    counts = [0] * 8
    avg_speeds = [0] * 8
    
    for d, s in zip(degs, speeds):
        idx = min(int(d / 45), 7)
        counts[idx] += 1
        avg_speeds[idx] += s
    
    for i in range(8):
        if counts[i] > 0:
            avg_speeds[i] /= counts[i]
    
    theta = [i * 45 * 3.14159 / 180 for i in range(8)]
    bars = ax.bar(theta, avg_speeds, width=0.6, bottom=0.0, alpha=0.7, color='skyblue', edgecolor='navy')
    
    # Названия направлений
    ax.set_xticks(theta)
    ax.set_xticklabels(['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'])
    ax.set_title(f'🧭 Роза ветров: {city}', fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

# ===== КОМАНДЫ =====

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌬️ Узнать ветер", callback_data="check_wind")],
        [InlineKeyboardButton(text="📊 Графики", callback_data="charts_menu")],
        [InlineKeyboardButton(text="📍 Мои города", callback_data="my_tracking")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="alerts_menu")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"🌬️ <b>Бот для отслеживания ветра</b>\n\n"
        f"Что я умею:\n"
        f"• 🌬️ Текущий ветер в любом городе\n"
        f"• 📊 Графики изменения ветра\n"
        f"• 🧭 Роза ветров\n"
        f"• 📅 Прогноз на 24 часа\n"
        f"• 🔔 Уведомления о сильном ветре\n"
        f"• 🗺️ Карта ветров\n\n"
        f"Используй кнопки ниже или команды:\n"
        f"/wind [город] — ветер сейчас\n"
        f"/forecast [город] — прогноз\n"
        f"/track [город] — отслеживать\n"
        f"/chart [город] — график\n"
        f"/rose [город] — роза ветров\n"
        f"/map [город] — карта ветров\n"
        f"/alert [скорость] — настроить уведомления",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Полная справка:</b>\n\n"
        "<b>🌬️ Основные:</b>\n"
        "/wind [город] — текущий ветер\n"
        "/forecast [город] — прогноз на 24ч\n"
        "/map [город] — карта ветров в районе\n\n"
        "<b>📊 Аналитика:</b>\n"
        "/chart [город] — график изменения ветра\n"
        "/rose [город] — роза ветров (статистика направлений)\n\n"
        "<b>📍 Отслеживание:</b>\n"
        "/track [город] — добавить в избранное\n"
        "/untrack [город] — убрать из избранного\n"
        "/mywind — все избранные города\n\n"
        "<b>🔔 Уведомления:</b>\n"
        "/alert [скорость] — включить уведомления при ветре выше указанной скорости (м/с)\n"
        "/alert off — выключить уведомления\n"
        "/alert_status — статус уведомлений\n\n"
        "<b>Примеры:</b>\n"
        "• /wind Москва\n"
        "• /forecast Сочи\n"
        "• /chart Владивосток\n"
        "• /alert 15 (уведомлять при ветре >15 м/с)\n"
        "• /track Сочи"
    )

@dp.message(Command("wind"))
async def cmd_wind(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    
    if len(args) < 2:
        if user_data[uid]["last_city"]:
            city = user_data[uid]["last_city"]
        else:
            await message.answer("❌ Укажи город: /wind Москва")
            return
    else:
        city = args[1].strip()
        user_data[uid]["last_city"] = city
    
    await message.bot.send_chat_action(message.chat.id, "typing")
    data = await get_current_wind(city)
    
    if not data:
        await message.answer(f"❌ Город «{city}» не найден.")
        return
    
    # Сохраняем в историю
    user_data[uid]["wind_history"][data["city"].lower()].append(
        (data["timestamp"], data["speed"], data["deg"])
    )
    # Ограничиваем историю 50 точками
    hist = user_data[uid]["wind_history"][data["city"].lower()]
    if len(hist) > 50:
        user_data[uid]["wind_history"][data["city"].lower()] = hist[-50:]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{data['city']}")],
        [InlineKeyboardButton(text="📊 График", callback_data=f"chart:{data['city']}")],
        [InlineKeyboardButton(text="📅 Прогноз", callback_data=f"forecast:{data['city']}")],
        [InlineKeyboardButton(text="🧭 Роза ветров", callback_data=f"rose:{data['city']}")],
        [InlineKeyboardButton(text="🗺️ Карта", callback_data=f"map:{data['city']}")],
        [InlineKeyboardButton(text="📍 В избранное", callback_data=f"track:{data['city']}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await message.answer(format_wind(data), reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.message(Command("forecast"))
async def cmd_forecast(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    
    if len(args) < 2:
        if user_data[uid]["last_city"]:
            city = user_data[uid]["last_city"]
        else:
            await message.answer("❌ Укажи город: /forecast Москва")
            return
    else:
        city = args[1].strip()
    
    await message.bot.send_chat_action(message.chat.id, "typing")
    forecasts = await get_forecast(city)
    
    if not forecasts:
        await message.answer(f"❌ Не удалось получить прогноз для «{city}».")
        return
    
    # Текстовый прогноз
    text = f"📅 <b>Прогноз ветра: {city}</b> (ближайшие 24ч)\n\n"
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
    
    # График прогноза
    chart_buf = await create_forecast_chart(forecasts, city)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌬️ Сейчас", callback_data=f"wind:{city}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    if chart_buf:
        await message.answer_photo(
            types.BufferedInputFile(chart_buf.getvalue(), filename="forecast.png"),
            caption=text, reply_markup=kb, parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.message(Command("chart"))
async def cmd_chart(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    
    if len(args) < 2:
        if user_data[uid]["last_city"]:
            city = user_data[uid]["last_city"]
        else:
            await message.answer("❌ Укажи город: /chart Москва")
            return
    else:
        city = args[1].strip()
    
    chart_buf = await create_wind_chart(uid, city)
    
    if not chart_buf:
        await message.answer(
            f"📊 Недостаточно данных для графика «{city}».\n"
            f"Сначала проверь ветер командой /wind {city} несколько раз."
        )
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить график", callback_data=f"chart:{city}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await message.answer_photo(
        types.BufferedInputFile(chart_buf.getvalue(), filename="chart.png"),
        caption=f"📊 <b>График ветра: {city}</b>",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.message(Command("rose"))
async def cmd_rose(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    
    if len(args) < 2:
        if user_data[uid]["last_city"]:
            city = user_data[uid]["last_city"]
        else:
            await message.answer("❌ Укажи город: /rose Москва")
            return
    else:
        city = args[1].strip()
    
    history = user_data[uid]["wind_history"].get(city.lower(), [])
    rose_buf = await create_wind_rose(history, city)
    
    if not rose_buf:
        await message.answer(
            f"🧭 Недостаточно данных для розы ветров «{city}».\n"
            f"Проверь ветер несколько раз: /wind {city}"
        )
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"rose:{city}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await message.answer_photo(
        types.BufferedInputFile(rose_buf.getvalue(), filename="rose.png"),
        caption=f"🧭 <b>Роза ветров: {city}</b>\n\nПоказывает преобладающие направления ветра.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.message(Command("map"))
async def cmd_map(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    
    if len(args) < 2:
        if user_data[uid]["last_city"]:
            city = user_data[uid]["last_city"]
        else:
            await message.answer("❌ Укажи город: /map Москва")
            return
    else:
        city = args[1].strip()
    
    await message.bot.send_chat_action(message.chat.id, "typing")
    data = await get_current_wind(city)
    
    if not data:
        await message.answer(f"❌ Город «{city}» не найден.")
        return
    
    # Используем Windy.com как внешнюю карту (более наглядная)
    lat, lon = data["lat"], data["lon"]
    map_url = f"https://www.windy.com/?{lat},{lon},8"
    
    # Также можно отправить статичную карту
    static_map = f"https://maps.geoapify.com/v1/staticmap?style=osm-bright&width=600&height=400&center=lonlat:{lon},{lat}&zoom=8&apiKey=YOUR_GEOAPIFY_KEY"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺️ Открыть интерактивную карту", url=map_url)],
        [InlineKeyboardButton(text="🌬️ Ветер здесь", callback_data=f"wind:{city}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await message.answer(
        f"🗺️ <b>Карта ветров: {data['city']}</b>\n\n"
        f"📍 Координаты: {lat:.4f}, {lon:.4f}\n\n"
        f"Нажми кнопку ниже, чтобы открыть интерактивную карту ветров Windy.com "
        f"с текущим положением.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.message(Command("track"))
async def cmd_track(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи город: /track Москва")
        return
    
    city = args[1].strip()
    uid = message.from_user.id
    
    await message.bot.send_chat_action(message.chat.id, "typing")
    data = await get_current_wind(city)
    
    if not data:
        await message.answer(f"❌ Город «{city}» не найден.")
        return
    
    cities = user_data[uid]["cities"]
    if data["city"].lower() not in [c.lower() for c in cities]:
        cities.append(data["city"])
        await message.answer(
            f"✅ <b>{data['city']}</b> добавлен в отслеживание!\n\n"
            f"Текущий ветер: {data['speed']:.1f} м/с\n"
            f"Используй /mywind для просмотра всех городов.",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(f"⚠️ <b>{data['city']}</b> уже отслеживается.", parse_mode=ParseMode.HTML)

@dp.message(Command("untrack"))
async def cmd_untrack(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    
    if len(args) < 2:
        cities = user_data[uid]["cities"]
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
    user_data[uid]["cities"] = [c for c in user_data[uid]["cities"] if c.lower() != city.lower()]
    await message.answer(f"✅ «{city}» удалён из отслеживания.")

@dp.message(Command("mywind"))
async def cmd_mywind(message: types.Message):
    uid = message.from_user.id
    cities = user_data[uid]["cities"]
    
    if not cities:
        await message.answer(
            "📭 Нет отслеживаемых городов.\n"
            "Добавь: /track Москва"
        )
        return
    
    await message.answer("🔄 Загружаю данные...")
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    results = []
    for city in cities:
        data = await get_current_wind(city)
        if data:
            e = wind_emoji(data["speed"])
            results.append(
                f"{e} <b>{data['city']}</b>: "
                f"{data['speed']:.1f} м/с, {wind_direction(data['deg'])}"
            )
            # Обновляем историю
            user_data[uid]["wind_history"][data["city"].lower()].append(
                (data["timestamp"], data["speed"], data["deg"])
            )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить все", callback_data="refresh_all")],
        [InlineKeyboardButton(text="📊 Общий график", callback_data="multi_chart")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    if results:
        await message.answer(
            "📍 <b>Твои города:</b>\n\n" + "\n".join(results),
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    else:
        await message.answer("❌ Ошибка загрузки данных.")

# ===== УВЕДОМЛЕНИЯ =====

@dp.message(Command("alert"))
async def cmd_alert(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    
    if len(args) < 2:
        status = user_data[uid]["alerts"]
        enabled = "✅ Включены" if status["enabled"] else "❌ Выключены"
        await message.answer(
            f"🔔 <b>Уведомления о сильном ветре</b>\n\n"
            f"Статус: {enabled}\n"
            f"Порог: {status['threshold']} м/с\n\n"
            f"Используй:\n"
            f"/alert [скорость] — включить (например: /alert 15)\n"
            f"/alert off — выключить\n"
            f"/alert_status — подробный статус"
        )
        return
    
    param = args[1].strip().lower()
    
    if param == "off":
        user_data[uid]["alerts"]["enabled"] = False
        await message.answer("🔕 Уведомления о сильном ветре <b>выключены</b>.", parse_mode=ParseMode.HTML)
        return
    
    try:
        threshold = float(param)
        if threshold < 0 or threshold > 50:
            await message.answer("❌ Укажи разумное значение (0-50 м/с).")
            return
        
        user_data[uid]["alerts"]["enabled"] = True
        user_data[uid]["alerts"]["threshold"] = threshold
        
        await message.answer(
            f"🔔 <b>Уведомления включены!</b>\n\n"
            f"Я буду проверять ветер в твоих избранных городах каждые 30 минут.\n"
            f"Если скорость превысит <b>{threshold} м/с</b> — пришлю уведомление!\n\n"
            f"Добавь города в отслеживание: /track [город]",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer("❌ Укажи число: /alert 15")

@dp.message(Command("alert_status"))
async def cmd_alert_status(message: types.Message):
    uid = message.from_user.id
    alerts = user_data[uid]["alerts"]
    cities = user_data[uid]["cities"]
    
    status = "✅ Активны" if alerts["enabled"] else "❌ Неактивны"
    cities_str = ", ".join(cities) if cities else "нет городов"
    
    await message.answer(
        f"🔔 <b>Статус уведомлений:</b>\n\n"
        f"Статус: {status}\n"
        f"Порог скорости: {alerts['threshold']} м/с\n"
        f"Отслеживаемые города: {cities_str}\n"
        f"Проверка: каждые 30 минут\n\n"
        f"Изменить: /alert [скорость] или /alert off"
    )

# ===== CALLBACK ОБРАБОТЧИКИ =====

@dp.callback_query(F.data == "check_wind")
async def cb_check_wind(callback: types.CallbackQuery):
    await callback.message.answer("🌬️ Напиши: /wind [город]")
    await callback.answer()

@dp.callback_query(F.data == "charts_menu")
async def cb_charts_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 График ветра", callback_data="chart_prompt")],
        [InlineKeyboardButton(text="🧭 Роза ветров", callback_data="rose_prompt")],
        [InlineKeyboardButton(text="📅 Прогноз", callback_data="forecast_prompt")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    await callback.message.answer("📊 <b>Графики и аналитика</b>\n\nВыбери тип:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.endswith("_prompt"))
async def cb_prompt(callback: types.CallbackQuery):
    cmd = callback.data.replace("_prompt", "")
    await callback.message.answer(f"Напиши: /{cmd} [город]")
    await callback.answer()

@dp.callback_query(F.data == "my_tracking")
async def cb_my_tracking(callback: types.CallbackQuery):
    await cmd_mywind(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "alerts_menu")
async def cb_alerts(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Включить", callback_data="alert_on_prompt")],
        [InlineKeyboardButton(text="🔕 Выключить", callback_data="alert_off")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="alert_status_cb")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    await callback.message.answer(
        "🔔 <b>Уведомления о сильном ветре</b>\n\n"
        "Я буду проверять ветер в твоих городах и предупреждать, "
        "если он станет слишком сильным!",
        reply_markup=kb
    )
    await callback.answer()

@dp.callback_query(F.data == "alert_on_prompt")
async def cb_alert_on(callback: types.CallbackQuery):
    await callback.message.answer("Напиши: /alert [порог в м/с]\nПример: /alert 15")
    await callback.answer()

@dp.callback_query(F.data == "alert_off")
async def cb_alert_off(callback: types.CallbackQuery):
    user_data[callback.from_user.id]["alerts"]["enabled"] = False
    await callback.message.answer("🔕 Уведомления выключены.")
    await callback.answer()

@dp.callback_query(F.data == "alert_status_cb")
async def cb_alert_status_cb(callback: types.CallbackQuery):
    await cmd_alert_status(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "start_menu")
async def cb_start_menu(callback: types.CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "help")
async def cb_help(callback: types.CallbackQuery):
    await cmd_help(callback.message)
    await callback.answer()

@dp.callback_query(F.data.startswith("refresh:"))
async def cb_refresh(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    data = await get_current_wind(city)
    if data:
        uid = callback.from_user.id
        user_data[uid]["wind_history"][city.lower()].append(
            (data["timestamp"], data["speed"], data["deg"])
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{city}")],
            [InlineKeyboardButton(text="📊 График", callback_data=f"chart:{city}")],
            [InlineKeyboardButton(text="📅 Прогноз", callback_data=f"forecast:{city}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
        ])
        await callback.message.edit_text(format_wind(data), reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer("Обновлено!")

@dp.callback_query(F.data.startswith("wind:"))
async def cb_wind(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    message = callback.message
    message.text = f"/wind {city}"
    message.from_user = callback.from_user
    await cmd_wind(message)
    await callback.answer()

@dp.callback_query(F.data.startswith("forecast:"))
async def cb_forecast(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    message = callback.message
    message.text = f"/forecast {city}"
    message.from_user = callback.from_user
    await cmd_forecast(message)
    await callback.answer()

@dp.callback_query(F.data.startswith("chart:"))
async def cb_chart(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    message = callback.message
    message.from_user = callback.from_user
    # Обновляем график
    chart_buf = await create_wind_chart(callback.from_user.id, city)
    if chart_buf:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"chart:{city}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
        ])
        await callback.message.answer_photo(
            types.BufferedInputFile(chart_buf.getvalue(), filename="chart.png"),
            caption=f"📊 <b>График ветра: {city}</b>",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    else:
        await callback.message.answer("📊 Недостаточно данных. Проверь ветер несколько раз.")
    await callback.answer()

@dp.callback_query(F.data.startswith("rose:"))
async def cb_rose(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    history = user_data[uid]["wind_history"].get(city.lower(), [])
    rose_buf = await create_wind_rose(history, city)
    if rose_buf:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"rose:{city}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
        ])
        await callback.message.answer_photo(
            types.BufferedInputFile(rose_buf.getvalue(), filename="rose.png"),
            caption=f"🧭 <b>Роза ветров: {city}</b>",
            reply_markup=kb, parse_mode=ParseMode.HTML
        )
    else:
        await callback.message.answer("🧭 Недостаточно данных.")
    await callback.answer()

@dp.callback_query(F.data.startswith("map:"))
async def cb_map(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    message = callback.message
    message.text = f"/map {city}"
    message.from_user = callback.from_user
    await cmd_map(message)
    await callback.answer()

@dp.callback_query(F.data.startswith("track:"))
async def cb_track(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    cities = user_data[uid]["cities"]
    
    if city.lower() not in [c.lower() for c in cities]:
        cities.append(city)
        await callback.answer(f"✅ {city} добавлен!")
    else:
        await callback.answer(f"⚠️ Уже отслеживается!")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{city}")],
        [InlineKeyboardButton(text="✅ В избранном", callback_data="already_tracked")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    await callback.message.edit_reply_markup(reply_markup=kb)

@dp.callback_query(F.data.startswith("untrack:"))
async def cb_untrack(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    user_data[uid]["cities"] = [c for c in user_data[uid]["cities"] if c.lower() != city.lower()]
    await callback.answer(f"❌ {city} удалён!")
    await cmd_mywind(callback.message)

@dp.callback_query(F.data == "refresh_all")
async def cb_refresh_all(callback: types.CallbackQuery):
    await cmd_mywind(callback.message)
    await callback.answer("Обновлено!")

@dp.callback_query(F.data == "multi_chart")
async def cb_multi_chart(callback: types.CallbackQuery):
    uid = callback.from_user.id
    cities = user_data[uid]["cities"]
    
    if len(cities) < 2:
        await callback.answer("Нужно минимум 2 города!")
        return
    
    # Создаём сравнительный график
    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    
    for city in cities:
        history = user_data[uid]["wind_history"].get(city.lower(), [])
        if len(history) >= 2:
            times = [h[0] for h in history[-20:]]
            speeds = [h[1] for h in history[-20:]]
            ax.plot(times, speeds, marker='o', label=city, linewidth=2)
    
    ax.set_ylabel('Скорость (м/с)', fontsize=12)
    ax.set_title('📊 Сравнение ветра в городах', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="multi_chart")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await callback.message.answer_photo(
        types.BufferedInputFile(buf.getvalue(), filename="multi_chart.png"),
        caption="📊 <b>Сравнение ветра в твоих городах</b>",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )
    await callback.answer()

# ===== ФОНОВАЯ ЗАДАЧА: ПРОВЕРКА УВЕДОМЛЕНИЙ =====

async def check_alerts():
    """Каждые 30 минут проверяет ветер в избранных городах."""
    while True:
        await asyncio.sleep(1800)  # 30 минут
        
        for uid, data in user_data.items():
            if not data["alerts"]["enabled"]:
                continue
            
            threshold = data["alerts"]["threshold"]
            
            for city in data["cities"]:
                try:
                    wind_data = await get_current_wind(city)
                    if wind_data and wind_data["speed"] >= threshold:
                        # Проверяем, не отправляли ли уже уведомление недавно
                        await bot.send_message(
                            uid,
                            f"🚨 <b>ВНИМАНИЕ! Сильный ветер!</b>\n\n"
                            f"🌬️ <b>{wind_data['city']}</b>\n"
                            f"💨 Скорость: <b>{wind_data['speed']:.1f} м/с</b>\n"
                            f"🧭 Направление: {wind_direction(wind_data['deg'])}\n"
                            f"⚡ Порывы: до {wind_data.get('gust', 0):.1f} м/с\n\n"
                            f"Порог: {threshold} м/с\n"
                            f"🕐 {datetime.now().strftime('%H:%M:%S')}",
                            parse_mode=ParseMode.HTML
                        )
                except Exception as e:
                    logging.error(f"Alert error for user {uid}, city {city}: {e}")

# ===== ЗАПУСК =====

async def main():
    # Запускаем фоновую проверку уведомлений
    asyncio.create_task(check_alerts())
    
    print("🌬️ Бот для отслеживания ветра запущен!")
    print("🔔 Фоновая проверка уведомлений активна (каждые 30 мин)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())