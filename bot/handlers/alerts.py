from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from bot.database.db import get_user_alerts, set_user_alerts
from bot.keyboards.inline import get_alerts_keyboard, get_back_home_keyboard
from bot.states import AlertState

router = Router()

@router.message(Command("alert"))
async def cmd_alert(message: types.Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    uid = message.from_user.id

    if len(args) < 2:
        status = await get_user_alerts(uid)
        enabled = "✅ Включены" if status["enabled"] else "❌ Выключены"
        await message.answer(
            f"🔔 <b>Уведомления о сильном ветре</b>\n\n"
            f"Статус: {enabled}\n"
            f"Порог: {status['threshold']} м/с\n\n"
            f"Используй:\n"
            f"/alert [скорость] — например: /alert 15\n"
            f"/alert off — выключить",
            reply_markup=get_alerts_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return

    param = args[1].strip().lower()

    if param == "off":
        await set_user_alerts(uid, enabled=False)
        await state.clear()
        await message.answer("🔕 Уведомления <b>выключены</b>.", parse_mode=ParseMode.HTML)
        return

    try:
        threshold = float(param)
        if threshold < 0 or threshold > 50:
            await message.answer("❌ Укажи значение от 0 до 50 м/с.")
            return

        await set_user_alerts(uid, enabled=True, threshold=threshold)
        await state.clear()
        await message.answer(
            f"🔔 <b>Уведомления включены!</b>\n\n"
            f"Проверка ветра каждые 30 минут. При ветре выше <b>{threshold} м/с</b> пришлю сообщение!\n"
            f"Добавить город: /track [город]",
            reply_markup=get_back_home_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer("❌ Укажи число: /alert 15")

# ----- FSM ОБРАБОТЧИК ВВОДА ПОРОГА ВЕТРА -----

@router.callback_query(F.data == "alert_on_prompt")
async def cb_alert_on_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AlertState.waiting_for_threshold)
    await callback.message.answer(
        "⌨️ Напиши желаемый порог ветра в м/с (число от 1 до 50):\nНапример: <b>12</b> или <b>15</b>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@router.message(AlertState.waiting_for_threshold)
async def process_threshold_input(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    try:
        threshold = float(message.text.strip().replace(',', '.'))
        if threshold < 0 or threshold > 50:
            await message.answer("❌ Пожалуйста, введи число от 1 до 50.")
            return

        await set_user_alerts(uid, enabled=True, threshold=threshold)
        await state.clear()
        await message.answer(
            f"🔔 <b>Уведомления успешно включены!</b>\n\n"
            f"Порог: <b>{threshold} м/с</b>\n"
            f"Добавить город в отслеживание: /track [город]",
            reply_markup=get_back_home_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer("❌ Ошибка ввода. Пожалуйста, введи только число (например: 15):")

@router.callback_query(F.data == "alerts_menu")
async def cb_alerts_menu(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    status = await get_user_alerts(uid)
    enabled = "✅ Включены" if status["enabled"] else "❌ Выключены"

    await callback.message.answer(
        f"🔔 <b>Уведомления о сильном ветре</b>\n\n"
        f"Текущий статус: {enabled}\n"
        f"Порог: <b>{status['threshold']} м/с</b>\n\n"
        f"Я буду проверять ветер каждые 30 минут и предупреждать "
        f"при превышении заданного порога!",
        reply_markup=get_alerts_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@router.callback_query(F.data == "alert_off")
async def cb_alert_off(callback: types.CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    await set_user_alerts(uid, enabled=False)
    await state.clear()
    await callback.message.answer("🔕 Уведомления выключены.", reply_markup=get_back_home_keyboard())
    await callback.answer()
