from aiogram.fsm.state import StatesGroup, State

class AlertState(StatesGroup):
    waiting_for_threshold = State()

class TrackState(StatesGroup):
    waiting_for_city = State()
