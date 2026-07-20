import os
import sys
import json
import re
import asyncio
import logging
import io
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
DATA_FILE = "user_data.json"

# СЕТКА СПОТОВ САНКТ-ПЕТЕРБУРГА И ЛЕНОБЛАСТИ
SPB_SPOTS = {
    "sestroretsk": {
        "name": "Сестрорецк / Дюны 🏖️",
        "search_city": "Сестрорецк",
        "lat": 59.973, "lon": 29.962,
        "desc": "Финский залив, популярнейший кайт- и виндсерф спот"
    },
    "kronstadt": {
        "name": "Кронштадт / Дамба ⚓",
        "search_city": "Кронштадт",
        "lat": 59.992, "lon": 29.771,
        "desc": "Северная и Южная дамбы, идеальны при западных ветрах"
    },
    "lakhta": {
        "name": "Лахта / Невская губа 🏢",
        "search_city": "Санкт-Петербург",
        "lat": 59.983, "lon": 30.183,
        "desc": "Акватория у Лахта Центра, открытая зона Невской губы"
    },
    "zelenogorsk": {
        "name": "Зеленогорск 🌲",
        "search_city": "Зеленогорск",
        "lat": 60.191, "lon": 29.704,
        "desc": "Северный берег залива, песчаный пляж"
    },
    "kokorevo": {
        "name": "Кокорево / Ладога ⛵",
        "search_city": "Шлиссельбург",
        "lat": 60.052, "lon": 31.077,
        "desc": "Ладожское озеро, отличный спот при восточных ветрах"
    },
    "sosnovy_bor": {
        "name": "Сосновый Бор 🏖️",
        "search_city": "Сосновый Бор",
        "lat": 59.897, "lon": 29.088,
        "desc": "Южный берег Финского залива, Липовский пляж"
    },
    "komarovo": {
        "name": "Комарово 🌅",
        "search_city": "Комарово",
        "lat": 60.181, "lon": 29.802,
        "desc": "Песчаное мелководье, популярно для виндсерфинга"
    }
}

def resolve_location(query: str):
    """Преобразует строку запроса (даже с эмодзи/спотами) в чистый город или GPS координаты."""
    if not query:
        return "Санкт-Петербург", None, None, "Санкт-Петербург"
        
    clean_q = query.strip()
    
    # 1. Проверяем совпадение со спотами СПб
    for key, spot in SPB_SPOTS.items():
        if (clean_q.lower() == key.lower() or 
            clean_q.lower() in spot["name"].lower() or 
            spot["name"].lower() in clean_q.lower() or
            spot["search_city"].lower() in clean_q.lower()):
            return spot["search_city"], spot["lat"], spot["lon"], spot["name"]
            
    # 2. Очищаем от эмодзи и спецсимволов для обычного запроса по городу
    cleaned = re.sub(r'[^\w\s-]', '', clean_q).strip()
    return cleaned or clean_q, None, None, clean_q

def spot_rating(speed: float) -> str:
    """Оценка условий катания на споте."""
    if speed < 4:
        return "❌ Слабый ветер (не подходит для катания)"
    elif speed < 8:
        return "⚠️ Умеренный (для учеников и больших кайтов)"
    elif speed < 14:
        return "✅ Идеальные условия для катания!"
    elif speed < 20:
        return "🔥 Сильный ветер (отличная каталка!)"
    else:
        return "⚡ Штормовые условия (только опытным райдерам!)"

# Хранилище данных
def default_user_dict():
    return {
        "cities": [],
        "last_city": "Санкт-Петербург",
        "wind_history": {},       # city -> [(timestamp_str, speed, deg)]
        "alerts": {"enabled": False, "threshold": 15},
        "last_alert": {},         # city -> timestamp_str
        "weekly_cache": {}        # city -> {"timestamp": str, "text": str}
    }

user_data = defaultdict(default_user_dict)

def load_user_data():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                for uid_str, u_dict in raw_data.items():
                    uid = int(uid_str)
                    user_data[uid].update(u_dict)
                    if "wind_history" not in user_data[uid]:
                        user_data[uid]["wind_history"] = {}
                    if "last_alert" not in user_data[uid]:
                        user_data[uid]["last_alert"] = {}
                    if "weekly_cache" not in user_data[uid]:
                        user_data[uid]["weekly_cache"] = {}
            logging.info("Данные пользователей успешно загружены.")
        except Exception as e:
            logging.error(f"Ошибка загрузки данных: {e}")

def save_user_data():
    try:
        data_to_save = {}
        for uid, u_dict in user_data.items():
            data_to_save[str(uid)] = {
                "cities": u_dict.get("cities", []),
                "last_city": u_dict.get("last_city"),
                "wind_history": u_dict.get("wind_history", {}),
                "alerts": u_dict.get("alerts", {"enabled": False, "threshold": 15}),
                "last_alert": u_dict.get("last_alert", {}),
                "weekly_cache": u_dict.get("weekly_cache", {})
            }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения данных: {e}")

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(level=logging.INFO)

# ===== ИНИЦИАЛИЗАЦИЯ =====
bot = Bot(token=TOKEN) if TOKEN else None
dp = Dispatcher()

# ===== ФУНКЦИИ РАБОТЫ С ПОГОДОЙ =====

async def get_current_wind(query: str, lat: float = None, lon: float = None):
    """Текущий ветер по названию или координатам. Возвращает (data_dict, error_message)."""
    if lat is None or lon is None:
        search_city, spot_lat, spot_lon, display_title = resolve_location(query)
        if spot_lat is not None and spot_lon is not None:
            lat, lon = spot_lat, spot_lon
        else:
            query = search_city

    if not OPENWEATHER_API_KEY:
        return None, "Не установлен OPENWEATHER_API_KEY в файле .env"
    
    url = "https://api.openweathermap.org/data/2.5/weather"
    if lat is not None and lon is not None:
        params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ru"}
    else:
        params = {"q": query, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ru"}
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    wind = d.get("wind", {})
                    main = d.get("main", {})
                    pressure_mmHg = round(main.get("pressure", 1013) * 0.750062)
                    return {
                        "city": d.get("name", query),
                        "country": d.get("sys", {}).get("country", ""),
                        "speed": wind.get("speed", 0.0),
                        "gust": wind.get("gust", 0.0),
                        "deg": wind.get("deg", 0),
                        "temp": main.get("temp", 0.0),
                        "feels_like": main.get("feels_like", 0.0),
                        "humidity": main.get("humidity", 0),
                        "pressure": pressure_mmHg,
                        "description": d.get("weather", [{}])[0].get("description", ""),
                        "lat": d.get("coord", {}).get("lat", 0.0),
                        "lon": d.get("coord", {}).get("lon", 0.0),
                        "timestamp": datetime.now()
                    }, None
                elif resp.status == 404:
                    return None, f"Город «{query}» не найден."
                elif resp.status == 401:
                    return None, "Неверный OpenWeather API ключ (401 Unauthorized)."
                else:
                    return None, f"Ошибка сервиса погоды (код {resp.status})."
    except Exception as e:
        return None, f"Ошибка сети при запросе погоды: {e}"

async def get_forecast_raw(query: str, lat: float = None, lon: float = None):
    """Сырые данные прогноза на 5-7 дней. Возвращает (forecast_list, city_name, error_message)."""
    display_title = query
    if lat is None or lon is None:
        search_city, spot_lat, spot_lon, display_title = resolve_location(query)
        if spot_lat is not None and spot_lon is not None:
            lat, lon = spot_lat, spot_lon
        else:
            query = search_city

    if not OPENWEATHER_API_KEY:
        return None, None, "Не установлен OPENWEATHER_API_KEY в файле .env"
        
    url = "https://api.openweathermap.org/data/2.5/forecast"
    if lat is not None and lon is not None:
        params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ru"}
    else:
        params = {"q": query, "appid": OPENWEATHER_API_KEY, "units": "metric", "lang": "ru"}
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    d = await resp.json()
                    forecasts = []
                    city_name = d.get("city", {}).get("name", display_title)
                    for item in d.get("list", []):
                        wind = item.get("wind", {})
                        main = item.get("main", {})
                        forecasts.append({
                            "time": datetime.fromtimestamp(item["dt"]),
                            "speed": wind.get("speed", 0.0),
                            "deg": wind.get("deg", 0),
                            "gust": wind.get("gust", 0.0),
                            "temp": main.get("temp", 0.0),
                            "pressure": round(main.get("pressure", 1013) * 0.750062),
                            "humidity": main.get("humidity", 0),
                            "description": item.get("weather", [{}])[0].get("description", "")
                        })
                    return forecasts, city_name, None
                elif resp.status == 404:
                    return None, None, f"Город «{query}» не найден."
                elif resp.status == 401:
                    return None, None, "Неверный OpenWeather API ключ (401 Unauthorized)."
                else:
                    return None, None, f"Ошибка прогноза (код {resp.status})."
    except Exception as e:
        return None, None, f"Ошибка сети: {e}"

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
        f"\n🌡️ <b>Температура:</b> {data['temp']:.1f}°C (ощущается как {data.get('feels_like', data['temp']):.1f}°C)\n"
        f"📊 <b>Давление:</b> {data.get('pressure', 760)} мм рт.ст.\n"
        f"💧 <b>Влажность:</b> {data.get('humidity', 50)}%\n"
        f"☁️ {data['description'].capitalize()}\n"
        f"\n🕐 {data['timestamp'].strftime('%H:%M:%S')}"
    )
    return msg

def record_wind_history(user_id: int, city: str, speed: float, deg: int, ts: datetime):
    city_key = city.lower()
    hist = user_data[user_id]["wind_history"].setdefault(city_key, [])
    hist.append((ts.strftime("%Y-%m-%d %H:%M:%S"), speed, deg))
    if len(hist) > 50:
        user_data[user_id]["wind_history"][city_key] = hist[-50:]
    save_user_data()

# ===== ГРАФИКИ И ИНФОГРАФИКА =====

async def create_detailed_infographic_chart(forecasts: list, city: str) -> io.BytesIO:
    """Создаёт подробный инфографический график: Ветер + Порывы + Температура + Давление."""
    if not forecasts:
        return None
        
    times = [f["time"] for f in forecasts]
    speeds = [f["speed"] for f in forecasts]
    gusts = [f.get("gust", 0) for f in forecasts]
    temps = [f["temp"] for f in forecasts]
    pressures = [f.get("pressure", 760) for f in forecasts]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), dpi=110, sharex=True)
    fig.patch.set_facecolor('#181825')

    for ax in (ax1, ax2):
        ax.set_facecolor('#1e1e2e')
        ax.tick_params(colors='#cdd6f4', labelsize=10)
        ax.xaxis.label.set_color('#cdd6f4')
        ax.yaxis.label.set_color('#cdd6f4')
        for spine in ax.spines.values():
            spine.set_color('#45475a')
        ax.grid(True, linestyle='--', alpha=0.25, color='#45475a')

    # Панель 1: Скорость и порывы ветра
    ax1.plot(times, speeds, color='#89b4fa', linewidth=2.5, marker='o', markersize=4, label='Скорость (м/с)')
    if any(g > 0 for g in gusts):
        ax1.plot(times, gusts, color='#f38ba8', linestyle='--', linewidth=1.8, marker='^', markersize=4, label='Порывы (м/с)')
    ax1.fill_between(times, speeds, alpha=0.25, color='#89b4fa')
    
    # Пороговые линии ветра
    ax1.axhline(y=5, color='green', linestyle='--', alpha=0.4, label='Слабый (5 м/с)')
    ax1.axhline(y=10, color='orange', linestyle='--', alpha=0.4, label='Умеренный (10 м/с)')
    ax1.axhline(y=15, color='red', linestyle='--', alpha=0.4, label='Сильный (15 м/с)')

    ax1.set_ylabel('Скорость ветра (м/с)', fontsize=11, fontweight='bold', color='#89b4fa')
    ax1.set_title(f'Подробный метео-анализ: {city}', fontsize=13, fontweight='bold', color='#f5e0dc', pad=12)
    ax1.legend(loc='upper left', facecolor='#313244', edgecolor='#45475a', labelcolor='#cdd6f4', fontsize=9)

    # Панель 2: Температура и Давление
    color_temp = '#fab387'
    ax2.plot(times, temps, color=color_temp, linewidth=2, marker='s', markersize=4, label='Температура (°C)')
    ax2.set_ylabel('Температура (°C)', color=color_temp, fontsize=11, fontweight='bold')
    ax2.tick_params(axis='y', labelcolor=color_temp)

    ax2_press = ax2.twinx()
    color_press = '#a6e3a1'
    ax2_press.plot(times, pressures, color=color_press, linestyle=':', linewidth=2, marker='d', markersize=4, label='Давление (мм)')
    ax2_press.set_ylabel('Давление (мм рт.ст.)', color=color_press, fontsize=11, fontweight='bold')
    ax2_press.tick_params(axis='y', labelcolor=color_press)
    ax2_press.spines['right'].set_color('#45475a')

    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
    plt.xticks(rotation=35)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close()
    return buf

async def create_wind_rose(raw_history: list, city: str) -> io.BytesIO:
    """Создаёт розу ветров."""
    if len(raw_history) < 3:
        return None
    
    parsed = []
    for h in raw_history:
        try:
            parsed.append((h[1], h[2])) # speed, deg
        except Exception:
            pass
            
    if len(parsed) < 3:
        return None
        
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'), dpi=100)
    
    degs = [p[1] for p in parsed]
    speeds = [p[0] for p in parsed]
    
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
    ax.bar(theta, avg_speeds, width=0.6, bottom=0.0, alpha=0.7, color='skyblue', edgecolor='navy')
    
    ax.set_xticks(theta)
    ax.set_xticklabels(['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'])
    ax.set_title(f'Роза ветров: {city}', fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

# ===== ВНОСИМ КНОПКИ ДЛЯ СТАРТА =====

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏄‍♂️ Споты СПб и области", callback_data="spb_spots_menu")],
        [InlineKeyboardButton(text="🌬️ Ветер сейчас", callback_data="check_wind"),
         InlineKeyboardButton(text="📅 На неделю (7д)", callback_data="week_prompt")],
        [InlineKeyboardButton(text="📊 Инфо-График", callback_data="charts_menu"),
         InlineKeyboardButton(text="📍 Мои города", callback_data="my_tracking")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="alerts_menu"),
         InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

# ===== ЛОГИЧЕСКИЕ ОБРАБОТЧИКИ =====

async def show_city_wind(user_id: int, city: str, send_func):
    search_city, lat, lon, display_title = resolve_location(city)
    data, err = await get_current_wind(search_city, lat=lat, lon=lon)
    if err:
        await send_func(f"❌ {err}")
        return
        
    user_data[user_id]["last_city"] = display_title
    record_wind_history(user_id, data["city"], data["speed"], data["deg"], data["timestamp"])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{display_title}")],
        [InlineKeyboardButton(text="📊 График", callback_data=f"chart:{display_title}")],
        [InlineKeyboardButton(text="📅 Прогноз 24ч", callback_data=f"forecast:{display_title}")],
        [InlineKeyboardButton(text="📅 На неделю (7д)", callback_data=f"week:{display_title}")],
        [InlineKeyboardButton(text="🗺️ Карта Windy", callback_data=f"map:{display_title}")],
        [InlineKeyboardButton(text="📍 В избранное", callback_data=f"track:{display_title}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await send_func(format_wind(data), reply_markup=kb, parse_mode=ParseMode.HTML)

async def show_city_week_forecast(user_id: int, city: str, send_func):
    search_city, lat, lon, display_title = resolve_location(city)
    now = datetime.now()
    cache = user_data[user_id]["weekly_cache"].get(display_title.lower())
    
    if cache:
        try:
            cache_time = datetime.strptime(cache["timestamp"], "%Y-%m-%d %H:%M:%S")
            if now - cache_time < timedelta(hours=12):
                await send_func(cache["text"], parse_mode=ParseMode.HTML)
                return
        except Exception:
            pass
            
    raw_forecasts, city_name, err = await get_forecast_raw(search_city, lat=lat, lon=lon)
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
    
    user_data[user_id]["weekly_cache"][display_title.lower()] = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "text": full_text
    }
    save_user_data()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Подробный график", callback_data=f"chart:{display_title}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")]
    ])
    await send_func(full_text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def show_city_chart(user_id: int, city: str, send_photo_func, send_text_func):
    search_city, lat, lon, display_title = resolve_location(city)
    raw_forecasts, city_name, err = await get_forecast_raw(search_city, lat=lat, lon=lon)
    if err or not raw_forecasts:
        await send_text_func(f"❌ {err or 'Не удалось получить данные для графика.'}")
        return
        
    title_name = display_title if display_title else city_name
    chart_buf = await create_detailed_infographic_chart(raw_forecasts[:16], title_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 На неделю", callback_data=f"week:{display_title}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await send_photo_func(
        types.BufferedInputFile(chart_buf.getvalue(), filename="chart.png"),
        caption=f"📊 <b>Информативный график метео-анализа: {title_name}</b>\n(Скорость, Порывы, Пороговые линии, Температура, Давление)",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

async def show_city_forecast_24h(user_id: int, city: str, send_photo_func, send_text_func):
    search_city, lat, lon, display_title = resolve_location(city)
    raw_forecasts, city_name, err = await get_forecast_raw(search_city, lat=lat, lon=lon)
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data=f"week:{display_title}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
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
    data, err = await get_current_wind(search_city, lat=lat, lon=lon)
    if err:
        await send_func(f"❌ {err}")
        return
    
    spot_lat = data["lat"] if lat is None else lat
    spot_lon = data["lon"] if lon is None else lon
    map_url = f"https://www.windy.com/?{spot_lat},{spot_lon},9"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺️ Открыть карту Windy.com", url=map_url)],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    
    await send_func(
        f"🗺️ <b>Интерактивная карта ветров: {display_title}</b>\n\n"
        f"📍 Координаты: {spot_lat:.4f}, {spot_lon:.4f}\n"
        f"Нажми кнопку ниже для перехода на интерактивную карту Windy.com.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

# ===== КОМАНДЫ =====

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name if message.from_user else "друг"
    await message.answer(
        f"👋 Привет, {user_name}!\n\n"
        f"🌬️ <b>Wind Tracker Bot — твой метео-помощник и трекер ветра</b>\n\n"
        f"Что я умею:\n"
        f"• 🏄‍♂️ <b>Споты Санкт-Петербурга:</b> готовый прогноз для Дюн, Кронштадта, Лахты, Ладоги с оценкой катания\n"
        f"• 📅 <b>Прогноз на неделю (5-7 дней):</b> с ежедневной перепроверкой\n"
        f"• 📊 <b>Подробный инфо-график:</b> скорость, порывы, температура, давление\n"
        f"• 🧭 <b>Роза ветров и карты Windy.com</b>\n"
        f"• 🔔 <b>Push-уведомления при сильном ветре</b>\n\n"
        f"Используй кнопки ниже или команды:\n"
        f"/spb — споты СПб и Ленобласти\n"
        f"/wind [город] — ветер сейчас\n"
        f"/week [город] — прогноз на неделю\n"
        f"/chart [город] — наглядный инфо-график\n"
        f"/track [город] — отслеживать",
        reply_markup=get_start_keyboard(), parse_mode=ParseMode.HTML
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Полный справочник команд:</b>\n\n"
        "<b>🏄‍♂️ Споты СПб:</b>\n"
        "/spb — быстрый выбор ветра на спотах СПб (Кронштадт, Дюны, Лахта, Ладога и др.) с оценкой условий\n\n"
        "<b>🌬️ Погода и прогнозы:</b>\n"
        "/wind [город] — текущий ветер и температура\n"
        "/forecast [город] — почасовой прогноз на 24 часа\n"
        "/week [город] — подробный прогноз на 5-7 дней с перепроверкой\n"
        "/map [город] — интерактивная карта ветров Windy.com\n\n"
        "<b>📊 Аналитика и графики:</b>\n"
        "/chart [город] — информативный график (ветер, порывы, давление, temp)\n"
        "/rose [город] — роза ветров\n\n"
        "<b>📍 Избранное и Уведомления:</b>\n"
        "/track [город] — добавить в избранные споты\n"
        "/untrack [город] — удалить из избранного\n"
        "/mywind — сводка по всем твоим городам\n"
        "/alert [скорость] — включить уведомление при ветре > X м/с\n"
        "/alert off — выключить",
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("spb"))
async def cmd_spb(message: types.Message):
    kb_rows = []
    for key, data in SPB_SPOTS.items():
        kb_rows.append([InlineKeyboardButton(text=data["name"], callback_data=f"spot:{key}")])
    kb_rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")])
    
    await message.answer(
        "🏄‍♂️ <b>Популярные ветровые споты Санкт-Петербурга и Ленобласти:</b>\n\n"
        "Выбери спот для получения текущего ветра, оценки катания, прогноза и карты Windy:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        parse_mode=ParseMode.HTML
    )

@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else (user_data[uid]["last_city"] or "Санкт-Петербург")
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_week_forecast(uid, city, message.answer)

@dp.message(Command("wind"))
async def cmd_wind(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else (user_data[uid]["last_city"] or "Санкт-Петербург")
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_wind(uid, city, message.answer)

@dp.message(Command("forecast"))
async def cmd_forecast(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else (user_data[uid]["last_city"] or "Санкт-Петербург")
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_forecast_24h(uid, city, message.answer_photo, message.answer)

@dp.message(Command("chart"))
async def cmd_chart(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else (user_data[uid]["last_city"] or "Санкт-Петербург")
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    await show_city_chart(uid, city, message.answer_photo, message.answer)

@dp.message(Command("rose"))
async def cmd_rose(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else (user_data[uid]["last_city"] or "Санкт-Петербург")
    search_city, lat, lon, display_title = resolve_location(city)
    history = user_data[uid]["wind_history"].get(search_city.lower(), []) or user_data[uid]["wind_history"].get(display_title.lower(), [])
    rose_buf = await create_wind_rose(history, display_title)
    
    if not rose_buf:
        await message.answer(
            f"🧭 Недостаточно данных для розы ветров «{display_title}».\n"
            f"Запроси ветер несколько раз: /wind {display_title}"
        )
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    await message.answer_photo(
        types.BufferedInputFile(rose_buf.getvalue(), filename="rose.png"),
        caption=f"🧭 <b>Роза ветров: {display_title}</b>\n\nПоказывает преобладающие направления ветра.",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )

@dp.message(Command("map"))
async def cmd_map(message: types.Message):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id
    city = args[1].strip() if len(args) >= 2 else (user_data[uid]["last_city"] or "Санкт-Петербург")
    await message.bot.send_chat_action(message.chat.id, "typing")
    await show_city_map(uid, city, message.answer)

@dp.message(Command("track"))
async def cmd_track(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажи город: /track Москва")
        return
    
    city = args[1].strip()
    uid = message.from_user.id
    search_city, lat, lon, display_title = resolve_location(city)
    data, err = await get_current_wind(search_city, lat=lat, lon=lon)
    if err:
        await message.answer(f"❌ {err}")
        return
    
    cities = user_data[uid]["cities"]
    if display_title.lower() not in [c.lower() for c in cities]:
        cities.append(display_title)
        save_user_data()
        await message.answer(
            f"✅ <b>{display_title}</b> добавлен в избранное!\n\n"
            f"Используй /mywind для быстрого просмотра.",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(f"⚠️ <b>{display_title}</b> уже в избранном.", parse_mode=ParseMode.HTML)

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
    save_user_data()
    await message.answer(f"✅ «{city}» удалён из списка.")

@dp.message(Command("mywind"))
async def cmd_mywind(message: types.Message):
    uid = message.from_user.id
    cities = user_data[uid]["cities"]
    
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
        data, err = await get_current_wind(search_city, lat=lat, lon=lon)
        if data:
            e = wind_emoji(data["speed"])
            results.append(
                f"{e} <b>{display_title}</b>: "
                f"{data['speed']:.1f} м/с, {wind_direction(data['deg'])}"
            )
            record_wind_history(uid, display_title, data["speed"], data["deg"], data["timestamp"])
    
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
            f"/alert [скорость] — например: /alert 15\n"
            f"/alert off — выключить",
            parse_mode=ParseMode.HTML
        )
        return
    
    param = args[1].strip().lower()
    
    if param == "off":
        user_data[uid]["alerts"]["enabled"] = False
        save_user_data()
        await message.answer("🔕 Уведомления <b>выключены</b>.", parse_mode=ParseMode.HTML)
        return
    
    try:
        threshold = float(param)
        if threshold < 0 or threshold > 50:
            await message.answer("❌ Укажи значение от 0 до 50 м/с.")
            return
        
        user_data[uid]["alerts"]["enabled"] = True
        user_data[uid]["alerts"]["threshold"] = threshold
        save_user_data()
        
        await message.answer(
            f"🔔 <b>Уведомления включены!</b>\n\n"
            f"Проверка ветра каждые 30 минут. При ветре выше <b>{threshold} м/с</b> пришлю сообщение!\n"
            f"Добавить город: /track [город]",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer("❌ Укажи число: /alert 15")

# ===== CALLBACK ОБРАБОТЧИКИ =====

@dp.callback_query(F.data == "spb_spots_menu")
async def cb_spb_spots_menu(callback: types.CallbackQuery):
    await cmd_spb(callback.message)
    await callback.answer()

@dp.callback_query(F.data.startswith("spot:"))
async def cb_spot_select(callback: types.CallbackQuery):
    spot_key = callback.data.split(":", 1)[1]
    spot = SPB_SPOTS.get(spot_key)
    
    if not spot:
        await callback.answer("Спот не найден.")
        return
        
    await callback.bot.send_chat_action(callback.message.chat.id, "typing")
    data, err = await get_current_wind(spot["search_city"], lat=spot["lat"], lon=spot["lon"])
    
    if err:
        await callback.message.answer(f"❌ {err}")
        await callback.answer()
        return
        
    user_id = callback.from_user.id
    user_data[user_id]["last_city"] = spot["name"]
    record_wind_history(user_id, spot["name"], data["speed"], data["deg"], data["timestamp"])
    
    map_url = f"https://www.windy.com/?{spot['lat']},{spot['lon']},10"
    rating = spot_rating(data["speed"])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺️ Открыть спот на Windy.com", url=map_url)],
        [InlineKeyboardButton(text="📊 Подробный график", callback_data=f"chart:{spot_key}")],
        [InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data=f"week:{spot_key}")],
        [InlineKeyboardButton(text="🏄‍♂️ Все споты СПб", callback_data="spb_spots_menu")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")]
    ])
    
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
    
    await callback.message.answer(msg, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "check_wind")
async def cb_check_wind(callback: types.CallbackQuery):
    await callback.message.answer("🌬️ Напиши город: /wind [город] или выбери /spb")
    await callback.answer()

@dp.callback_query(F.data == "charts_menu")
async def cb_charts_menu(callback: types.CallbackQuery):
    uid = callback.from_user.id
    city = user_data[uid]["last_city"] or "Санкт-Петербург"
    await show_city_chart(uid, city, callback.message.answer_photo, callback.message.answer)
    await callback.answer()

@dp.callback_query(F.data == "week_prompt")
async def cb_week_prompt(callback: types.CallbackQuery):
    uid = callback.from_user.id
    city = user_data[uid]["last_city"] or "Санкт-Петербург"
    await show_city_week_forecast(uid, city, callback.message.answer)
    await callback.answer()

@dp.callback_query(F.data.startswith("week:"))
async def cb_week_city(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_week_forecast(uid, city, callback.message.answer)
    await callback.answer()

@dp.callback_query(F.data == "my_tracking")
async def cb_my_tracking(callback: types.CallbackQuery):
    await cmd_mywind(callback.message)
    await callback.answer()

@dp.callback_query(F.data == "alerts_menu")
async def cb_alerts(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Настроить порог", callback_data="alert_on_prompt")],
        [InlineKeyboardButton(text="🔕 Выключить", callback_data="alert_off")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
    await callback.message.answer(
        "🔔 <b>Уведомления о сильном ветре</b>\n\n"
        "Я буду проверять ветер каждые 30 минут и предупреждать "
        "при превышении заданного порога!",
        reply_markup=kb, parse_mode=ParseMode.HTML
    )
    await callback.answer()

@dp.callback_query(F.data == "alert_on_prompt")
async def cb_alert_on(callback: types.CallbackQuery):
    await callback.message.answer("Напиши: /alert [порог в м/с]\nПример: /alert 15")
    await callback.answer()

@dp.callback_query(F.data == "alert_off")
async def cb_alert_off(callback: types.CallbackQuery):
    user_data[callback.from_user.id]["alerts"]["enabled"] = False
    save_user_data()
    await callback.message.answer("🔕 Уведомления выключены.")
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
    search_city, lat, lon, display_title = resolve_location(city)
    data, err = await get_current_wind(search_city, lat=lat, lon=lon)
    if data:
        uid = callback.from_user.id
        record_wind_history(uid, display_title, data["speed"], data["deg"], data["timestamp"])
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{display_title}")],
            [InlineKeyboardButton(text="📊 Инфо-График", callback_data=f"chart:{display_title}")],
            [InlineKeyboardButton(text="📅 На неделю", callback_data=f"week:{display_title}")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
        ])
        await callback.message.edit_text(format_wind(data), reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await callback.message.answer(f"❌ {err}")
    await callback.answer("Обновлено!")

@dp.callback_query(F.data.startswith("chart:"))
async def cb_chart(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_chart(uid, city, callback.message.answer_photo, callback.message.answer)
    await callback.answer()

@dp.callback_query(F.data.startswith("forecast:"))
async def cb_forecast(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_forecast_24h(uid, city, callback.message.answer_photo, callback.message.answer)
    await callback.answer()

@dp.callback_query(F.data.startswith("map:"))
async def cb_map(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    await show_city_map(uid, city, callback.message.answer)
    await callback.answer()

@dp.callback_query(F.data.startswith("track:"))
async def cb_track(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    search_city, lat, lon, display_title = resolve_location(city)
    cities = user_data[uid]["cities"]
    
    if display_title.lower() not in [c.lower() for c in cities]:
        cities.append(display_title)
        save_user_data()
        await callback.answer(f"✅ {display_title} добавлен!")
    else:
        await callback.answer(f"⚠️ Уже в избранном!")

@dp.callback_query(F.data.startswith("untrack:"))
async def cb_untrack(callback: types.CallbackQuery):
    city = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    user_data[uid]["cities"] = [c for c in user_data[uid]["cities"] if c.lower() != city.lower()]
    save_user_data()
    await callback.answer(f"❌ {city} удалён!")
    await cmd_mywind(callback.message)

@dp.callback_query(F.data == "refresh_all")
async def cb_refresh_all(callback: types.CallbackQuery):
    await cmd_mywind(callback.message)
    await callback.answer("Обновлено!")

# ===== ФОНОВАЯ ЗАДАЧА: ПРОВЕРКА УВЕДОМЛЕНИЙ =====

async def check_alerts():
    """Каждые 30 минут проверяет ветер в избранных городах."""
    while True:
        await asyncio.sleep(1800)
        
        if not bot:
            continue

        now = datetime.now()
        for uid, data in user_data.items():
            if not data.get("alerts", {}).get("enabled"):
                continue
            
            threshold = data["alerts"]["threshold"]
            last_alert_map = data.get("last_alert", {})
            
            for city in data.get("cities", []):
                try:
                    last_alert_str = last_alert_map.get(city.lower())
                    if last_alert_str:
                        last_alert_time = datetime.strptime(last_alert_str, "%Y-%m-%d %H:%M:%S")
                        if now - last_alert_time < timedelta(hours=3):
                            continue

                    search_city, lat, lon, display_title = resolve_location(city)
                    wind_data, err = await get_current_wind(search_city, lat=lat, lon=lon)
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
                        last_alert_map[city.lower()] = now.strftime("%Y-%m-%d %H:%M:%S")
                        save_user_data()
                except Exception as e:
                    logging.error(f"Alert error for user {uid}, city {city}: {e}")

# ===== ЗАПУСК =====

async def main():
    load_user_data()
    
    if not TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не задан в файле .env!")
        return
        
    if not OPENWEATHER_API_KEY:
        print("⚠️ ПРЕДУПРЕЖДЕНИЕ: OPENWEATHER_API_KEY не задан в файле .env!")
        
    asyncio.create_task(check_alerts())
    
    print("🌬️ Wind Tracker Bot запущен!")
    print("🏄‍♂️ Меню спотов Санкт-Петербурга и Ленобласти подключено.")
    print("📅 Прогноз на неделю и инфо-графики доступны.")
    print("🔔 Фоновая проверка уведомлений активна (каждые 30 мин)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())