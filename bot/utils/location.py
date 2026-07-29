import re
from bot.constants import SPB_SPOTS

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
