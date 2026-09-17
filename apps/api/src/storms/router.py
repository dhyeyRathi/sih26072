"""
Storm cell API endpoints.
Provides real-time storm cell data, trajectories, and forecasts.
"""

from fastapi import APIRouter, Query
from typing import Optional
from src.storms.tracking import storm_tracker
from src.risk.engine import assess_storm_risk

router = APIRouter(prefix="/storms", tags=["storms"])


@router.get("")
async def get_active_storms():
    """Get all currently active tracked storm cells."""
    cells = storm_tracker.get_active_cells()
    return {
        "count": len(cells),
        "storms": cells,
    }


@router.get("/trajectories")
async def get_trajectories():
    """Get predicted trajectories for all active storm cells."""
    trajectories = storm_tracker.predict_trajectories(
        horizons_minutes=[15, 30, 45, 60]
    )
    return {
        "count": len(trajectories),
        "trajectories": trajectories,
    }


@router.get("/{cell_id}")
async def get_storm_detail(cell_id: str):
    """Get detailed information for a specific storm cell."""
    cells = storm_tracker.get_active_cells()
    cell = next((c for c in cells if c.get("cell_id") == cell_id), None)

    if not cell:
        return {"error": "Storm cell not found", "cell_id": cell_id}

    # Get risk assessment
    risk = assess_storm_risk(cell)

    # Get trajectory
    trajectories = storm_tracker.predict_trajectories()
    trajectory = next((t for t in trajectories if t["cell_id"] == cell_id), None)

    return {
        "cell": cell,
        "risk": risk,
        "trajectory": trajectory,
    }


@router.get("/{cell_id}/eta")
async def get_storm_eta(
    cell_id: str,
    lat: float = Query(..., description="Target latitude"),
    lon: float = Query(..., description="Target longitude"),
):
    """Calculate ETA for a storm cell to reach a target location."""
    cells = storm_tracker.get_active_cells()
    cell = next((c for c in cells if c.get("cell_id") == cell_id), None)

    if not cell:
        return {"error": "Storm cell not found", "cell_id": cell_id}

    risk = assess_storm_risk(cell, target={"lat": lat, "lon": lon})

    return {
        "cell_id": cell_id,
        "target": {"lat": lat, "lon": lon},
        "eta_minutes": risk.get("eta_minutes"),
        "risk_level": risk["risk_level"],
        "thunderstorm_probability": risk["thunderstorm_probability"],
        "lightning_probability": risk["lightning_probability"],
    }
