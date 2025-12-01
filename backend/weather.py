# backend/weather.py
import httpx
import logging
from datetime import datetime
from backend.database import get_all_settings

logger = logging.getLogger(__name__)

async def get_current_weather() -> str:
    """
    Fetches 5-day forecast from OpenMeteo (Free, No Key).
    """
    try:
        settings = await get_all_settings()
        lat = settings.get("weather_location_lat", "40.7608")
        lon = settings.get("weather_location_lon", "-111.8910")
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
            "forecast_days": 5 
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            
            curr = data.get("current", {})
            daily = data.get("daily", {})
            
            # 1. Current Conditions
            current_temp = curr.get("temperature_2m")
            summary = [f"Right Now: {current_temp}°F"]
            
            # 2. Forecast Loop
            dates = daily.get("time", [])
            highs = daily.get("temperature_2m_max", [])
            lows = daily.get("temperature_2m_min", [])
            rains = daily.get("precipitation_probability_max", [])
            
            for i, date_str in enumerate(dates):
                # Convert "2023-11-25" -> "Saturday"
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    day_name = date_obj.strftime("%A")
                except:
                    day_name = date_str

                # Label Today/Tomorrow for the LLM
                if i == 0: label = "Today"
                elif i == 1: label = "Tomorrow"
                else: label = day_name
                
                # Safety check for list index
                h = highs[i] if i < len(highs) else "?"
                l = lows[i] if i < len(lows) else "?"
                r = rains[i] if i < len(rains) else "?"

                line = f"- {date_str} ({label}): High {h}°F, Low {l}°F, Rain {r}%"
                summary.append(line)
            
            return "\n".join(summary)
            
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        return "Weather unavailable. Please check internet connection or coordinates."