import json
import urllib.request
import urllib.parse
from datetime import datetime
import time
from typing import Dict, Optional, Tuple

# Cache dictionary to store responses and prevent rate-limiting.
# Format: {(lat, lon): {"data": dict, "timestamp": float}}
_weather_cache: Dict[Tuple[float, float], Dict] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour cache

def fetch_realtime_weather(lat: float, lon: float) -> Optional[Dict]:
    """
    Fetches real-time precipitation data for a given location using the Open-Meteo API.
    Returns a dictionary with 'rainfall_intensity' (current mm/hr) and 
    'rainfall_24h' (sum of precipitation over the last 24 hours in mm).
    
    Uses an in-memory cache to avoid hitting API rate limits.
    """
    coord_key = (round(lat, 4), round(lon, 4))
    now = time.time()
    
    if coord_key in _weather_cache:
        cached = _weather_cache[coord_key]
        if now - cached["timestamp"] < CACHE_TTL_SECONDS:
            return cached["data"]
            
    # Prepare API request (Open-Meteo)
    # Fetching current precipitation and hourly precipitation for the past 24 hours, plus current temperature
    # Open-Meteo is free for non-commercial use and requires no API key.
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation,temperature_2m&hourly=precipitation&past_hours=24&forecast_hours=1&timezone=Africa%2FAbidjan"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "CHEWS-Flood-Atlas/1.0"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=5.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                
                # Current precipitation (mm/h) and temperature
                current_precip = data.get("current", {}).get("precipitation", 0.0)
                current_temp = data.get("current", {}).get("temperature_2m", 25.0)
                
                # Past 24h precipitation sum
                hourly_precip = data.get("hourly", {}).get("precipitation", [])
                
                # The 'past_hours=24' gives us the last 24 hours + current hour + next hour
                # We'll just sum the first 24 items in the list.
                past_24h_precip = sum(hourly_precip[:24]) if hourly_precip else 0.0
                
                result = {
                    "rainfall_intensity": float(current_precip),
                    "rainfall_24h": float(past_24h_precip),
                    "temperature_2m": float(current_temp)
                }
                
                # Store in cache
                _weather_cache[coord_key] = {
                    "data": result,
                    "timestamp": now
                }
                
                return result
                
    except Exception as e:
        print(f"[WeatherAPI] Failed to fetch weather for {lat},{lon}: {e}")
        return None

    return None
