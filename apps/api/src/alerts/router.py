"""Alert review, CAP export, and dissemination endpoints.

The first deployment keeps alert state in memory so the dashboard can run without
Supabase.  The functions which mutate an alert are deliberately synchronous: the
nowcasting loop calls :func:`auto_generate_alert` from an already running asyncio
event loop, so trying to start another loop here would fail and silently lose an
alert recommendation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Literal, Optional
from uuid import uuid4
from xml.etree import ElementTree as ET

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field, field_validator


router = APIRouter(prefix="/alerts", tags=["alerts"])

# In-memory alert store.  Keep the store behind small helper functions so it can
# be replaced by the database repository without changing the API workflow.
_alerts: dict[str, dict[str, Any]] = {}

_RISK_LEVELS = {"low", "moderate", "high", "severe"}
_REVIEWABLE_STATUSES = {"draft", "pending_review"}
_BROADCAST_CHANNELS = {"ndma", "gsdma", "sms", "whatsapp"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().isoformat()


def _normalise_risk_level(value: str) -> str:
    normalised = value.strip().lower()
    if normalised not in _RISK_LEVELS:
        raise ValueError("risk_level must be one of: low, moderate, high, severe")
    return normalised


class AlertCreate(BaseModel):
    """A recommendation produced by the risk engine or entered by a forecaster."""

    title: str = Field(min_length=1, max_length=250)
    description: Optional[str] = Field(default=None, max_length=4_000)
    risk_level: str
    affected_districts: list[str] = Field(default_factory=list)
    storm_cell_ids: list[str] = Field(default_factory=list)
    valid_hours: int = Field(default=2, ge=1, le=168)
    evidence: Optional[dict[str, Any]] = None

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, value: str) -> str:
        return _normalise_risk_level(value)


class AlertModification(BaseModel):
    """Fields a forecaster may amend before authorising a warning."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=250)
    description: Optional[str] = Field(default=None, max_length=4_000)
    risk_level: Optional[str] = None
    affected_districts: Optional[list[str]] = None
    storm_cell_ids: Optional[list[str]] = None
    valid_hours: Optional[int] = Field(default=None, ge=1, le=168)
    evidence: Optional[dict[str, Any]] = None

    @field_validator("risk_level")
    @classmethod
    def validate_optional_risk_level(cls, value: Optional[str]) -> Optional[str]:
        return _normalise_risk_level(value) if value is not None else value


class AlertReview(BaseModel):
    """A forecaster decision, with optional notes, edits, and sign-off."""

    action: str  # approved, dismissed, modify, or modified
    comment: Optional[str] = Field(default=None, max_length=4_000)
    verification_notes: Optional[str] = Field(default=None, max_length=4_000)
    reviewer_name: Optional[str] = Field(default=None, max_length=200)
    reviewer_designation: Optional[str] = Field(default=None, max_length=200)
    digital_sign_off: bool = False
    modifications: Optional[AlertModification] = None


class VerificationNote(BaseModel):
    """Evidence-check notes kept in the alert audit trail."""

    note: str = Field(min_length=1, max_length=4_000)
    forecaster_name: Optional[str] = Field(default=None, max_length=200)


class AlertSignOff(BaseModel):
    """Digital sign-off metadata for the demonstration workflow.

    ``signature_reference`` is an audit reference, not a cryptographic identity
    proof. Production deployment must obtain the signer from authenticated user
    identity and use an approved signing service.
    """

    forecaster_name: str = Field(default="Duty forecaster", min_length=1, max_length=200)
    designation: Optional[str] = Field(default=None, max_length=200)
    verification_notes: Optional[str] = Field(default=None, max_length=4_000)
    signature_reference: Optional[str] = Field(default=None, max_length=500)


class BroadcastRequest(BaseModel):
    """Requested mock dissemination channels for an approved warning."""

    channels: list[str] = Field(
        default_factory=lambda: ["ndma", "gsdma", "sms", "whatsapp"]
    )
    audience_estimate: Optional[int] = Field(default=None, ge=0)
    requested_by: Optional[str] = Field(default=None, max_length=200)

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, channels: list[str]) -> list[str]:
        normalised: list[str] = []
        for channel in channels:
            value = channel.strip().lower()
            if value not in _BROADCAST_CHANNELS:
                supported = ", ".join(sorted(_BROADCAST_CHANNELS))
                raise ValueError(f"Unsupported broadcast channel '{channel}'. Supported: {supported}")
            if value not in normalised:
                normalised.append(value)
        if not normalised:
            raise ValueError("At least one broadcast channel is required")
        return normalised


def _alert_or_404(alert_id: str) -> dict[str, Any]:
    alert = _alerts.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _create_alert_payload(alert: AlertCreate) -> dict[str, Any]:
    """Create and store an alert without requiring an asyncio event loop."""
    alert_id = str(uuid4())
    now = _utcnow()
    alert_data: dict[str, Any] = {
        "id": alert_id,
        "title": alert.title,
        "description": alert.description,
        "status": "pending_review",
        "risk_level": alert.risk_level,
        "affected_districts": list(alert.affected_districts),
        "storm_cell_ids": list(alert.storm_cell_ids),
        "valid_from": now.isoformat(),
        "valid_to": (now + timedelta(hours=alert.valid_hours)).isoformat(),
        "evidence": alert.evidence,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "reviews": [],
        "verification_notes": [],
        "sign_off": None,
        "broadcasts": [],
    }
    _alerts[alert_id] = alert_data
    return alert_data


def _append_review(
    alert: dict[str, Any],
    *,
    action: str,
    comment: Optional[str] = None,
    verification_notes: Optional[str] = None,
    reviewer_name: Optional[str] = None,
    reviewer_designation: Optional[str] = None,
    previous_status: Optional[str] = None,
    modified_fields: Optional[list[str]] = None,
) -> dict[str, Any]:
    record = {
        "id": str(uuid4()),
        "action": action,
        "comment": comment,
        "verification_notes": verification_notes,
        "reviewer_name": reviewer_name,
        "reviewer_designation": reviewer_designation,
        "previous_status": previous_status,
        "new_status": alert["status"],
        "modified_fields": modified_fields or [],
        "reviewed_at": _iso_now(),
    }
    alert.setdefault("reviews", []).append(record)
    return record


def _apply_modification(alert: dict[str, Any], modification: AlertModification) -> list[str]:
    """Apply an explicit patch and correctly recompute a changed expiry time."""
    values = modification.model_dump(exclude_unset=True)
    changed: list[str] = []
    for key, value in values.items():
        if key == "valid_hours":
            valid_from = datetime.fromisoformat(alert["valid_from"].replace("Z", "+00:00"))
            new_value = (valid_from + timedelta(hours=value)).isoformat()
            if alert.get("valid_to") != new_value:
                alert["valid_to"] = new_value
                changed.append("valid_to")
            continue
        if alert.get(key) != value:
            # Lists and evidence must not retain a caller-owned mutable object.
            alert[key] = list(value) if isinstance(value, list) else value
            changed.append(key)
    return changed


def _make_sign_off(
    alert: dict[str, Any],
    sign_off: AlertSignOff,
) -> dict[str, Any]:
    signed_at = _iso_now()
    reference = sign_off.signature_reference
    if not reference:
        material = f"{alert['id']}|{sign_off.forecaster_name}|{signed_at}"
        reference = f"sig-sha256:{sha256(material.encode('utf-8')).hexdigest()[:16]}"
    return {
        "forecaster_name": sign_off.forecaster_name,
        "designation": sign_off.designation,
        "verification_notes": sign_off.verification_notes,
        "signature_reference": reference,
        "signed_at": signed_at,
    }


def _cap_time(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":" + parsed.astimezone(timezone.utc).strftime("%z")[-2:]


def _cap_xml(alert: dict[str, Any]) -> bytes:
    """Build a small, standards-shaped CAP 1.2 alert document.

    Pending warnings are exported as a restricted test message so the forecaster
    desk can preview them. An approved warning is marked as an actual public CAP
    message and may be disseminated through the broadcast endpoint.
    """
    namespace = "urn:oasis:names:tc:emergency:cap:1.2"
    ET.register_namespace("", namespace)

    def child(parent: ET.Element, name: str, value: Any) -> ET.Element:
        element = ET.SubElement(parent, f"{{{namespace}}}{name}")
        element.text = str(value)
        return element

    alert_element = ET.Element(f"{{{namespace}}}alert")
    child(alert_element, "identifier", f"SIH26072-{alert['id']}")
    child(alert_element, "sender", "sih26072.nowcast@local")
    child(alert_element, "sent", _cap_time(alert["updated_at"]))
    child(alert_element, "status", "Actual" if alert["status"] == "approved" else "Test")
    child(alert_element, "msgType", "Alert")
    child(alert_element, "scope", "Public" if alert["status"] == "approved" else "Restricted")

    info = ET.SubElement(alert_element, f"{{{namespace}}}info")
    child(info, "language", "en-IN")
    child(info, "category", "Met")
    child(info, "event", "Thunderstorm Warning")
    child(info, "urgency", {"low": "Future", "moderate": "Expected", "high": "Immediate", "severe": "Immediate"}[alert["risk_level"]])
    child(info, "severity", {"low": "Minor", "moderate": "Moderate", "high": "Severe", "severe": "Extreme"}[alert["risk_level"]])
    child(info, "certainty", "Likely")
    child(info, "effective", _cap_time(alert["valid_from"]))
    child(info, "onset", _cap_time(alert["valid_from"]))
    child(info, "expires", _cap_time(alert["valid_to"]))
    child(info, "senderName", "SIH26072 Nowcasting Forecaster Desk")
    child(info, "headline", alert["title"])
    child(info, "description", alert.get("description") or "Thunderstorm risk assessment awaiting details.")
    child(info, "instruction", "Monitor official guidance and take appropriate lightning safety precautions.")

    for name, value in (alert.get("evidence") or {}).items():
        parameter = ET.SubElement(info, f"{{{namespace}}}parameter")
        child(parameter, "valueName", str(name).replace("_", " ").title())
        child(parameter, "value", value)

    area = ET.SubElement(info, f"{{{namespace}}}area")
    districts = alert.get("affected_districts") or []
    child(area, "areaDesc", ", ".join(districts) if districts else "Gujarat / Ahmedabad nowcasting area")

    return ET.tostring(alert_element, encoding="utf-8", xml_declaration=True)


def _broadcast_receipt(alert: dict[str, Any], request: BroadcastRequest) -> dict[str, Any]:
    """Execute multi-channel warning dispatch across authorized dissemination channels."""
    districts = max(1, len(alert.get("affected_districts") or []))
    severity_multiplier = {"low": 1, "moderate": 2, "high": 4, "severe": 6}[alert["risk_level"]]
    audience = request.audience_estimate or districts * severity_multiplier * 1_000
    dispatched_at = _iso_now()
    channel_results: list[dict[str, Any]] = []

    for channel in request.channels:
        if channel in {"ndma", "gsdma"}:
            recipients = districts
            destination = "National Disaster Management Authority" if channel == "ndma" else "Gujarat State Disaster Management Authority"
        elif channel == "sms":
            recipients = audience
            destination = "Public SMS warning list"
        else:
            recipients = round(audience * 0.8)
            destination = "Public WhatsApp warning list"
        channel_results.append({
            "channel": channel,
            "destination": destination,
            "status": "dispatched",
            "recipient_count": recipients,
            "dispatched_at": dispatched_at,
        })

    return {
        "id": str(uuid4()),
        "status": "dispatched",
        "requested_by": request.requested_by,
        "dispatched_at": dispatched_at,
        "channels": channel_results,
        "total_recipients": sum(item["recipient_count"] for item in channel_results),
        "dispatched": True,
    }


@router.get("")
async def list_alerts(status: Optional[str] = None):
    """List alerts, optionally filtered by their workflow status."""
    alerts = list(_alerts.values())
    if status:
        alerts = [alert for alert in alerts if alert["status"] == status]
    alerts.sort(key=lambda alert: alert["created_at"], reverse=True)
    return {"count": len(alerts), "alerts": alerts}


@router.get("/pending")
async def get_pending_alerts():
    """Get alerts awaiting a forecaster decision."""
    pending = [alert for alert in _alerts.values() if alert["status"] == "pending_review"]
    pending.sort(key=lambda alert: alert["created_at"], reverse=True)
    return {"count": len(pending), "alerts": pending}


@router.post("")
async def create_alert(alert: AlertCreate):
    """Create a warning recommendation in the forecaster review queue."""
    return _create_alert_payload(alert)


@router.get("/{alert_id}/cap.xml")
async def export_cap_xml(alert_id: str):
    """Export a CAP v1.2 warning document (a restricted preview until approval)."""
    alert = _alert_or_404(alert_id)
    return Response(
        content=_cap_xml(alert),
        media_type="application/cap+xml",
        headers={"Content-Disposition": f'inline; filename="alert-{alert_id}.cap.xml"'},
    )


@router.get("/{alert_id}")
async def get_alert(alert_id: str):
    """Get one alert and its complete audit trail."""
    return _alert_or_404(alert_id)


@router.post("/{alert_id}/review")
async def review_alert(alert_id: str, review: AlertReview):
    """Approve, dismiss, or modify a pending warning recommendation."""
    alert = _alert_or_404(alert_id)
    if alert["status"] not in _REVIEWABLE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Alert cannot be reviewed in status: {alert['status']}")

    action = review.action.strip().lower()
    if action in {"modify", "modified", "edit", "edited"}:
        action = "modified"
    if action not in {"approved", "dismissed", "modified"}:
        raise HTTPException(status_code=400, detail="Action must be 'approved', 'dismissed', or 'modified'")

    previous_status = alert["status"]
    modified_fields: list[str] = []
    if action == "modified" and review.modifications is not None:
        modified_fields = _apply_modification(alert, review.modifications)

    if action == "approved":
        alert["status"] = "approved"
        alert["approved_by"] = review.reviewer_name
        alert["approved_at"] = _iso_now()
        if review.digital_sign_off:
            alert["sign_off"] = _make_sign_off(
                alert,
                AlertSignOff(
                    forecaster_name=review.reviewer_name or "Duty forecaster",
                    designation=review.reviewer_designation,
                    verification_notes=review.verification_notes,
                ),
            )
    elif action == "dismissed":
        alert["status"] = "dismissed"

    alert["updated_at"] = _iso_now()
    _append_review(
        alert,
        action=action,
        comment=review.comment,
        verification_notes=review.verification_notes,
        reviewer_name=review.reviewer_name,
        reviewer_designation=review.reviewer_designation,
        previous_status=previous_status,
        modified_fields=modified_fields,
    )
    return alert


@router.post("/{alert_id}/modify")
async def modify_alert(alert_id: str, modification: AlertModification):
    """Apply an explicit forecaster edit and retain an auditable change record."""
    alert = _alert_or_404(alert_id)
    if alert["status"] not in {*_REVIEWABLE_STATUSES, "approved"}:
        raise HTTPException(status_code=400, detail=f"Alert cannot be modified in status: {alert['status']}")

    previous_status = alert["status"]
    changed = _apply_modification(alert, modification)
    # An amended approved warning must be checked and authorised again.
    if previous_status == "approved":
        alert["status"] = "pending_review"
        alert["sign_off"] = None
        alert.pop("approved_by", None)
        alert.pop("approved_at", None)
    alert["updated_at"] = _iso_now()
    _append_review(
        alert,
        action="modified",
        previous_status=previous_status,
        modified_fields=changed,
    )
    return alert


@router.post("/{alert_id}/verification")
async def add_verification_note(alert_id: str, verification: VerificationNote):
    """Append a forecaster evidence-check note without changing warning state."""
    alert = _alert_or_404(alert_id)
    record = {
        "id": str(uuid4()),
        "note": verification.note,
        "forecaster_name": verification.forecaster_name,
        "recorded_at": _iso_now(),
    }
    alert.setdefault("verification_notes", []).append(record)
    alert["updated_at"] = _iso_now()
    return {"alert_id": alert_id, "verification_note": record, "alert": alert}


@router.post("/{alert_id}/signoff")
async def sign_off_alert(alert_id: str, sign_off: AlertSignOff):
    """Digitally sign off and approve a forecaster-reviewed warning."""
    alert = _alert_or_404(alert_id)
    if alert["status"] not in {*_REVIEWABLE_STATUSES, "approved"}:
        raise HTTPException(status_code=400, detail=f"Alert cannot be signed off in status: {alert['status']}")

    previous_status = alert["status"]
    alert["sign_off"] = _make_sign_off(alert, sign_off)
    alert["status"] = "approved"
    alert["approved_by"] = sign_off.forecaster_name
    alert["approved_at"] = alert["sign_off"]["signed_at"]
    alert["updated_at"] = _iso_now()
    _append_review(
        alert,
        action="approved",
        verification_notes=sign_off.verification_notes,
        reviewer_name=sign_off.forecaster_name,
        reviewer_designation=sign_off.designation,
        previous_status=previous_status,
    )
    return alert


@router.post("/{alert_id}/broadcast")
async def broadcast_alert(alert_id: str, request: BroadcastRequest):
    """Simulate approved CAP dissemination to NDMA/GSDMA/SMS/WhatsApp channels."""
    alert = _alert_or_404(alert_id)
    if alert["status"] != "approved":
        raise HTTPException(
            status_code=400,
            detail="Only an approved alert can be broadcast. Review or sign off the alert first.",
        )

    receipt = _broadcast_receipt(alert, request)
    alert.setdefault("broadcasts", []).append(receipt)
    alert["last_broadcast_at"] = receipt["dispatched_at"]
    alert["broadcast_status"] = receipt["status"]
    alert["updated_at"] = _iso_now()
    return {"alert_id": alert_id, "broadcast": receipt, "alert": alert}


def auto_generate_alert(storm: dict[str, Any], risk: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Synchronously create a high-risk draft for use inside the async pipeline.

    This function intentionally does *not* call ``run_until_complete``.  The
    pipeline in ``main.py`` already owns the event loop, and the old implementation
    therefore raised ``RuntimeError: This event loop is already running``.
    """
    risk_level = str(risk.get("risk_level", "")).lower()
    if risk_level not in {"high", "severe"}:
        return None

    if float(risk.get("confidence_score", 0.0)) < 0.55:
        return None

    cell_id = str(storm.get("cell_id", "Unknown"))
    for existing in _alerts.values():
        if (
            existing.get("status") in _REVIEWABLE_STATUSES
            and cell_id in existing.get("storm_cell_ids", [])
        ):
            return None

    thunderstorm_probability = float(risk.get("thunderstorm_probability", 0.0))
    lightning_probability = float(risk.get("lightning_probability", 0.0))
    alert = AlertCreate(
        title=f"Thunderstorm Warning - {cell_id}",
        description=(
            f"Storm cell {cell_id} detected with {risk_level.upper()} risk. "
            f"Moving {float(risk.get('direction_deg', storm.get('movement_direction_deg', 0))):.0f}° "
            f"at {float(risk.get('speed_kmh', storm.get('movement_speed_kmh', 0))):.0f} km/h. "
            f"Thunderstorm probability: {thunderstorm_probability:.0%}. "
            f"Lightning probability: {lightning_probability:.0%}."
        ),
        risk_level=risk_level,
        storm_cell_ids=[cell_id] if cell_id else [],
        evidence={
            "thunderstorm_probability": thunderstorm_probability,
            "lightning_probability": lightning_probability,
            "intensity": risk.get("intensity", storm.get("intensity")),
            "speed_kmh": risk.get("speed_kmh", storm.get("movement_speed_kmh")),
            "trend": risk.get("trend", storm.get("trend")),
        },
    )
    return _create_alert_payload(alert)
