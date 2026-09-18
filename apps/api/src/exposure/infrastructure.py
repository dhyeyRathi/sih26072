"""
Critical Infrastructure Exposure & Geospatial Risk Engine.
Implements CORE.md Section 14 & Section 34 (Feature #14).

Calculates spatial exposure and threat levels for critical assets:
hospitals, airports, power substations, highways, and district populations.
"""

import math
from typing import Optional, List, Dict, Any

# Curated high-resolution spatial database of critical infrastructure in Gujarat
CRITICAL_ASSETS: List[Dict[str, Any]] = [
    {
        "id": "HOSP-01",
        "name": "Ahmedabad Civil Hospital & Trauma Center",
        "category": "hospital",
        "lat": 23.0531,
        "lon": 72.5975,
        "district": "Ahmedabad",
        "capacity": 2800,
        "criticality": "tier-1",
        "emergency_contact": "108",
        "backup_power": True,
    },
    {
        "id": "HOSP-02",
        "name": "SVP Hospital (Sardar Vallabhbhai Patel)",
        "category": "hospital",
        "lat": 23.0180,
        "lon": 72.5714,
        "district": "Ahmedabad",
        "capacity": 1500,
        "criticality": "tier-1",
        "emergency_contact": "108",
        "backup_power": True,
    },
    {
        "id": "HOSP-03",
        "name": "Apollo International Hospital",
        "category": "hospital",
        "lat": 23.1118,
        "lon": 72.6133,
        "district": "Gandhinagar",
        "capacity": 450,
        "criticality": "tier-2",
        "emergency_contact": "108",
        "backup_power": True,
    },
    {
        "id": "HOSP-04",
        "name": "GMERS Civil Hospital Gandhinagar",
        "category": "hospital",
        "lat": 23.2323,
        "lon": 72.6567,
        "district": "Gandhinagar",
        "capacity": 650,
        "criticality": "tier-1",
        "emergency_contact": "108",
        "backup_power": True,
    },
    {
        "id": "HOSP-05",
        "name": "SSG Civil Hospital Vadodara",
        "category": "hospital",
        "lat": 22.3025,
        "lon": 73.1932,
        "district": "Vadodara",
        "capacity": 1600,
        "criticality": "tier-1",
        "emergency_contact": "108",
        "backup_power": True,
    },
    {
        "id": "AIR-01",
        "name": "SVP International Airport (AMD)",
        "category": "airport",
        "lat": 23.0772,
        "lon": 72.6347,
        "district": "Ahmedabad",
        "daily_passengers": 38000,
        "criticality": "tier-1",
        "aviation_met_office": "AMD AMO",
    },
    {
        "id": "AIR-02",
        "name": "Vadodara Airport (BDQ)",
        "category": "airport",
        "lat": 22.3362,
        "lon": 73.2263,
        "district": "Vadodara",
        "daily_passengers": 7500,
        "criticality": "tier-2",
        "aviation_met_office": "BDQ AMS",
    },
    {
        "id": "PWR-01",
        "name": "GETCO 400kV Substation Pirana",
        "category": "power_grid",
        "lat": 22.9654,
        "lon": 72.5682,
        "district": "Ahmedabad",
        "voltage_kv": 400,
        "criticality": "tier-1",
    },
    {
        "id": "PWR-02",
        "name": "GETCO 400kV Substation Dehgam",
        "category": "power_grid",
        "lat": 23.1685,
        "lon": 72.8124,
        "district": "Gandhinagar",
        "voltage_kv": 400,
        "criticality": "tier-1",
    },
    {
        "id": "HWY-01",
        "name": "NE-1 National Expressway 1 (Ahmedabad-Vadodara)",
        "category": "highway",
        "lat": 22.6840,
        "lon": 72.8620,
        "district": "Kheda / Anand",
        "length_km": 93.1,
        "criticality": "tier-1",
        "lane_count": 6,
    },
    {
        "id": "HWY-02",
        "name": "Sarkhej-Gandhinagar (SG) Highway Expressway",
        "category": "highway",
        "lat": 23.0950,
        "lon": 72.5350,
        "district": "Ahmedabad / Gandhinagar",
        "length_km": 44.0,
        "criticality": "tier-1",
        "lane_count": 6,
    },
    {
        "id": "HWY-03",
        "name": "Sardar Patel Ring Road (SPRR)",
        "category": "highway",
        "lat": 23.0100,
        "lon": 72.6800,
        "district": "Ahmedabad",
        "length_km": 76.0,
        "criticality": "tier-2",
        "lane_count": 4,
    },
]

DISTRICT_VULNERABILITIES = {
    "Ahmedabad": {"population": 8450000, "urban_density_km2": 9900, "flood_prone_zones": 14},
    "Gandhinagar": {"population": 1520000, "urban_density_km2": 2400, "flood_prone_zones": 6},
    "Vadodara": {"population": 4200000, "urban_density_km2": 6100, "flood_prone_zones": 11},
    "Anand": {"population": 2100000, "urban_density_km2": 720, "flood_prone_zones": 8},
    "Kheda": {"population": 2300000, "urban_density_km2": 580, "flood_prone_zones": 7},
}


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great circle distance between two points in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_asset_exposure(asset: Dict[str, Any], storms: List[Dict[str, Any]], trajectories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Assess exposure for a single critical asset against active storm cells and predicted trajectories.
    """
    asset_lat = asset["lat"]
    asset_lon = asset["lon"]

    closest_storm = None
    min_dist_km = 9999.0

    for storm in storms:
        dist = haversine_distance_km(asset_lat, asset_lon, storm["center_lat"], storm["center_lon"])
        if dist < min_dist_km:
            min_dist_km = dist
            closest_storm = storm

    # Check trajectory forecast intersection
    closest_horizon = None
    trajectory_hit = False

    for traj in trajectories:
        for fc in traj.get("forecasts", []):
            f_lat = fc["predicted_lat"]
            f_lon = fc["predicted_lon"]
            f_dist = haversine_distance_km(asset_lat, asset_lon, f_lat, f_lon)
            # Uncertainty radius envelope
            envelope_km = max(8.0, fc.get("uncertainty_km", 10.0))
            if f_dist <= envelope_km:
                trajectory_hit = True
                if closest_horizon is None or fc["horizon_minutes"] < closest_horizon:
                    closest_horizon = fc["horizon_minutes"]

    # Assign Threat Level
    if min_dist_km <= 10.0:
        threat_level = "critical"
        eta_min = 0
    elif trajectory_hit and closest_horizon is not None:
        threat_level = "critical" if closest_horizon <= 20 else "warning"
        eta_min = closest_horizon
    elif min_dist_km <= 25.0:
        threat_level = "warning"
        # Estimate ETA based on closest storm speed
        speed = closest_storm.get("movement_speed_kmh", 20.0) if closest_storm else 20.0
        eta_min = max(5, int((min_dist_km / max(5.0, speed)) * 60))
    elif min_dist_km <= 45.0:
        threat_level = "watch"
        speed = closest_storm.get("movement_speed_kmh", 20.0) if closest_storm else 20.0
        eta_min = int((min_dist_km / max(5.0, speed)) * 60)
    else:
        threat_level = "safe"
        eta_min = None

    return {
        **asset,
        "threat_level": threat_level,
        "distance_to_storm_km": round(min_dist_km, 1) if closest_storm else None,
        "closest_cell_id": closest_storm["cell_id"] if closest_storm else None,
        "estimated_arrival_minutes": eta_min,
    }


def assess_all_infrastructure(storms: List[Dict[str, Any]], trajectories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run full exposure assessment across all critical assets and districts.
    """
    assessed_assets = [
        calculate_asset_exposure(asset, storms, trajectories)
        for asset in CRITICAL_ASSETS
    ]

    # Count breakdown
    critical_count = sum(1 for a in assessed_assets if a["threat_level"] == "critical")
    warning_count = sum(1 for a in assessed_assets if a["threat_level"] == "warning")
    watch_count = sum(1 for a in assessed_assets if a["threat_level"] == "watch")
    safe_count = sum(1 for a in assessed_assets if a["threat_level"] == "safe")

    # Exposed population calculation
    threatened_districts = set()
    for a in assessed_assets:
        if a["threat_level"] in ("critical", "warning"):
            threatened_districts.add(a["district"].split(" / ")[0])

    exposed_population = sum(
        DISTRICT_VULNERABILITIES.get(d, {}).get("population", 0)
        for d in threatened_districts
    )

    # Composite exposure score (0 - 100)
    composite_score = min(100, (critical_count * 25) + (warning_count * 12) + (watch_count * 4))

    return {
        "assets": assessed_assets,
        "summary": {
            "total_assets": len(assessed_assets),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "watch_count": watch_count,
            "safe_count": safe_count,
            "composite_exposure_score": composite_score,
            "threatened_districts": list(threatened_districts),
            "estimated_exposed_population": exposed_population,
        }
    }
