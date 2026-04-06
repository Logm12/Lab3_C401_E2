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
def _safe_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)

def _search_web(
    query: str,
    max_results: int = 5,
    retries: int = 2,
    retry_delay: float = 1.5,
) -> List[Dict[str, str]]:
    """Search the web using Tavily AI API — ưu tiên kết quả tiếng Việt."""
    tavily_api_key = _get_tavily_api_key()
    if not tavily_api_key:
        raise ValueError("TAVILY_API_KEY is not set in environment variables.")

    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key":        tavily_api_key,
                    "query":          query,
                    "max_results":    max_results,
                    "search_depth":   "basic",
                    "include_answer": False,
                    "topic":          "general",
                    "language":       "vi",
                },
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            results = [
                {
                    "title":   r.get("title", ""),
                    "snippet": r.get("content", ""),
                    "url":     r.get("url", ""),
                    "score":   r.get("score", None),
                }
                for r in data.get("results", [])
            ]
            if results:
                return results
            return []
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Tavily search failed after {retries} attempts. Last error: {last_error}"
    )

def get_transport(
    origin: str,
    destination: str,
    date: str,
    transport_type: str = "máy bay",
) -> str:
    query = (
        f"vé {transport_type} từ {origin} đến {destination} "
        f"ngày {date} giá bao nhiêu tiền VND lịch khởi hành"
    )
    try:
        results = _search_web(query, max_results=5)
        return _safe_json({
            "origin":         origin,
            "destination":    destination,
            "date":           date,
            "transport_type": transport_type,
            "currency":       "VND",
            "source":         "tavily",
            "query":          query,
            "results":        results,
        })
    except Exception as error:
        return _safe_json({"error": f"Lỗi tìm phương tiện: {str(error)}", "query": query})
        
def get_accommodation(
    location: str,
    check_in: str,
    check_out: str,
    budget: str,
) -> str:
    query = (
        f"khách sạn tốt tại {location} "
        f"nhận phòng {check_in} trả phòng {check_out} "
        f"giá phòng bao nhiêu VND ngân sách {budget}"
    )
    try:
        results = _search_web(query, max_results=5)
        return _safe_json({
            "location":  location,
            "check_in":  check_in,
            "check_out": check_out,
            "budget":    budget,
            "currency":  "VND",
            "source":    "tavily",
            "query":     query,
            "results":   results,
        })
    except Exception as error:
        return _safe_json({"error": f"Lỗi tìm khách sạn: {str(error)}", "query": query})
