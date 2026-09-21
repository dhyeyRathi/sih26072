"""
Risk/Decision Engine — converts ML model outputs into operational risk information.
Separate from the ML engine by design (CORE.md Section 5).
"""

from typing import Optional
import numpy as np

# Default operational target for ETA calculations
AHMEDABAD_TARGET = {"lat": 23.0225, "lon": 72.5714}

RISK_LEVEL_ORDER = {"low": 1, "moderate": 2, "high": 3, "severe": 4}

# Per-cell hysteresis state to reduce 1 Hz risk flicker
_risk_hysteresis: dict[str, dict] = {}


def enrich_storm_with_forecast_probs(storm: dict, trajectory: Optional[dict] = None) -> dict:
    """
    Merge nearest-horizon ML forecast probabilities into a tracked cell dict
    so risk assessment uses model outputs instead of dBZ heuristics.
    """
    enriched = {**storm}
    if not trajectory:
        return enriched

    forecasts = trajectory.get("forecasts") or []
    if not forecasts:
        return enriched

    # Shortest horizon forecast acts as the current nowcast proxy
    fc = min(forecasts, key=lambda f: f.get("horizon_minutes", 999))
    if "thunderstorm_probability" in fc:
        enriched["thunderstorm_probability"] = fc["thunderstorm_probability"]
    if "lightning_probability" in fc:
        enriched["lightning_probability"] = fc["lightning_probability"]
    if "confidence_score" in fc:
        enriched["confidence_score"] = fc["confidence_score"]

    return enriched


def _estimate_ts_from_dbz(max_dbz: float) -> float:
    """Conservative thunderstorm probability from reflectivity."""
    return float(np.clip((max_dbz - 35) / 45, 0.0, 0.85))


def _estimate_lt_from_rate(lightning_rate: float, max_dbz: float) -> float:
    """Sigmoid lightning probability from flash rate."""
    if lightning_rate > 0:
        return float(np.clip(1.0 / (1.0 + np.exp(-(lightning_rate - 8) / 4)), 0.0, 0.90))
    return float(np.clip((max_dbz - 45) / 30, 0.0, 0.75))


def _environmental_modifiers(environmental: Optional[dict]) -> tuple[float, float]:
    """Small ± adjustments from live NWP / lightning observations."""
    if not environmental:
        return 0.0, 0.0

    cape = float(environmental.get("observed_cape_j_kg", 1200))
    lt_rate = float(environmental.get("lightning_flash_rate", 0))

    ts_mod = float(np.clip((cape - 1200) / 4000, -0.05, 0.10))
    lt_mod = float(np.clip(lt_rate / 25, 0.0, 0.08))
    return ts_mod, lt_mod


def calculate_risk_level(
    thunderstorm_probability: float,
    lightning_probability: float,
    intensity: str,
    speed_kmh: float,
    trend: str = "steady",
) -> str:
    """
    Determine operational risk level from model outputs.

    Risk levels (CORE.md Section 34, Feature #8):
    - LOW: thunderstorm prob < 30%
    - MODERATE: 30-60%
    - HIGH: 60-80%
    - SEVERE: > 80%

    Adjusted upward if lightning probability is high or intensity is intensifying.
    """
    if thunderstorm_probability >= 0.80:
        base = 4
    elif thunderstorm_probability >= 0.60:
        base = 3
    elif thunderstorm_probability >= 0.30:
        base = 2
    else:
        base = 1

    if lightning_probability >= 0.7:
        base = min(4, base + 1)

    if intensity in ("severe", "strong") and trend == "intensifying" and base < 4:
        base = min(4, base + 1)

    levels = {1: "low", 2: "moderate", 3: "high", 4: "severe"}
    return levels[base]


def _apply_hysteresis(cell_id: str, raw_level: str) -> tuple[str, str]:
    """
    Require 2 consecutive upgrade cycles before raising risk level.
    Downgrades apply immediately.
    """
    if not cell_id:
        return raw_level, raw_level

    state = _risk_hysteresis.get(cell_id, {"level": raw_level, "pending_upgrade": None, "cycles": 0})
    prev_level = state.get("level", raw_level)
    raw_order = RISK_LEVEL_ORDER.get(raw_level, 1)
    prev_order = RISK_LEVEL_ORDER.get(prev_level, 1)

    if raw_order > prev_order:
        if state.get("pending_upgrade") == raw_level:
            cycles = state.get("cycles", 0) + 1
            if cycles >= 2:
                _risk_hysteresis[cell_id] = {"level": raw_level, "pending_upgrade": None, "cycles": 0}
                return raw_level, prev_level
            _risk_hysteresis[cell_id] = {"level": prev_level, "pending_upgrade": raw_level, "cycles": cycles}
            return prev_level, prev_level

        _risk_hysteresis[cell_id] = {"level": prev_level, "pending_upgrade": raw_level, "cycles": 1}
        return prev_level, prev_level

    _risk_hysteresis[cell_id] = {"level": raw_level, "pending_upgrade": None, "cycles": 0}
    return raw_level, prev_level


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
        return None

    distance_km = _haversine_km(storm_lat, storm_lon, target_lat, target_lon)
    bearing = _bearing_deg(storm_lat, storm_lon, target_lat, target_lon)

    angle_diff = abs(direction_deg - bearing)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    if angle_diff > 90:
        return None

    approach_speed = speed_kmh * np.cos(np.radians(angle_diff))
    if approach_speed < 1.0:
        return None

    eta_minutes = (distance_km / approach_speed) * 60
    if eta_minutes > 120:
        return None

    return round(eta_minutes, 0)


# Per-cell flash rate history for 2-sigma Lightning Jump detection
_cell_lightning_history: dict[str, list[float]] = {}


def compute_physics_indicators(storm: dict, environmental: Optional[dict] = None) -> dict:
    """
    Computes severe convective weather physical indicators from radar reflectivity,
    thermodynamics, and lightning observations according to atmospheric science literature:

    1. VIL (Vertically Integrated Liquid) [Greene & Clark 1972]:
       VIL = 3.44e-6 * sum(Z^(4/7)) * delta_h  (kg/m^2)

    2. VIL Density [Amburn & Wolf 1997]:
       VIL_density = (VIL / Echo_Top_m) * 1000  (g/m^3)
       Threshold >= 3.5 g/m^3 indicates severe hail / severe downbursts.

    3. 2-Sigma Lightning Jump Algorithm [Schultz et al. 2009/2011, Gatlin & Goodman 2010]:
       DFRDT = (FR_t + FR_{t-1})/2 - (FR_{t-2} + FR_{t-3})/2
       Jump flagged if DFRDT >= 2 * sigma(DFRDT_history) and FR >= 10 flashes/min.

    4. Max Updraft Velocity W_max:
       W_max = sqrt(2 * CAPE)  (m/s)
    """
    max_dbz = float(storm.get("max_reflectivity_dbz", 35.0))
    lt_rate = float(storm.get("lightning_rate", 0.0))
    cape = float((environmental or {}).get("observed_cape_j_kg", 1200.0))

    # 1. Echo Top height estimation (km) based on CAPE & max reflectivity
    echo_top_km = round(min(18.0, max(5.0, 7.5 + (max_dbz - 35.0) * 0.15 + np.sqrt(max(0.0, cape)) * 0.08)), 1)
    echo_top_m = echo_top_km * 1000.0

    # 2. VIL calculation (Greene & Clark 1972)
    num_layers = max(3, int(echo_top_km))
    delta_h = echo_top_m / num_layers
    layers_dbz = [max(10.0, max_dbz - abs(i - num_layers * 0.4) ** 1.5 * 3.0) for i in range(num_layers)]

    vil_sum = 0.0
    for dbz in layers_dbz:
        z_linear = 10.0 ** (dbz / 10.0)
        vil_sum += (z_linear ** (4.0 / 7.0)) * delta_h

    vil_kg_m2 = round(3.44e-6 * vil_sum, 2)

    # 3. VIL Density (Amburn & Wolf 1997)
    vil_density_g_m3 = round((vil_kg_m2 / echo_top_m) * 1000.0, 2) if echo_top_m > 0 else 0.0

    # 4. Max Updraft Speed W_max (m/s)
    w_max_m_s = round(float(np.sqrt(2.0 * max(0.0, cape))), 1)

    # 5. 2-Sigma Lightning Jump Algorithm
    cell_id = storm.get("cell_id", "unknown")
    if cell_id not in _cell_lightning_history:
        _cell_lightning_history[cell_id] = []

    hist = _cell_lightning_history[cell_id]
    hist.append(lt_rate)
    if len(hist) > 20:
        hist.pop(0)

    dfrdt = 0.0
    sigma_ratio = 0.0
    jump_detected = False

    if len(hist) >= 4:
        fr_now = (hist[-1] + hist[-2]) / 2.0
        fr_prev = (hist[-3] + hist[-4]) / 2.0
        dfrdt = fr_now - fr_prev

        dfrdt_hist = []
        for idx in range(3, len(hist)):
            f_now = (hist[idx] + hist[idx - 1]) / 2.0
            f_prev = (hist[idx - 2] + hist[idx - 3]) / 2.0
            dfrdt_hist.append(f_now - f_prev)

        if len(dfrdt_hist) > 1:
            mean_dfrdt = float(np.mean(dfrdt_hist))
            std_dfrdt = float(np.std(dfrdt_hist))
            if std_dfrdt > 0.01:
                sigma_ratio = (dfrdt - mean_dfrdt) / std_dfrdt
            else:
                sigma_ratio = dfrdt / 1.0
        else:
            sigma_ratio = dfrdt / 1.0

        if sigma_ratio >= 2.0 and lt_rate >= 10.0:
            jump_detected = True

    return {
        "vil_kg_m2": vil_kg_m2,
        "vil_density_g_m3": vil_density_g_m3,
        "echo_top_km": echo_top_km,
        "w_max_m_s": w_max_m_s,
        "lightning_jump": {
            "jump_detected": jump_detected,
            "dfrdt": round(dfrdt, 2),
            "sigma_ratio": round(sigma_ratio, 2),
        }
    }


def assess_storm_risk(
    storm: dict,
    target: Optional[dict] = None,
    environmental: Optional[dict] = None,
) -> dict:
    """
    Full risk assessment for a tracked storm cell.
    Optionally calculate ETA to a target location.
    """
    max_dbz = storm.get("max_reflectivity_dbz", 30)
    lightning_rate = storm.get("lightning_rate", 0)
    trend = storm.get("trend", "steady")

    # Compute physical indicators
    physics = compute_physics_indicators(storm, environmental)

    has_ml_probs = (
        "thunderstorm_probability" in storm
        and storm.get("thunderstorm_probability") is not None
    )

    if has_ml_probs:
        ts_prob = float(storm["thunderstorm_probability"])
        lt_prob = float(storm.get("lightning_probability", 0.3))
        confidence = float(storm.get("confidence_score", 0.7))
    else:
        ts_prob = _estimate_ts_from_dbz(max_dbz)
        lt_prob = _estimate_lt_from_rate(lightning_rate, max_dbz)
        confidence = 0.55

    ts_mod, lt_mod = _environmental_modifiers(environmental)

    # Physical indicator risk escalation
    if physics["vil_density_g_m3"] >= 3.5:
        ts_mod += 0.08
    if physics["lightning_jump"]["jump_detected"]:
        lt_mod += 0.12

    ts_prob = float(np.clip(ts_prob + ts_mod, 0.0, 0.99))
    lt_prob = float(np.clip(lt_prob + lt_mod, 0.0, 0.99))

    raw_level = calculate_risk_level(
        thunderstorm_probability=ts_prob,
        lightning_probability=lt_prob,
        intensity=storm.get("intensity", "moderate"),
        speed_kmh=storm.get("movement_speed_kmh", 0),
        trend=trend,
    )

    cell_id = storm.get("cell_id", "")
    risk_level, previous_level = _apply_hysteresis(cell_id, raw_level)

    result = {
        "cell_id": cell_id,
        "risk_level": risk_level,
        "raw_risk_level": raw_level,
        "previous_risk_level": previous_level if previous_level != risk_level else None,
        "thunderstorm_probability": round(ts_prob, 2),
        "lightning_probability": round(lt_prob, 2),
        "confidence_score": round(confidence, 2),
        "intensity": storm.get("intensity", "moderate"),
        "speed_kmh": storm.get("movement_speed_kmh", 0),
        "direction_deg": storm.get("movement_direction_deg", 0),
        "trend": trend,
        "vil_kg_m2": physics["vil_kg_m2"],
        "vil_density_g_m3": physics["vil_density_g_m3"],
        "echo_top_km": physics["echo_top_km"],
        "w_max_m_s": physics["w_max_m_s"],
        "lightning_jump": physics["lightning_jump"],
    }

    eta_target = target or AHMEDABAD_TARGET
    eta = calculate_eta_minutes(
        storm["center_lat"], storm["center_lon"],
        eta_target["lat"], eta_target["lon"],
        storm.get("movement_speed_kmh", 0),
        storm.get("movement_direction_deg", 0),
    )
    result["eta_minutes"] = eta
    result["target"] = eta_target

    return result


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _bearing_deg(lat1, lon1, lat2, lon2):
    dlon = np.radians(lon2 - lon1)
    lat1_r = np.radians(lat1)
    lat2_r = np.radians(lat2)
    x = np.sin(dlon) * np.cos(lat2_r)
    y = np.cos(lat1_r) * np.sin(lat2_r) - np.sin(lat1_r) * np.cos(lat2_r) * np.cos(dlon)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360
