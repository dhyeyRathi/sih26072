"""Deterministic, source-grounded meteorological copilot.

This module intentionally does not depend on an external LLM or vector store.
It retrieves from a small curated catalogue of official operational resources
and combines that text context with structured, live platform tools.  The
result is predictable, inspectable, and suitable for a demo/offline setup.

Important safety boundary: this code is a decision-support assistant.  It does
not issue an official warning, invent meteorological observations, or turn an
answer into an operational instruction without forecaster review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
import re
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence


@dataclass(frozen=True)
class KnowledgeDocument:
    """A compact, auditable record used by the local retrieval layer."""

    id: str
    title: str
    organisation: str
    url: str
    summary: str
    tags: tuple[str, ...]
    operational_points: tuple[str, ...]

    def citation(self, relevance: float | None = None) -> dict[str, Any]:
        """Return a JSON-ready citation without exposing retrieval internals."""
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "organisation": self.organisation,
            "url": self.url,
            "summary": self.summary,
        }
        if relevance is not None:
            result["relevance"] = round(float(relevance), 3)
        return result


# These summaries are deliberately short paraphrases of the linked primary
# sources.  Live observations are never stored here; they must come from a
# structured platform tool below.
KNOWLEDGE_BASE: tuple[KnowledgeDocument, ...] = (
    KnowledgeDocument(
        id="imd-nowcast-services",
        title="Nowcast Services of IMD",
        organisation="India Meteorological Department",
        url=(
            "https://mausam.imd.gov.in/imd_latest/contents/pdf/"
            "pubbrochures/NowcastServices%20of%20IMD.pdf"
        ),
        summary=(
            "IMD describes district and station nowcast warning services for "
            "severe weather and associated impacts."
        ),
        tags=(
            "imd", "nowcast", "thunderstorm", "warning", "district",
            "station", "forecaster", "severe-weather",
        ),
        operational_points=(
            "Use the authorised IMD nowcast and warning workflow for official public communication.",
            "Treat this platform as decision support: review current observations, forecast guidance, and impacts before an authorised warning decision.",
        ),
    ),
    KnowledgeDocument(
        id="imd-public-weather-services-sop",
        title="IMD Public Weather Services: Forecasting SOP",
        organisation="India Meteorological Department",
        url="https://mausam.imd.gov.in/imd_latest/contents/pdf/forecasting_sop.pdf",
        summary=(
            "IMD's public-weather-services SOP describes severe-weather "
            "nowcast guidance and the role of regional forecasting centres."
        ),
        tags=(
            "imd", "sop", "forecast", "guidance", "warning", "review",
            "thunderstorm", "workflow",
        ),
        operational_points=(
            "Check the current guidance and local observations before escalating a warning recommendation.",
            "Keep an authorised forecaster in the review and dissemination path for any official warning.",
        ),
    ),
    KnowledgeDocument(
        id="ndma-lightning-safety",
        title="SACHET Lightning: Do's and Don'ts",
        organisation="National Disaster Management Authority",
        url="https://sachet.ndma.gov.in/DosDont",
        summary=(
            "NDMA's SACHET public-safety guidance covers protective actions "
            "for lightning hazards."
        ),
        tags=(
            "ndma", "lightning", "safety", "public", "sachet", "action",
            "outdoor", "shelter",
        ),
        operational_points=(
            "For public lightning-safety messaging, use the current NDMA SACHET guidance rather than a copilot-generated safety script.",
            "Keep public-safety advice separate from the platform's probabilistic forecast output.",
        ),
    ),
    KnowledgeDocument(
        id="wmo-nowcasting-guidelines",
        title="Nowcasting Guidelines – A Summary",
        organisation="World Meteorological Organization",
        url="https://public.wmo.int/media/magazine-article/nowcasting-guidelines-summary",
        summary=(
            "WMO summarises nowcasting as an integrated process using "
            "observations, automated techniques, model guidance, verification, "
            "and forecaster expertise."
        ),
        tags=(
            "wmo", "nowcasting", "verification", "radar", "observation",
            "model", "forecaster", "quality",
        ),
        operational_points=(
            "Interpret automated guidance alongside observations and forecaster expertise.",
            "Verify nowcast products against the phenomena and users they are intended to support.",
        ),
    ),
)


_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "at", "be", "can", "could", "do", "does",
    "for", "from", "give", "how", "i", "in", "is", "it", "me", "of", "on",
    "or", "please", "show", "tell", "that", "the", "this", "to", "what", "which",
    "with", "why", "will", "would", "you",
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tokenise(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]*", value.lower())
        if token not in _STOP_WORDS
    }


def _normalise_for_json(value: Any) -> Any:
    """Convert numpy/scalar-like values to plain JSON-compatible values.

    Live modules currently use numpy in several places.  Keeping this conversion
    here makes a copilot response safe even when a live source returns numpy
    scalar values.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _normalise_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalise_for_json(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _normalise_for_json(value.item())
        except Exception:
            pass
    return str(value)


def retrieve_knowledge(query: str, limit: int = 3) -> list[dict[str, Any]]:
    """Retrieve relevant trusted-source records using transparent term scoring.

    This intentionally uses a deterministic lexical ranker instead of pretending
    that a local static catalogue is a semantic/vector database.  Returned
    records always carry their primary-source URL for display by the client.
    """
    safe_limit = max(1, min(int(limit), len(KNOWLEDGE_BASE)))
    query_tokens = _tokenise(query)
    scored: list[tuple[float, KnowledgeDocument]] = []

    for document in KNOWLEDGE_BASE:
        title_tokens = _tokenise(document.title)
        tag_tokens = set(document.tags)
        body_tokens = _tokenise(
            " ".join((document.summary, *document.operational_points))
        )

        title_matches = len(query_tokens & title_tokens)
        tag_matches = len(query_tokens & tag_tokens)
        body_matches = len(query_tokens & body_tokens)
        score = (title_matches * 3.0) + (tag_matches * 2.0) + body_matches

        # A query that explicitly names an organisation should retain that
        # source even if wording differs from the document summary.
        if document.organisation.lower() in query.lower():
            score += 3.0
        scored.append((score, document))

    scored.sort(key=lambda item: (-item[0], item[1].id))
    selected = scored[:safe_limit]

    # If a question contains no useful document terms, prefer general
    # nowcasting governance material rather than presenting a fake match.
    if not query_tokens or selected[0][0] == 0:
        fallback_ids = ("wmo-nowcasting-guidelines", "imd-nowcast-services")
        fallback = [doc for doc in KNOWLEDGE_BASE if doc.id in fallback_ids]
        selected = [(0.0, doc) for doc in fallback[:safe_limit]]

    max_score = max((score for score, _ in selected), default=0.0)
    return [
        document.citation(relevance=(score / max_score) if max_score else 0.0)
        for score, document in selected
    ]


def _tool_result(tool: str, data: Any = None, error: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tool": tool,
        "available": error is None,
        "retrieved_at": _utc_now(),
    }
    if error is not None:
        result["error"] = error
    else:
        result["data"] = _normalise_for_json(data)
    return result


def get_live_storms(cell_id: str | None = None) -> dict[str, Any]:
    """Return active tracked cells and structured risk-engine outputs.

    Imports are intentionally local.  This allows the knowledge-only copilot to
    remain usable in a lightweight environment where model runtime imports are
    not available.
    """
    try:
        from src.risk.engine import assess_storm_risk
        from src.storms.tracking import storm_tracker

        cells = storm_tracker.get_active_cells()
        if cell_id:
            wanted = cell_id.strip().lower()
            cells = [cell for cell in cells if str(cell.get("cell_id", "")).lower() == wanted]

        snapshots = [
            {
                "cell": cell,
                "risk": assess_storm_risk(cell),
            }
            for cell in cells
        ]
        return _tool_result(
            "live_storms",
            {
                "source": "platform_runtime",
                "count": len(snapshots),
                "cell_id_filter": cell_id,
                "cells": snapshots,
            },
        )
    except Exception as exc:
        return _tool_result("live_storms", error=f"Live storm data is unavailable: {exc}")


def get_live_trajectories(cell_id: str | None = None) -> dict[str, Any]:
    """Return the current model trajectory objects, when the runtime is ready."""
    try:
        from src.storms.tracking import storm_tracker

        trajectories = storm_tracker.predict_trajectories(horizons_minutes=[15, 30, 45, 60])
        if cell_id:
            wanted = cell_id.strip().lower()
            trajectories = [
                item for item in trajectories
                if str(item.get("cell_id", "")).lower() == wanted
            ]
        return _tool_result(
            "live_trajectories",
            {
                "source": "platform_runtime",
                "count": len(trajectories),
                "cell_id_filter": cell_id,
                "trajectories": trajectories,
            },
        )
    except Exception as exc:
        return _tool_result("live_trajectories", error=f"Live trajectory data is unavailable: {exc}")


def get_live_infrastructure(cell_id: str | None = None) -> dict[str, Any]:
    """Assess current infrastructure exposure from existing platform modules."""
    storms_result = get_live_storms(cell_id)
    trajectories_result = get_live_trajectories(cell_id)
    if not storms_result["available"]:
        return _tool_result("live_infrastructure", error=storms_result["error"])
    if not trajectories_result["available"]:
        return _tool_result("live_infrastructure", error=trajectories_result["error"])

    try:
        from src.exposure.infrastructure import assess_all_infrastructure

        storms = [item["cell"] for item in storms_result["data"]["cells"]]
        trajectories = trajectories_result["data"]["trajectories"]
        exposure = assess_all_infrastructure(storms, trajectories)
        return _tool_result(
            "live_infrastructure",
            {
                "source": "platform_runtime",
                "cell_id_filter": cell_id,
                **exposure,
            },
        )
    except Exception as exc:
        return _tool_result(
            "live_infrastructure",
            error=f"Infrastructure exposure data is unavailable: {exc}",
        )


def get_live_radar_summary() -> dict[str, Any]:
    """Return a small observation summary without placing radar grids in RAG."""
    try:
        from src.ingestion.simulator import data_generator

        frame = data_generator.get_current_frame()
        grid = frame.get("grid")
        if grid is None:
            raise ValueError("The current frame has no radar grid")
        max_dbz = float(grid.max())
        active = int((grid >= 10).sum())
        return _tool_result(
            "live_radar_summary",
            {
                # The present development source is explicitly identified so a
                # user cannot mistake it for an IMD operational feed.
                "source": "simulated_platform_runtime",
                "timestamp": frame.get("timestamp"),
                "grid_shape": frame.get("grid_shape"),
                "max_reflectivity_dbz": round(max_dbz, 1),
                "grid_points_at_or_above_10_dbz": active,
                "storm_count": len(frame.get("storms", [])),
            },
        )
    except Exception as exc:
        return _tool_result("live_radar_summary", error=f"Radar summary is unavailable: {exc}")


def get_live_weather_context(cell_id: str | None = None) -> dict[str, Any]:
    """Collect the live information classes used by the copilot."""
    storms = get_live_storms(cell_id)
    trajectories = get_live_trajectories(cell_id)
    radar = get_live_radar_summary()
    return {
        "storms": storms,
        "trajectories": trajectories,
        "radar": radar,
    }


def _find_document(document_id: str) -> KnowledgeDocument | None:
    return next((doc for doc in KNOWLEDGE_BASE if doc.id == document_id), None)


def _extract_cell_id(question: str) -> str | None:
    match = re.search(r"\bC[-\s]?(\d{1,8})\b", question, flags=re.IGNORECASE)
    return f"C-{match.group(1)}" if match else None


def _risk_summary(storms_result: Mapping[str, Any], requested_cell: str | None) -> str:
    if not storms_result.get("available"):
        return "Current storm risk could not be retrieved from the platform runtime."

    snapshots = storms_result.get("data", {}).get("cells", [])
    if requested_cell and not snapshots:
        return f"No active tracked cell matching {requested_cell} is available in the current platform state."
    if not snapshots:
        return "No active tracked storm cells are available in the current platform state."

    lines: list[str] = []
    for snapshot in snapshots[:5]:
        cell = snapshot.get("cell", {})
        risk = snapshot.get("risk", {})
        cell_name = cell.get("cell_id", "unidentified cell")
        segments = [f"{cell_name}: risk {risk.get('risk_level', 'unavailable')}."]
        if risk.get("thunderstorm_probability") is not None:
            segments.append(
                f"Thunderstorm probability {risk['thunderstorm_probability']:.0%}."
            )
        if risk.get("lightning_probability") is not None:
            segments.append(f"Lightning probability {risk['lightning_probability']:.0%}.")
        if cell.get("max_reflectivity_dbz") is not None:
            segments.append(f"Maximum reflectivity {cell['max_reflectivity_dbz']} dBZ.")
        if cell.get("lightning_rate") is not None:
            segments.append(f"Platform lightning-rate value {cell['lightning_rate']}.")
        lines.append(" ".join(segments))
    return "Current structured risk output: " + " ".join(lines)


def _trajectory_summary(trajectories_result: Mapping[str, Any], requested_cell: str | None) -> str:
    if not trajectories_result.get("available"):
        return "Current trajectory guidance could not be retrieved from the platform runtime."

    trajectories = trajectories_result.get("data", {}).get("trajectories", [])
    if requested_cell and not trajectories:
        return f"No current trajectory is available for {requested_cell}."
    if not trajectories:
        return "No current storm trajectories are available in the platform state."

    summaries: list[str] = []
    for trajectory in trajectories[:3]:
        forecasts = trajectory.get("forecasts", [])
        if not forecasts:
            continue
        compact_forecasts = []
        for forecast in (forecasts[0], forecasts[-1]) if len(forecasts) > 1 else forecasts:
            compact_forecasts.append(
                "{horizon} min: ({lat}, {lon}), uncertainty {uncertainty} km".format(
                    horizon=forecast.get("horizon_minutes", "?"),
                    lat=forecast.get("predicted_lat", "?"),
                    lon=forecast.get("predicted_lon", "?"),
                    uncertainty=forecast.get("uncertainty_km", "?"),
                )
            )
        summaries.append(
            f"{trajectory.get('cell_id', 'unidentified cell')} forecast — "
            + "; ".join(compact_forecasts)
            + "."
        )
    return "Current model trajectory guidance: " + " ".join(summaries) if summaries else (
        "The platform returned trajectory objects without forecast points."
    )


def _exposure_summary(exposure_result: Mapping[str, Any]) -> str:
    if not exposure_result.get("available"):
        return "Current infrastructure exposure could not be retrieved from the platform runtime."

    data = exposure_result.get("data", {})
    summary = data.get("summary", {})
    threatened = [
        asset for asset in data.get("assets", [])
        if asset.get("threat_level") in {"critical", "warning"}
    ]
    if not threatened:
        return "The current exposure calculation lists no critical or warning-level infrastructure assets."

    names = []
    for asset in threatened[:5]:
        eta = asset.get("estimated_arrival_minutes")
        eta_text = f", ETA {eta} min" if eta is not None else ""
        names.append(f"{asset.get('name', asset.get('id', 'asset'))} ({asset.get('threat_level')}{eta_text})")
    return (
        "Current infrastructure exposure: "
        f"{summary.get('critical_count', 0)} critical and "
        f"{summary.get('warning_count', 0)} warning-level assets. "
        "Affected assets: " + "; ".join(names) + "."
    )


def _radar_summary(radar_result: Mapping[str, Any]) -> str:
    if not radar_result.get("available"):
        return "Current radar observation summary could not be retrieved from the platform runtime."
    data = radar_result.get("data", {})
    source = data.get("source", "platform_runtime")
    return (
        f"Current radar summary ({source}): maximum reflectivity "
        f"{data.get('max_reflectivity_dbz', 'unavailable')} dBZ; "
        f"{data.get('storm_count', 'unavailable')} source storm records; "
        f"frame timestamp {data.get('timestamp', 'unavailable')}."
    )


def _knowledge_guidance(citations: Sequence[Mapping[str, Any]]) -> str:
    points: list[str] = []
    for citation in citations:
        document = _find_document(str(citation.get("id", "")))
        if document is None:
            continue
        for point in document.operational_points[:1]:
            points.append(f"{point} [{document.title}]")
    return "Source-grounded operational context: " + " ".join(points) if points else ""


def get_suggestions() -> list[dict[str, str]]:
    """Return frontend-ready prompts without making a live-data call."""
    return [
        {
            "id": "active-risk",
            "label": "Summarize active risks",
            "question": "Summarize the current active storm-cell risks.",
        },
        {
            "id": "cell-threat",
            "label": "Analyse cell C-1001",
            "question": "Analyse the current threat from cell C-1001.",
        },
        {
            "id": "infrastructure",
            "label": "Threatened infrastructure",
            "question": "Which hospitals and other critical infrastructure are currently at risk?",
        },
        {
            "id": "forecast",
            "label": "60-minute forecast",
            "question": "Summarize the current 60-minute storm trajectory guidance.",
        },
        {
            "id": "imd-sop",
            "label": "Relevant IMD workflow",
            "question": "What IMD operational workflow guidance is relevant to a thunderstorm nowcast warning?",
        },
        {
            "id": "lightning-safety",
            "label": "Lightning safety source",
            "question": "Which official source should be used for public lightning-safety guidance?",
        },
    ]


def answer_question(
    question: str,
    *,
    cell_id: str | None = None,
    include_live_data: bool = True,
    document_limit: int = 3,
) -> dict[str, Any]:
    """Build a cited, deterministic answer for a forecaster question.

    The answer contains both readable prose and the structured tool payloads
    used to create it.  Clients can therefore render numbers from their source
    rather than scraping them back out of text.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("A non-empty question is required")

    clean_question = question.strip()
    requested_cell = cell_id.strip().upper() if cell_id and cell_id.strip() else _extract_cell_id(clean_question)
    terms = _tokenise(clean_question)
    citations = retrieve_knowledge(clean_question, limit=document_limit)
    live_data: dict[str, Any] = {}
    tool_calls: list[dict[str, Any]] = []
    sections: list[str] = []

    risk_terms = {"risk", "warning", "threat", "high", "severe", "why", "active", "current", "cell"}
    forecast_terms = {"forecast", "trajectory", "eta", "arrival", "60", "minute", "nowcast", "movement"}
    exposure_terms = {
        "hospital", "hospitals", "airport", "airports", "infrastructure",
        "asset", "assets", "exposure", "highway", "highways", "power",
        "grid", "district", "districts", "facility", "facilities",
    }
    radar_terms = {"radar", "reflectivity", "observation", "dbz"}
    guidance_terms = {"sop", "guidance", "procedure", "protocol", "imd", "ndma", "wmo", "safety", "action"}

    asks_risk = bool(terms & risk_terms) or requested_cell is not None
    asks_forecast = bool(terms & forecast_terms)
    asks_exposure = bool(terms & exposure_terms)
    asks_radar = bool(terms & radar_terms)
    asks_guidance = bool(terms & guidance_terms)

    if include_live_data and (asks_risk or asks_forecast or asks_exposure):
        storms = get_live_storms(requested_cell)
        live_data["storms"] = storms
        tool_calls.append({
            "name": "live_storms",
            "available": storms["available"],
            "purpose": "active cells and risk-engine output",
        })
        if asks_risk:
            sections.append(_risk_summary(storms, requested_cell))

    if include_live_data and (asks_forecast or asks_exposure):
        trajectories = get_live_trajectories(requested_cell)
        live_data["trajectories"] = trajectories
        tool_calls.append({
            "name": "live_trajectories",
            "available": trajectories["available"],
            "purpose": "current model trajectory guidance",
        })
        if asks_forecast:
            sections.append(_trajectory_summary(trajectories, requested_cell))

    if include_live_data and asks_exposure:
        # Reuse the independent tool output in the response so an operator can
        # inspect the exact asset assessment behind the prose.
        exposure = get_live_infrastructure(requested_cell)
        live_data["infrastructure"] = exposure
        tool_calls.append({
            "name": "live_infrastructure",
            "available": exposure["available"],
            "purpose": "critical-infrastructure exposure assessment",
        })
        sections.append(_exposure_summary(exposure))

    if include_live_data and asks_radar:
        radar = get_live_radar_summary()
        live_data["radar"] = radar
        tool_calls.append({
            "name": "live_radar_summary",
            "available": radar["available"],
            "purpose": "current radar observation summary",
        })
        sections.append(_radar_summary(radar))

    # A pure live-data question still gets a compact provenance note.  A policy
    # or general question gets guidance from the actual curated source records.
    if asks_guidance or not sections:
        guidance = _knowledge_guidance(citations)
        if guidance:
            sections.append(guidance)

    if not sections:
        sections.append(
            "I could not retrieve a matching live platform tool result or trusted guidance record for that question."
        )

    guardrails = [
        "Decision-support only: this copilot cannot issue, approve, or disseminate an official warning.",
        "Live numerical values are shown only when returned by a structured platform tool; they are not retrieved from the document catalogue.",
        "The current development radar tool is labelled simulated_platform_runtime and must not be represented as an IMD operational feed.",
        "An authorised forecaster remains responsible for interpretation and any official action.",
    ]

    return {
        "question": clean_question,
        "answer": "\n\n".join(section for section in sections if section),
        "requested_cell_id": requested_cell,
        "sources": citations,
        "tool_calls": tool_calls,
        "live_data": _normalise_for_json(live_data),
        "guardrails": guardrails,
        "generated_at": _utc_now(),
    }


__all__ = [
    "KNOWLEDGE_BASE",
    "KnowledgeDocument",
    "answer_question",
    "get_live_infrastructure",
    "get_live_radar_summary",
    "get_live_storms",
    "get_live_trajectories",
    "get_live_weather_context",
    "get_suggestions",
    "retrieve_knowledge",
]
