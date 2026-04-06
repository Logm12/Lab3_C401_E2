import json
import os
import time
from datetime import datetime, date as date_type
from typing import Any, Dict, List, Optional

import requests


USER_AGENT = "travelbot-lab/1.0"


def _get_tavily_api_key() -> Optional[str]:
    return os.getenv("TAVILY_API_KEY") or os.getenv("TAVI_API_KEY")
def get_weather(location: str, date: str) -> str:
    try:
        forecast_date     = _normalize_date(date)
        forecast_date_obj = datetime.strptime(forecast_date, "%Y-%m-%d").date()
        delta             = (forecast_date_obj - date_type.today()).days

        if delta < 0 or delta > 16:
            return _safe_json({
                "error": (
                    f"Ngày {forecast_date} nằm ngoài phạm vi dự báo. "
                    f"Open-Meteo chỉ hỗ trợ dự báo từ 0 đến 16 ngày kể từ hôm nay."
                )
            })

        geo = _http_get(
            "https://nominatim.openstreetmap.org/search",
            {"q": location, "format": "json", "limit": 1},
        )
        if not geo:
            return _safe_json({"error": f"Không tìm thấy địa điểm: {location}"})

        lat = float(geo[0]["lat"])
        lon = float(geo[0]["lon"])

        weather = _http_get(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude":   lat,
                "longitude":  lon,
                "daily":      "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone":   "auto",
                "start_date": forecast_date,
                "end_date":   forecast_date,
            },
        )
        daily = weather.get("daily", {})
        return _safe_json({
            "location":    location,
            "date":        forecast_date,
            "coordinates": {"lat": lat, "lon": lon},
            "source":      "open-meteo + nominatim",
            "weather": {
                "weathercode":          (daily.get("weathercode")        or [None])[0],
                "temperature_max_c":    (daily.get("temperature_2m_max") or [None])[0],
                "temperature_min_c":    (daily.get("temperature_2m_min") or [None])[0],
                "precipitation_sum_mm": (daily.get("precipitation_sum")  or [None])[0],
            },
        })
    except Exception as error:
        return _safe_json({"error": f"Lỗi Weather API: {str(error)}"})
