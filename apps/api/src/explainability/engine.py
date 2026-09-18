"""Explainable, deterministic warning evidence for active storm cells.

The live demo currently runs on simulated radar and lightning observations.  The
diagnostics below are therefore transparent *derived indicators*, not claims of
live radiosonde, satellite, or radar-volume measurements.  They provide the
same structured explanation interface that real data adapters can populate in a
production deployment.
"""

from __future__ import annotations

from typing import Any


def _clip(value: float, lower: float, upper: float) -> float:
    return round(max(lower, min(upper, value)), 1)


def _risk_word(risk_level: str) -> str:
    return {
        "severe": "immediate severe-weather action",
        "high": "an operational warning review",
        "moderate": "heightened monitoring",
        "low": "routine monitoring",
    }.get(risk_level, "monitoring")


def build_warning_evidence(cell: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    """Create a fully serialisable meteorological explanation for one cell.

    Values are derived from available cell attributes using conservative,
    documented demo transforms.  Each indicator carries its provenance so an
    operator can distinguish observed values from simulated/derived ones.
    """
    max_dbz = float(cell.get("max_reflectivity_dbz", 0.0))
    mean_dbz = float(cell.get("mean_reflectivity_dbz", max_dbz * 0.72))
    lightning_rate = float(cell.get("lightning_rate", 0.0))
    speed_kmh = float(cell.get("movement_speed_kmh", 0.0))
    trend = str(cell.get("trend", "steady"))
    intensity = str(cell.get("intensity", "weak"))
    risk_level = str(risk.get("risk_level", "low"))
    thunderstorm_probability = float(risk.get("thunderstorm_probability", 0.0))
    lightning_probability = float(risk.get("lightning_probability", 0.0))

    intensifying_bonus = 1.0 if trend == "intensifying" else -0.45 if trend in {"weakening", "dissipating"} else 0.0
    cape = _clip(550 + max_dbz * 42 + intensifying_bonus * 350, 400, 3600)
    cin = _clip(-75 + max_dbz * 1.05 - intensifying_bonus * 12, -90, -5)
    lifted_index = _clip(2.5 - max_dbz * 0.14 - intensifying_bonus, -8.5, 2.0)
    k_index = _clip(17 + max_dbz * 0.36 + lightning_rate * 0.08, 18, 43)
    vil = _clip((max_dbz - 20) * 1.18, 0, 65)
    echo_top = _clip(3.2 + (max_dbz - 22) * 0.23, 3.0, 16.5)
    cooling_rate = _clip(-2.5 - (max_dbz - 25) * 0.24 - intensifying_bonus * 2.5, -15.0, -2.0)
    cloud_top_temperature = _clip(-25 - (max_dbz - 25) * 1.0, -72.0, -25.0)
    lightning_jump = _clip((lightning_rate * 9.5) + (35 if trend == "intensifying" else -10 if trend == "weakening" else 0), -20, 240)
    shear = _clip(10 + speed_kmh * 0.52 + (9 if intensity in {"strong", "severe"} else 0), 8, 55)

    indicators = {
        "convective_instability": {
            "cape_j_kg": cape,
            "cin_j_kg": cin,
            "lifted_index_c": lifted_index,
            "k_index_c": k_index,
            "provenance": "derived from simulated cell intensity and lifecycle",
        },
        "radar_core_dynamics": {
            "max_reflectivity_dbz": round(max_dbz, 1),
            "mean_reflectivity_dbz": round(mean_dbz, 1),
            "vertically_integrated_liquid_kg_m2": vil,
            "echo_top_km": echo_top,
            "provenance": "simulated radar reflectivity / derived volume proxies",
        },
        "satellite_microphysics": {
            "cloud_top_cooling_c_per_30_min": cooling_rate,
            "estimated_cloud_top_temperature_c": cloud_top_temperature,
            "provenance": "derived proxy; no live INSAT adapter connected",
        },
        "lightning_jump": {
            "flash_rate_per_min": round(lightning_rate, 1),
            "ten_min_acceleration_percent": lightning_jump,
            "lightning_probability": round(lightning_probability, 2),
            "provenance": "simulated lightning feed / lifecycle-derived acceleration",
        },
        "kinematics": {
            "movement_speed_kmh": round(speed_kmh, 1),
            "movement_direction_deg": round(float(cell.get("movement_direction_deg", 0.0)), 1),
            "deep_layer_bulk_shear_knots": shear,
            "lifecycle_trend": trend,
            "provenance": "tracked-cell motion / derived shear proxy",
        },
    }

    evidence: list[str] = []
    if max_dbz >= 55:
        evidence.append(f"A {max_dbz:.1f} dBZ radar core supports a severe convective classification.")
    elif max_dbz >= 45:
        evidence.append(f"A {max_dbz:.1f} dBZ radar core indicates a strong thunderstorm updraft.")
    else:
        evidence.append(f"Radar reflectivity is {max_dbz:.1f} dBZ and remains below the strongest-core threshold.")
    if lightning_probability >= 0.7 or lightning_rate >= 10:
        evidence.append(f"Lightning risk is elevated ({lightning_probability:.0%}; {lightning_rate:.1f} flashes/min proxy).")
    if trend == "intensifying":
        evidence.append("The tracked cell is intensifying, increasing confidence in near-term escalation.")
    if shear >= 30:
        evidence.append(f"The derived {shear:.0f}-kt deep-layer shear proxy supports organised storm motion.")

    synthesis = (
        f"Cell {cell.get('cell_id', 'unknown')} is flagged for {_risk_word(risk_level)}: "
        f"{intensity} intensity, {max_dbz:.1f} dBZ core, "
        f"{thunderstorm_probability:.0%} thunderstorm probability, and "
        f"{lightning_probability:.0%} lightning probability. "
        f"This explanation uses live demo cell data plus transparent derived proxies."
    )

    return {
        "cell_id": cell.get("cell_id"),
        "diagnostic_profile": "simulated-derived-v1",
        "indicators": indicators,
        "evidence": evidence,
        "synthesis": synthesis,
        "data_quality": {
            "classification": "demonstration / simulated inputs",
            "radar": "simulated live grid",
            "lightning": "simulated live feed",
            "satellite": "not connected; proxy shown",
            "sounding_nwp": "not connected; proxy shown",
        },
    }

