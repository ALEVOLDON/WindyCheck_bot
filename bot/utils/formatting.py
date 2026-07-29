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
