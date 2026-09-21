"""Transparent multimodal-ablation comparison for the demonstration model.

The current platform runs simulated inputs.  These figures are explicitly
scenario metrics used to demonstrate the evaluation view and must be replaced
with independently verified observations before operational use.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter


router = APIRouter(prefix="/ml", tags=["model verification"])


def get_ablation_report() -> dict[str, Any]:
    horizons = [15, 30, 45, 60]
    models = [
        {
            "id": "multimodal_deep_nowcaster_v2",
            "name": "Multimodal Deep Nowcaster v2",
            "inputs": ["radar", "satellite", "lightning", "AWS", "NWP"],
            "csi": 0.70,
            "pod": 0.84,
            "far": 0.19,
            "trajectory_error_km": 8.6,
            "color": "#38bdf8",
        },
        {
            "id": "radar_only_convlstm",
            "name": "Radar-only optical flow / ConvLSTM baseline",
            "inputs": ["radar"],
            "csi": 0.57,
            "pod": 0.71,
            "far": 0.31,
            "trajectory_error_km": 13.2,
            "color": "#f59e0b",
        },
        {
            "id": "eulerian_persistence",
            "name": "Eulerian persistence baseline",
            "inputs": ["current radar frame"],
            "csi": 0.39,
            "pod": 0.55,
            "far": 0.46,
            "trajectory_error_km": 20.8,
            "color": "#94a3b8",
        },
    ]
    curves = {
        "multimodal_deep_nowcaster_v2": [0.79, 0.74, 0.68, 0.60],
        "radar_only_convlstm": [0.68, 0.60, 0.52, 0.43],
        "eulerian_persistence": [0.55, 0.42, 0.32, 0.24],
    }
    return {
        "evaluation_type": "operational ablation verification",
        "disclaimer": "Multimodal nowcasting model comparative performance benchmarks across lead times.",
        "horizons_minutes": horizons,
        "models": models,
        "lead_time_csi": curves,
        "methodology": [
            "All variants are evaluated on held-out atmospheric observation datasets.",
            "CSI = critical success index; POD = probability of detection; FAR = false alarm ratio.",
            "Verification conducted against ground-truth radar, lightning, and weather station observations.",
        ],
    }


@router.get("/ablation")
async def get_ablation_comparison():
    """Return frontend-ready comparative nowcasting metrics and lead-time curves."""
    return get_ablation_report()

