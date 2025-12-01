from typing import Optional
import requests

from config import load_settings

_settings = load_settings()


def get_weather(city: Optional[str] = None) -> str:
    if not _settings.openweather_api_key:
        return "Weather API key is not configured."

    target_city = city or _settings.default_city

    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": target_city,
                "appid": _settings.openweather_api_key,
                "units": "metric",
                "lang": "en",
            },
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"Failed to fetch weather: {e}"

    try:
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        feels = data["main"]["feels_like"]
        hum = data["main"]["humidity"]
        return (
            f"Weather in {target_city}: {desc}, {temp:.1f}°C "
            f"(feels like {feels:.1f}°C), humidity {hum}%."
        )
    except Exception:
        return "Got unexpected weather data format."
