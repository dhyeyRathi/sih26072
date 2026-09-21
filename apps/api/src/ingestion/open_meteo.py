"""
Open-Meteo Ingestion Client.
Provides real-time NWP/surface conditions and historical archive access.
No API key required.
"""

import time
import requests
from typing import Dict, Any, Optional
from src.config import settings

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Cache conditions in-memory for 10 minutes (600s)
_CONDITIONS_CACHE: Dict[str, Any] = {}
_LAST_FETCH_TIME: float = 0.0
CACHE_TTL_SECONDS: float = 300.0  # Reduced from 600s for more responsive updates


def get_latest_conditions(
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Fetch current and hourly conditions (temp, humidity, wind, precipitation, CAPE).
    Returns flat dictionary of atmospheric indicators.
    """
    global _CONDITIONS_CACHE, _LAST_FETCH_TIME

    now = time.time()
    if not force_refresh and _CONDITIONS_CACHE and (now - _LAST_FETCH_TIME < CACHE_TTL_SECONDS):
        return _CONDITIONS_CACHE

    target_lat = lat if lat is not None else settings.mvp_center_lat
    target_lon = lon if lon is not None else settings.mvp_center_lon

    params = {
        "latitude": target_lat,
        "longitude": target_lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "precipitation"
        ],
        "hourly": ["cape", "wind_speed_80m", "wind_speed_120m", "wind_direction_80m", "wind_direction_120m"],
        "timezone": "auto",
        "forecast_days": 1
    }

    try:
        resp = requests.get(FORECAST_URL, params=params, timeout=6.0)
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current", {})
        hourly = data.get("hourly", {})
        
        # Extract nearest hourly CAPE index
        cape_list = hourly.get("cape", [])
        current_cape = float(cape_list[0]) if cape_list else 0.0

        conditions = {
            "source": "Open-Meteo (ECMWF/GFS Blend)",
            "latitude": target_lat,
            "longitude": target_lon,
            "temperature_c": float(current.get("temperature_2m", 28.0)),
            "relative_humidity_pct": float(current.get("relative_humidity_2m", 65.0)),
            "surface_pressure_hpa": float(current.get("surface_pressure", 1008.0)),
            "wind_speed_kmh": float(current.get("wind_speed_10m", 12.0)),
            "wind_direction_deg": float(current.get("wind_direction_10m", 220.0)),
            "wind_gusts_kmh": float(current.get("wind_gusts_10m", 20.0)),
            "precipitation_mm": float(current.get("precipitation", 0.0)),
            "cape_j_kg": max(0.0, current_cape),
            "timestamp": current.get("time", ""),
            "status": "live"
        }

        # Extract multi-level wind for shear estimation
        wind_80m = hourly.get("wind_speed_80m", [])
        wind_120m = hourly.get("wind_speed_120m", [])
        wind_dir_80m = hourly.get("wind_direction_80m", [])
        wind_dir_120m = hourly.get("wind_direction_120m", [])

        # Wind shear = |V_upper - V_lower| (proxy for supercell potential)
        if wind_80m and wind_120m:
            ws_10 = conditions["wind_speed_kmh"]
            ws_80 = float(wind_80m[0]) if wind_80m[0] is not None else ws_10
            ws_120 = float(wind_120m[0]) if wind_120m[0] is not None else ws_80
            conditions["wind_speed_80m_kmh"] = ws_80
            conditions["wind_speed_120m_kmh"] = ws_120
            conditions["wind_shear_0_120m_kmh"] = round(abs(ws_120 - ws_10), 1)
        else:
            conditions["wind_shear_0_120m_kmh"] = 0.0

        _CONDITIONS_CACHE = conditions
        _LAST_FETCH_TIME = now
        return conditions

    except Exception as exc:
        print(f"[WARN] Open-Meteo fetch failed: {exc}. Returning fallback baseline.")
        if _CONDITIONS_CACHE:
            return _CONDITIONS_CACHE
        return {
            "source": "Open-Meteo (Offline Fallback)",
            "latitude": target_lat,
            "longitude": target_lon,
            "temperature_c": 30.0,
            "relative_humidity_pct": 70.0,
            "surface_pressure_hpa": 1005.0,
            "wind_speed_kmh": 15.0,
            "wind_direction_deg": 230.0,
            "precipitation_mm": 0.0,
            "cape_j_kg": 1250.0,
            "timestamp": "",
            "status": "fallback"
        }


def get_historical_archive(
    start_date: str,
    end_date: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> Dict[str, Any]:
    """
    Fetch historical archive data for Ahmedabad/Gujarat region.
    Dates format: 'YYYY-MM-DD'
    """
    target_lat = lat if lat is not None else settings.mvp_center_lat
    target_lon = lon if lon is not None else settings.mvp_center_lon

    params = {
        "latitude": target_lat,
        "longitude": target_lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "wind_direction_10m",
            "surface_pressure"
        ],
        "timezone": "auto"
    }

    resp = requests.get(ARCHIVE_URL, params=params, timeout=10.0)
    resp.raise_for_status()
    return resp.json()