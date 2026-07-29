import logging
import aiohttp
from datetime import datetime
from config import OPENWEATHER_API_KEY
from bot.utils.location import resolve_location

logger = logging.getLogger(__name__)

class WeatherService:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

    async def start(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.info("HTTP-сессия aiohttp открыта.")

    async def stop(self):
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("HTTP-сессия aiohttp закрыта.")

    async def get_current_wind(self, query: str, lat: float = None, lon: float = None):
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
            if not self.session:
                await self.start()

            async with self.session.get(url, params=params) as resp:
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
            logger.error(f"Ошибка сети get_current_wind: {e}")
            return None, f"Ошибка сети при запросе погоды: {e}"

    async def get_forecast_raw(self, query: str, lat: float = None, lon: float = None):
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
            if not self.session:
                await self.start()

            async with self.session.get(url, params=params) as resp:
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
            logger.error(f"Ошибка сети get_forecast_raw: {e}")
            return None, None, f"Ошибка сети: {e}"

weather_service = WeatherService()
