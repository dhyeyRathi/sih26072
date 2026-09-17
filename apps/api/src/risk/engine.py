"""
Risk/Decision Engine — converts ML model outputs into operational risk information.
Separate from the ML engine by design (CORE.md Section 5).
"""

from typing import Optional
import numpy as np
from src.config import settings


def calculate_risk_level(
    thunderstorm_probability: float,
    lightning_probability: float,
    intensity: str,
    speed_kmh: float,
) -> str:
    """
    Determine operational risk level from model outputs.

    Risk levels (CORE.md Section 34, Feature #8):
    - LOW: thunderstorm prob < 30%
    - MODERATE: 30-60%
    - HIGH: 60-80%
    - SEVERE: > 80%

    Adjusted upward if lightning probability is high or intensity is severe.
    """
    # Base risk from thunderstorm probability
    if thunderstorm_probability >= 0.80:
        base = 4  # severe
    elif thunderstorm_probability >= 0.60:
        base = 3  # high
    elif thunderstorm_probability >= 0.30:
        base = 2  # moderate
    else:
        base = 1  # low

    # Lightning boost
    if lightning_probability >= 0.7:
        base = min(4, base + 1)

    # Intensity boost
    if intensity in ("severe", "strong") and base < 4:
        base = min(4, base + 1)

    levels = {1: "low", 2: "moderate", 3: "high", 4: "severe"}
    return levels[base]


def calculate_eta_minutes(
    storm_lat: float,
    storm_lon: float,
    target_lat: float,
    target_lon: float,
    speed_kmh: float,
    direction_deg: float,
) -> Optional[float]:
    """
    Calculate estimated time of arrival at a target location.

    Uses great-circle distance and storm speed/direction.
    Returns None if the storm is moving away from the target.
    """
    if speed_kmh < 1.0:
        return None  # Stationary storm, no meaningful ETA

    # Distance to target
    distance_km = _haversine_km(storm_lat, storm_lon, target_lat, target_lon)

    # Bearing from storm to target
    bearing = _bearing_deg(storm_lat, storm_lon, target_lat, target_lon)

    # Angle between storm direction and target bearing
    angle_diff = abs(direction_deg - bearing)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    # If storm is moving away (more than 90° off), no ETA
    if angle_diff > 90:
        return None

    # Effective approach speed (projection of velocity onto target direction)
    approach_speed = speed_kmh * np.cos(np.radians(angle_diff))

    if approach_speed < 1.0:
        return None

    eta_hours = distance_km / approach_speed
    eta_minutes = eta_hours * 60

    # Cap at 120 minutes (beyond our forecast horizon is not meaningful)
    if eta_minutes > 120:
        return None

    return round(eta_minutes, 0)


def assess_storm_risk(storm: dict, target: Optional[dict] = None) -> dict:
    """
    Full risk assessment for a tracked storm cell.
    Optionally calculate ETA to a target location.
    """
    ts_prob = storm.get("thunderstorm_probability", 0.5)
    lt_prob = storm.get("lightning_probability", 0.3)

    # Estimate probabilities from reflectivity if not provided by model
    max_dbz = storm.get("max_reflectivity_dbz", 30)
    if "thunderstorm_probability" not in storm:
        ts_prob = min(1.0, max(0, (max_dbz - 25) / 40))
    if "lightning_probability" not in storm:
        lightning_rate = storm.get("lightning_rate", 0)
        lt_prob = min(1.0, lightning_rate / 20.0) if lightning_rate else min(1.0, max(0, (max_dbz - 40) / 25))

    risk_level = calculate_risk_level(
        thunderstorm_probability=ts_prob,
        lightning_probability=lt_prob,
        intensity=storm.get("intensity", "moderate"),
        speed_kmh=storm.get("movement_speed_kmh", 0),
    )

    result = {
        "cell_id": storm.get("cell_id"),
        "risk_level": risk_level,
        "thunderstorm_probability": round(ts_prob, 2),
        "lightning_probability": round(lt_prob, 2),
        "intensity": storm.get("intensity", "moderate"),
        "speed_kmh": storm.get("movement_speed_kmh", 0),
        "direction_deg": storm.get("movement_direction_deg", 0),
        "trend": storm.get("trend", "steady"),
    }

    if target:
        eta = calculate_eta_minutes(
            storm["center_lat"], storm["center_lon"],
            target["lat"], target["lon"],
            storm.get("movement_speed_kmh", 0),
            storm.get("movement_direction_deg", 0),
        )
        result["eta_minutes"] = eta
        result["target"] = target

    return result


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))


def _bearing_deg(lat1, lon1, lat2, lon2):
    dlon = np.radians(lon2 - lon1)
    lat1_r = np.radians(lat1)
    lat2_r = np.radians(lat2)
    x = np.sin(dlon) * np.cos(lat2_r)
    y = np.cos(lat1_r) * np.sin(lat2_r) - np.sin(lat1_r) * np.cos(lat2_r) * np.cos(dlon)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360
