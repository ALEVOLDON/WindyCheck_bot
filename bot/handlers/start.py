from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from bot.keyboards.inline import get_start_keyboard, get_back_home_keyboard

router = Router()

@router.message(Command("start"))
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

@router.message(Command("help"))
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
        reply_markup=get_back_home_keyboard(),
        parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data == "start_menu")
async def cb_start_menu(callback: types.CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()

@router.callback_query(F.data == "help")
async def cb_help(callback: types.CallbackQuery):
    await cmd_help(callback.message)
    await callback.answer()
