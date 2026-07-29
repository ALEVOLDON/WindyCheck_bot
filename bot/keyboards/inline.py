from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.constants import SPB_SPOTS

def get_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏄‍♂️ Споты СПб и области", callback_data="spb_spots_menu")],
        [InlineKeyboardButton(text="🌬️ Ветер сейчас", callback_data="check_wind"),
         InlineKeyboardButton(text="📅 На неделю (7д)", callback_data="week_prompt")],
        [InlineKeyboardButton(text="📊 Инфо-График", callback_data="charts_menu"),
         InlineKeyboardButton(text="📍 Мои города", callback_data="my_tracking")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="alerts_menu"),
         InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

def get_spots_keyboard() -> InlineKeyboardMarkup:
    kb_rows = []
    for key, data in SPB_SPOTS.items():
        kb_rows.append([InlineKeyboardButton(text=data["name"], callback_data=f"spot:{key}")])
    kb_rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)

def get_weather_actions_keyboard(display_title: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{display_title}")],
        [InlineKeyboardButton(text="📊 График", callback_data=f"chart:{display_title}")],
        [InlineKeyboardButton(text="📅 Прогноз 24ч", callback_data=f"forecast:{display_title}")],
        [InlineKeyboardButton(text="📅 На неделю (7д)", callback_data=f"week:{display_title}")],
        [InlineKeyboardButton(text="🗺️ Карта Windy", callback_data=f"map:{display_title}")],
        [InlineKeyboardButton(text="📍 В избранное", callback_data=f"track:{display_title}")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])

def get_spot_actions_keyboard(map_url: str, spot_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺️ Открыть спот на Windy.com", url=map_url)],
        [InlineKeyboardButton(text="📊 Подробный график", callback_data=f"chart:{spot_key}")],
        [InlineKeyboardButton(text="📅 Прогноз на неделю", callback_data=f"week:{spot_key}")],
        [InlineKeyboardButton(text="🏄‍♂️ Все споты СПб", callback_data="spb_spots_menu")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="start_menu")]
    ])

def get_alerts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Настроить порог", callback_data="alert_on_prompt")],
        [InlineKeyboardButton(text="🔕 Выключить", callback_data="alert_off")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])

def get_back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Меню", callback_data="start_menu")]
    ])
