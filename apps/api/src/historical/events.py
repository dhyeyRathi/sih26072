"""Curated demonstration archive for historical-event intelligence.

These records are scenario summaries for a hackathon demonstration, not an
authoritative IMD archive.  Every response labels the catalogue accordingly so
it can later be replaced by verified radar/gauge/event datasets.
"""

from __future__ import annotations

import math
from typing import Any


HISTORICAL_EVENTS: list[dict[str, Any]] = [
    {
        "id": "guj-2022-ahmedabad-cloudburst",
        "name": "July 2022 Ahmedabad Flash Cloudburst",
        "date": "2022-07-10",
        "region": "Ahmedabad, Gujarat",
        "event_type": "severe_convective_cloudburst",
        "observed_rainfall_mm": 88,
        "rainfall_window_hours": 2,
        "peak_gust_kmh": 68,
        "impact_summary": "Short-duration urban flooding and a severe lightning cluster affected Ahmedabad catchments.",
        "feature_vector": {"reflectivity_dbz": 61, "lightning_rate": 24, "speed_kmh": 25, "shear_knots": 38},
        "origin": {"lat": 22.99, "lon": 72.58},
        "motion": {"direction_deg": 48, "speed_kmh": 25},
    },
    {
        "id": "guj-2023-biparjoy-squall-bands",
        "name": "June 2023 Cyclone Biparjoy Squall Bands",
        "date": "2023-06-15",
        "region": "Kutch / Saurashtra, Gujarat",
        "event_type": "cyclonic_convective_rainbands",
        "observed_rainfall_mm": 64,
        "rainfall_window_hours": 3,
        "peak_gust_kmh": 120,
        "impact_summary": "Outer rainbands brought widespread squalls, strong gusts, and travel disruption along coastal Gujarat.",
        "feature_vector": {"reflectivity_dbz": 54, "lightning_rate": 10, "speed_kmh": 48, "shear_knots": 52},
        "origin": {"lat": 22.75, "lon": 69.35},
        "motion": {"direction_deg": 35, "speed_kmh": 48},
    },
    {
        "id": "guj-2021-tauktae-supercells",
        "name": "May 2021 Cyclone Tauktae Pre-landfall Supercells",
        "date": "2021-05-16",
        "region": "South Gujarat",
        "event_type": "embedded_supercell",
        "observed_rainfall_mm": 72,
        "rainfall_window_hours": 2,
        "peak_gust_kmh": 108,
        "impact_summary": "Organised convective cells preceded landfall with damaging wind and heavy rainfall potential.",
        "feature_vector": {"reflectivity_dbz": 59, "lightning_rate": 18, "speed_kmh": 43, "shear_knots": 49},
        "origin": {"lat": 21.65, "lon": 72.85},
        "motion": {"direction_deg": 30, "speed_kmh": 43},
    },
    {
        "id": "guj-2020-pre-monsoon-squall-line",
        "name": "June 2020 Gujarat Pre-Monsoon Severe Squall Line",
        "date": "2020-06-06",
        "region": "Central Gujarat",
        "event_type": "squall_line",
        "observed_rainfall_mm": 46,
        "rainfall_window_hours": 2,
        "peak_gust_kmh": 82,
        "impact_summary": "A fast-moving severe squall line produced gust fronts, lightning, and localised disruption.",
        "feature_vector": {"reflectivity_dbz": 56, "lightning_rate": 15, "speed_kmh": 56, "shear_knots": 42},
        "origin": {"lat": 22.62, "lon": 73.05},
        "motion": {"direction_deg": 64, "speed_kmh": 56},
    },
]


VERIFICATION_METRICS = {
    "period": "demonstration hold-out scenario set",
    "sample_size": 48,
    "pod": 0.84,
    "far": 0.19,
    "csi": 0.70,
    "mean_trajectory_error_km": 8.6,
    "disclaimer": "Illustrative metrics only; production verification requires independent observed cases.",
}


def list_event_summaries() -> list[dict[str, Any]]:
    """Return archive details excluding internal similarity fields."""
    return [{key: value for key, value in event.items() if key not in {"feature_vector", "origin", "motion"}} for event in HISTORICAL_EVENTS]


def get_event(event_id: str) -> dict[str, Any] | None:
    return next((event for event in HISTORICAL_EVENTS if event["id"] == event_id), None)


def feature_vector_from_cell(cell: dict[str, Any]) -> dict[str, float]:
    max_dbz = float(cell.get("max_reflectivity_dbz", 45.0))
    speed_kmh = float(cell.get("movement_speed_kmh", 20.0))
    return {
        "reflectivity_dbz": max_dbz,
        "lightning_rate": float(cell.get("lightning_rate", max(0.0, (max_dbz - 40) * 0.8))),
        "speed_kmh": speed_kmh,
        "shear_knots": float(cell.get("deep_layer_shear_knots", min(55.0, 10 + speed_kmh * 0.52))),
    }


def find_analogues(features: dict[str, float], limit: int = 3) -> list[dict[str, Any]]:
    """Score event analogues using bounded, transparent feature differences."""
    scales = {"reflectivity_dbz": 20.0, "lightning_rate": 25.0, "speed_kmh": 45.0, "shear_knots": 35.0}
    weights = {"reflectivity_dbz": 0.35, "lightning_rate": 0.25, "speed_kmh": 0.20, "shear_knots": 0.20}
    matches: list[dict[str, Any]] = []
    for event in HISTORICAL_EVENTS:
        reference = event["feature_vector"]
        weighted_distance = sum(
            weights[name] * min(1.0, abs(float(features.get(name, reference[name])) - float(reference[name])) / scales[name])
            for name in weights
        )
        similarity = max(0.0, 1.0 - weighted_distance)
        matches.append({
            "event_id": event["id"],
            "event_name": event["name"],
            "similarity_score": round(similarity, 3),
            "match_percentage": round(similarity * 100, 1),
            "historical_impact": event["impact_summary"],
            "observed_rainfall_mm": event["observed_rainfall_mm"],
            "peak_gust_kmh": event["peak_gust_kmh"],
            "feature_comparison": {
                name: {"current": round(float(features.get(name, reference[name])), 1), "historical": reference[name]}
                for name in weights
            },
        })
    return sorted(matches, key=lambda item: item["similarity_score"], reverse=True)[:limit]


def generate_replay(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate deterministic T-60 to T+60 replay frames for the demo archive."""
    origin = event["origin"]
    motion = event["motion"]
    direction = math.radians(float(motion["direction_deg"]))
    speed = float(motion["speed_kmh"])
    frames: list[dict[str, Any]] = []
    for minutes in range(-60, 61, 10):
        distance_km = speed * minutes / 60.0
        dx = math.sin(direction) * distance_km
        dy = math.cos(direction) * distance_km
        observed_lat = origin["lat"] + dy / 111.0
        observed_lon = origin["lon"] + dx / (111.0 * max(0.1, math.cos(math.radians(origin["lat"]))))
        # A deterministic growing forecast error makes the replay useful for
        # demonstrating forecast-vs-observation verification.
        forecast_error = (abs(minutes) / 60.0) * 0.045
        predicted_lat = observed_lat + forecast_error * math.cos(direction + math.pi / 3)
        predicted_lon = observed_lon + forecast_error * math.sin(direction + math.pi / 3)
        frames.append({
            "offset_minutes": minutes,
            "observed": {"lat": round(observed_lat, 4), "lon": round(observed_lon, 4)},
            "predicted": {"lat": round(predicted_lat, 4), "lon": round(predicted_lon, 4)},
            "reflectivity_dbz": round(max(20.0, event["feature_vector"]["reflectivity_dbz"] - abs(minutes) * 0.09), 1),
        })
    return frames

