"""REST API for transparent storm-warning reasoning."""

from fastapi import APIRouter, HTTPException

from src.explainability.engine import build_warning_evidence
from src.risk.engine import assess_storm_risk
from src.storms.tracking import storm_tracker


router = APIRouter(prefix="/explainability", tags=["explainability"])


@router.get("/{cell_id}")
async def get_warning_explanation(cell_id: str):
    """Return physical indicators and plain-language evidence for an active cell."""
    cell = next(
        (item for item in storm_tracker.get_active_cells() if item.get("cell_id") == cell_id),
        None,
    )
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Storm cell '{cell_id}' was not found")

    risk = assess_storm_risk(cell)
    return {
        "cell": cell,
        "risk": risk,
        **build_warning_evidence(cell, risk),
    }

