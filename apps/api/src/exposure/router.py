"""REST endpoints for critical-infrastructure exposure assessments."""

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException

from src.exposure.infrastructure import (
    CRITICAL_ASSETS,
    DISTRICT_VULNERABILITIES,
    assess_all_infrastructure,
    calculate_asset_exposure,
)
from src.risk.engine import assess_storm_risk
from src.storms.tracking import storm_tracker


router = APIRouter(prefix="/exposure", tags=["exposure"])

_FORECAST_HORIZONS = [15, 30, 45, 60]
_THREAT_ORDER = {"safe": 0, "watch": 1, "warning": 2, "critical": 3}


def _current_state() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return one internally consistent snapshot of active cells and trajectories."""
    storms = storm_tracker.get_active_cells()
    trajectories = storm_tracker.predict_trajectories(
        horizons_minutes=_FORECAST_HORIZONS
    )
    return storms, trajectories


def _trajectory_for_cell(
    trajectories: list[dict[str, Any]], cell_id: str
) -> dict[str, Any] | None:
    return next(
        (trajectory for trajectory in trajectories if trajectory.get("cell_id") == cell_id),
        None,
    )


def _district_names(asset: dict[str, Any]) -> list[str]:
    """Expand the curated slash-delimited district labels into canonical names."""
    return [
        district.strip()
        for district in asset.get("district", "").split("/")
        if district.strip()
    ]


def _district_summary(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarise non-safe exposure by district without double-counting assets."""
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "asset_ids": [],
            "critical_assets": 0,
            "warning_assets": 0,
            "watch_assets": 0,
        }
    )

    for asset in assets:
        threat = asset.get("threat_level", "safe")
        if threat == "safe":
            continue

        for district in _district_names(asset):
            bucket = grouped[district]
            bucket["asset_ids"].append(asset["id"])
            bucket[f"{threat}_assets"] += 1

    summaries: list[dict[str, Any]] = []
    for district, counts in grouped.items():
        if counts["critical_assets"]:
            threat_level = "critical"
        elif counts["warning_assets"]:
            threat_level = "warning"
        else:
            threat_level = "watch"

        vulnerability = DISTRICT_VULNERABILITIES.get(district, {})
        summaries.append(
            {
                "district": district,
                "threat_level": threat_level,
                "threatened_asset_count": len(counts["asset_ids"]),
                "critical_assets": counts["critical_assets"],
                "warning_assets": counts["warning_assets"],
                "watch_assets": counts["watch_assets"],
                "asset_ids": counts["asset_ids"],
                "population": vulnerability.get("population"),
                "urban_density_km2": vulnerability.get("urban_density_km2"),
                "flood_prone_zones": vulnerability.get("flood_prone_zones"),
            }
        )

    return sorted(
        summaries,
        key=lambda item: (
            -_THREAT_ORDER[item["threat_level"]],
            -item["threatened_asset_count"],
            item["district"],
        ),
    )


def _summary_with_totals(summary: dict[str, Any]) -> dict[str, Any]:
    """Add consumer-friendly totals while retaining the engine's source fields."""
    result = dict(summary)
    result["total_threatened_assets"] = (
        result.get("critical_count", 0)
        + result.get("warning_count", 0)
        + result.get("watch_count", 0)
    )
    return result


@router.get("/assets")
async def get_exposure_assets() -> dict[str, Any]:
    """Get all curated critical assets with their current real-time threat state."""
    storms, trajectories = _current_state()
    assessment = assess_all_infrastructure(storms, trajectories)

    return {
        "count": len(assessment["assets"]),
        "active_storm_count": len(storms),
        "assets": assessment["assets"],
        "summary": _summary_with_totals(assessment["summary"]),
    }


@router.get("/summary")
async def get_exposure_summary() -> dict[str, Any]:
    """Get the global exposure score, threatened assets, and exposed population."""
    storms, trajectories = _current_state()
    assessment = assess_all_infrastructure(storms, trajectories)

    return {
        "active_storm_count": len(storms),
        **_summary_with_totals(assessment["summary"]),
    }


@router.get("/cell/{cell_id}")
async def get_cell_exposure(cell_id: str) -> dict[str, Any]:
    """Get assets and district exposure associated with one active storm cell."""
    storms, trajectories = _current_state()
    cell = next((storm for storm in storms if storm.get("cell_id") == cell_id), None)
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Storm cell '{cell_id}' was not found")

    trajectory = _trajectory_for_cell(trajectories, cell_id)
    cell_trajectories = [trajectory] if trajectory is not None else []
    cell_assessment = assess_all_infrastructure([cell], cell_trajectories)
    assessed_assets = cell_assessment["assets"]
    intersected_assets = [
        asset for asset in assessed_assets if asset.get("threat_level") != "safe"
    ]
    district_summary = _district_summary(assessed_assets)

    return {
        "cell": cell,
        "risk": assess_storm_risk(cell),
        "trajectory": trajectory,
        "count": len(intersected_assets),
        "assets": intersected_assets,
        "intersected_assets": intersected_assets,
        "district_summary": district_summary,
        "summary": _summary_with_totals(cell_assessment["summary"]),
    }
