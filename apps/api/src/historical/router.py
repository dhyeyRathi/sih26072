"""Historical analogue, replay, and verification endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.historical.events import (
    VERIFICATION_METRICS,
    feature_vector_from_cell,
    find_analogues,
    generate_replay,
    get_event,
    list_event_summaries,
)
from src.storms.tracking import storm_tracker


router = APIRouter(prefix="/historical", tags=["historical"])


class AnalogueRequest(BaseModel):
    cell_id: Optional[str] = Field(default=None, max_length=64)
    max_reflectivity_dbz: Optional[float] = Field(default=None, ge=0, le=90)
    lightning_rate: Optional[float] = Field(default=None, ge=0, le=250)
    speed_kmh: Optional[float] = Field(default=None, ge=0, le=250)
    shear_knots: Optional[float] = Field(default=None, ge=0, le=120)
    limit: int = Field(default=3, ge=1, le=4)


@router.get("/events")
async def get_historical_events():
    return {
        "catalogue_type": "curated demonstration archive",
        "count": len(list_event_summaries()),
        "events": list_event_summaries(),
    }


@router.post("/match")
async def match_historical_event(request: AnalogueRequest):
    features: dict[str, float] = {}
    selected_cell = None
    if request.cell_id:
        selected_cell = next((cell for cell in storm_tracker.get_active_cells() if cell.get("cell_id") == request.cell_id), None)
        if selected_cell is None:
            raise HTTPException(status_code=404, detail=f"Storm cell '{request.cell_id}' was not found")
        features = feature_vector_from_cell(selected_cell)

    for field in ("max_reflectivity_dbz", "lightning_rate", "speed_kmh", "shear_knots"):
        value = getattr(request, field)
        if value is not None:
            target = "reflectivity_dbz" if field == "max_reflectivity_dbz" else field
            features[target] = float(value)

    if not features:
        raise HTTPException(status_code=422, detail="Provide cell_id or at least one historical feature")

    defaults = {"reflectivity_dbz": 45.0, "lightning_rate": 8.0, "speed_kmh": 25.0, "shear_knots": 25.0}
    features = {**defaults, **features}
    return {
        "cell_id": request.cell_id,
        "input_features": features,
        "matches": find_analogues(features, request.limit),
        "catalogue_type": "curated demonstration archive",
    }


@router.get("/metrics")
async def get_historical_metrics():
    return {"metrics": VERIFICATION_METRICS}


@router.get("/replay/{event_id}")
async def get_historical_replay(event_id: str):
    event = get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Historical event '{event_id}' was not found")
    return {
        "event": {key: value for key, value in event.items() if key not in {"feature_vector", "origin", "motion"}},
        "frames": generate_replay(event),
        "disclaimer": "Replay coordinates are a deterministic demonstration reconstruction, not official observed radar frames.",
    }

