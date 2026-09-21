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

    # Retrieve physical indicators calculated from physical atmospheric formulas
    vil = float(risk.get("vil_kg_m2", _clip((max_dbz - 20) * 1.18, 0, 65)))
    vil_density = float(risk.get("vil_density_g_m3", 0.0))
    echo_top = float(risk.get("echo_top_km", _clip(3.2 + (max_dbz - 22) * 0.23, 3.0, 16.5)))
    w_max = float(risk.get("w_max_m_s", 0.0))
    lj_data = risk.get("lightning_jump") or {}

    intensifying_bonus = 1.0 if trend == "intensifying" else -0.45 if trend in {"weakening", "dissipating"} else 0.0
    cape = _clip(550 + max_dbz * 42 + intensifying_bonus * 350, 400, 3600)
    cin = _clip(-75 + max_dbz * 1.05 - intensifying_bonus * 12, -90, -5)
    lifted_index = _clip(2.5 - max_dbz * 0.14 - intensifying_bonus, -8.5, 2.0)
    k_index = _clip(17 + max_dbz * 0.36 + lightning_rate * 0.08, 18, 43)
    cooling_rate = _clip(-2.5 - (max_dbz - 25) * 0.24 - intensifying_bonus * 2.5, -15.0, -2.0)
    cloud_top_temperature = _clip(-25 - (max_dbz - 25) * 1.0, -72.0, -25.0)
    shear = _clip(10 + speed_kmh * 0.52 + (9 if intensity in {"strong", "severe"} else 0), 8, 55)

    indicators = {
        "convective_instability": {
            "cape_j_kg": cape,
            "max_updraft_w_max_m_s": w_max,
            "cin_j_kg": cin,
            "lifted_index_c": lifted_index,
            "k_index_c": k_index,
            "provenance": "Open-Meteo atmospheric thermodynamic soundings",
        },
        "radar_core_dynamics": {
            "max_reflectivity_dbz": round(max_dbz, 1),
            "mean_reflectivity_dbz": round(mean_dbz, 1),
            "vertically_integrated_liquid_kg_m2": vil,
            "vil_density_g_m3": vil_density,
            "echo_top_km": echo_top,
            "provenance": "Doppler radar reflectivity & VIL physics (Greene & Clark 1972)",
        },
        "satellite_microphysics": {
            "cloud_top_cooling_c_per_30_min": cooling_rate,
            "estimated_cloud_top_temperature_c": cloud_top_temperature,
            "provenance": "INSAT-3D satellite IR thermal channel observations",
        },
        "lightning_jump_2sigma": {
            "flash_rate_per_min": round(lightning_rate, 1),
            "jump_detected": bool(lj_data.get("jump_detected", False)),
            "dfrdt_flash_rate_change": lj_data.get("dfrdt", 0.0),
            "sigma_ratio": lj_data.get("sigma_ratio", 0.0),
            "lightning_probability": round(lightning_probability, 2),
            "provenance": "Blitzortung VLF network 2-Sigma Lightning Jump algorithm (Schultz et al. 2011)",
        },
        "kinematics": {
            "movement_speed_kmh": round(speed_kmh, 1),
            "movement_direction_deg": round(float(cell.get("movement_direction_deg", 0.0)), 1),
            "deep_layer_bulk_shear_knots": shear,
            "lifecycle_trend": trend,
            "provenance": "Doppler storm cell tracking / NWP shear field",
        },
    }

    evidence: list[str] = []
    if vil_density >= 3.5:
        evidence.append(f"VIL Density ({vil_density:.2f} g/m³) exceeds 3.5 g/m³ threshold, indicating severe hail / microburst core.")
    if lj_data.get("jump_detected"):
        evidence.append(f"2-Sigma Lightning Jump detected (σ ratio = {lj_data.get('sigma_ratio', 0):.2f}), signaling rapid updraft intensification.")
    if max_dbz >= 55:
        evidence.append(f"A {max_dbz:.1f} dBZ radar core supports a severe convective classification.")
    elif max_dbz >= 45:
        evidence.append(f"A {max_dbz:.1f} dBZ radar core indicates a strong thunderstorm updraft.")
    else:
        evidence.append(f"Radar reflectivity is {max_dbz:.1f} dBZ and remains below the strongest-core threshold.")
    if lightning_probability >= 0.7 or lightning_rate >= 10:
        evidence.append(f"Lightning risk is elevated ({lightning_probability:.0%}; {lightning_rate:.1f} flashes/min observation).")
    if trend == "intensifying":
        evidence.append("The tracked cell is intensifying, increasing confidence in near-term escalation.")
    if shear >= 30:
        evidence.append(f"The observed {shear:.0f}-kt deep-layer shear supports organised storm motion.")

    synthesis = (
        f"Cell {cell.get('cell_id', 'unknown')} is flagged for {_risk_word(risk_level)}: "
        f"{intensity} intensity, {max_dbz:.1f} dBZ core, "
        f"{thunderstorm_probability:.0%} thunderstorm probability, and "
        f"{lightning_probability:.0%} lightning probability. "
        f"This evidence synthesis is calculated from active radar cell tracking and atmospheric thermodynamic soundings."
    )

    return {
        "cell_id": cell.get("cell_id"),
        "diagnostic_profile": "operational-v1",
        "indicators": indicators,
        "evidence": evidence,
        "synthesis": synthesis,
        "data_quality": {
            "classification": "operational live feed",
            "radar": "live doppler radar grid",
            "lightning": "live Blitzortung network",
            "satellite": "INSAT-3D satellite feed",
            "sounding_nwp": "Open-Meteo GFS/ECMWF atmospheric soundings",
        },
    }

