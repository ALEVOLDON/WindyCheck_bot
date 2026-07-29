import io
import asyncio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def _sync_create_detailed_infographic_chart(forecasts: list, city: str) -> io.BytesIO | None:
    """Синхронная функция отрисовки инфо-графики на Matplotlib."""
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
    plt.close(fig)
    return buf

def _sync_create_wind_rose(raw_history: list, city: str) -> io.BytesIO | None:
    """Синхронная функция создания розы ветров."""
    if len(raw_history) < 3:
        return None

    parsed = []
    for h in raw_history:
        try:
            # h - это кортеж (timestamp, speed, deg)
            parsed.append((h[1], h[2]))
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
    plt.close(fig)
    return buf

async def create_detailed_infographic_chart(forecasts: list, city: str) -> io.BytesIO | None:
    """Асинхронный вызов генерации инфо-графика в отдельном потоке (не блокирует Event Loop)."""
    return await asyncio.to_thread(_sync_create_detailed_infographic_chart, forecasts, city)

async def create_wind_rose(raw_history: list, city: str) -> io.BytesIO | None:
    """Асинхронный вызов построения розы ветров в отдельном потоке."""
    return await asyncio.to_thread(_sync_create_wind_rose, raw_history, city)
