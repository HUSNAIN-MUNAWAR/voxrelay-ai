from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db import (
    Alert,
    Appointment,
    AuditEvent,
    CallEvent,
    CallSession,
    ExtractedEntity,
    FollowUpTask,
    Lead,
    QualityEvaluation,
    TranscriptSegment,
)
from app.services.integrations import enqueue_mock_crm_sync
from app.services.routing import evaluate_routing
from app.services.scenarios import SCENARIOS, Scenario

DEFAULT_ORG = "org-northstar"


PII_FIELDS = {"name": "identity", "phone": "phone", "email": "email", "location": "location"}


def event_payload(call: CallSession, raw: dict[str, Any], index: int) -> dict[str, Any]:
    event_type = raw.get("type", "unknown")
    trace_id = call.metadata_json.get("trace_id") or f"trace-{call.id}"
    occurred_at = datetime.utcnow().isoformat() + "Z"
    # Phase 3 envelope keeps legacy fields (`type`, `state`, etc.) for older clients while
    # exposing an SDK/webhook-ready event contract.
    return {
        "event_id": f"evt-{call.id}-{index:04d}",
        "event_type": event_type,
        "type": event_type,
        "sequence": index,
        "occurred_at": occurred_at,
        "organization_id": call.organization_id,
        "call_id": call.id,
        "trace_id": trace_id,
        "schema_version": "2026-07.phase3",
        "payload": raw,
        **raw,
    }


def _append_event(db: Session, call: CallSession, raw: dict[str, Any]) -> None:
    db.add(
        CallEvent(
            id=f"call-event-{uuid4().hex[:12]}",
            organization_id=call.organization_id,
            call_id=call.id,
            event_type=raw.get("type", "unknown"),
            state=raw.get("state"),
            payload=raw,
            occurred_at=datetime.utcnow(),
        )
    )


def create_simulated_call(
    db: Session,
    scenario_key: str,
    agent_id: str | None = None,
    organization_id: str = DEFAULT_ORG,
    actor: str = "demo.operator",
) -> CallSession:
    scenario = SCENARIOS.get(scenario_key, SCENARIOS["clinic_booking"])
    call_id = f"call-{uuid4().hex[:12]}"
    call = CallSession(
        id=call_id,
        organization_id=organization_id,
        agent_id=agent_id or scenario.agent_id,
        scenario=scenario.key,
        caller_name=scenario.caller_name,
        caller_phone=scenario.caller_phone,
        status="queued",
        outcome="in_progress",
        consent_state="pending",
        metadata_json={
            "synthetic": True,
            "scenario_label": scenario.label,
            "provider_mode": "deterministic_local",
            "trace_id": f"trace-{call_id}",
        },
    )
    db.add(call)
    _append_event(
        db,
        call,
        {"type": "state_changed", "state": "queued", "note": "Local deterministic call created"},
    )
    db.add(
        AuditEvent(
            id=f"audit-{uuid4().hex[:10]}",
            organization_id=organization_id,
            actor=actor,
            action="simulation.created",
            entity_type="call",
            entity_id=call_id,
            detail={"scenario": scenario.key, "synthetic": True},
        )
    )
    db.commit()
    db.refresh(call)
    return call


def _persist_entities(db: Session, call: CallSession, scenario: Scenario) -> None:
    for field, value in scenario.lead.items():
        if field not in {
            "name",
            "phone",
            "email",
            "service_type",
            "urgency",
            "location",
            "preferred_time",
        }:
            continue
        db.add(
            ExtractedEntity(
                id=f"entity-{uuid4().hex[:12]}",
                organization_id=call.organization_id,
                call_id=call.id,
                field_name=field,
                value=str(value),
                confidence=0.95 if field not in {"email", "preferred_time"} else 0.91,
                source_segment_id=None,
                validation_state="rule_assisted",
                pii_classification=PII_FIELDS.get(field, "none"),
                crm_mapping_status="mapped"
                if field in {"name", "phone", "email", "service_type"}
                else "not_required",
            )
        )


def persist_completion(db: Session, call: CallSession, scenario: Scenario) -> None:
    if db.query(Lead).filter(Lead.call_id == call.id).first():
        return
    lead_data = scenario.lead
    lead = Lead(
        id=f"lead-{uuid4().hex[:12]}",
        organization_id=call.organization_id,
        call_id=call.id,
        name=lead_data["name"],
        phone=lead_data["phone"],
        email=lead_data.get("email", ""),
        service_type=lead_data["service_type"],
        urgency=lead_data["urgency"],
        location=lead_data.get("location", ""),
        status=lead_data["status"],
        score=lead_data["score"],
        owner=lead_data["owner"],
        tags=lead_data["tags"],
        fields_json={"preferred_time": lead_data.get("preferred_time", ""), "synthetic": True},
    )
    db.add(lead)
    _persist_entities(db, call, scenario)

    if scenario.outcome == "booked":
        start = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(
            days=1, hours=10
        )
        db.add(
            Appointment(
                id=f"apt-{uuid4().hex[:12]}",
                organization_id=call.organization_id,
                lead_id=lead.id,
                agent_id=call.agent_id,
                title=f"{lead.name} — primary care intake",
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status="confirmed",
                assignee="Downtown Clinic Intake",
                provider="mock_local_calendar",
            )
        )
    q = scenario.quality
    db.add(
        QualityEvaluation(
            id=f"qe-{uuid4().hex[:12]}",
            call_id=call.id,
            quality_score=q["score"],
            transcript_completeness=q["completeness"],
            hallucination_risk=q["hallucination_risk"],
            policy_risk=q["policy_risk"],
            latency_ms=q["latency_ms"],
            sentiment_trend=q["sentiment"],
            findings=q["findings"],
        )
    )
    call.status = "completed" if scenario.outcome != "needs_review" else "wrapping_up"
    call.outcome = scenario.outcome
    call.duration_seconds = max(48, len(scenario.events) * 8)
    call.lead_score = lead_data["score"]
    call.quality_score = q["score"]
    call.consent_state = (
        "granted"
        if scenario.key not in {"plumbing_emergency", "low_confidence"}
        else "not_captured"
    )
    call.escalation_level = (
        "emergency"
        if scenario.outcome == "escalated"
        else ("human_review" if scenario.outcome in {"needs_review", "transferred"} else "none")
    )

    route_context = {
        "urgency": lead_data.get("urgency"),
        "confidence": 0.52 if scenario.key == "low_confidence" else 0.96,
        "booking_failed": False,
        "restricted_topic": scenario.key == "insurance_claim",
        "sentiment_risk": scenario.key == "plumbing_emergency",
    }
    decision = evaluate_routing(db, call.organization_id, route_context)
    if decision.matched:
        db.add(
            AuditEvent(
                id=f"audit-{uuid4().hex[:10]}",
                organization_id=call.organization_id,
                actor="voxrelay.routing_engine",
                action="routing.rule_evaluated",
                entity_type="call",
                entity_id=call.id,
                detail={
                    "rule_id": decision.rule_id,
                    "destination": decision.destination,
                    "synthetic": True,
                },
            )
        )
    if scenario.outcome in {"escalated", "needs_review", "transferred"}:
        db.add(
            Alert(
                id=f"alert-{uuid4().hex[:12]}",
                organization_id=call.organization_id,
                category="emergency_detected"
                if scenario.outcome == "escalated"
                else "human_review_required",
                severity="critical" if scenario.outcome == "escalated" else "medium",
                title="Emergency escalation detected"
                if scenario.outcome == "escalated"
                else "Call requires human review",
                detail="Created by deterministic local simulation. No external notification was sent.",
                status="open",
                entity_type="call",
                entity_id=call.id,
                assignee=decision.destination if decision.matched else "Human Review Queue",
            )
        )
        db.add(
            FollowUpTask(
                id=f"task-{uuid4().hex[:12]}",
                organization_id=call.organization_id,
                lead_id=lead.id,
                call_id=call.id,
                task_type="emergency_follow_up"
                if scenario.outcome == "escalated"
                else "review_transcript",
                title="Review deterministic call outcome",
                assignee=decision.destination if decision.matched else "Human Review Queue",
                due_at=datetime.utcnow() + timedelta(minutes=10),
                priority="critical" if scenario.outcome == "escalated" else "high",
                status="open",
            )
        )
    enqueue_mock_crm_sync(
        db,
        call.organization_id,
        lead,
        idempotency_key=f"call-{call.id}-crm-sync",
        simulate_failure=scenario.key == "insurance_claim",
    )
    _append_event(
        db,
        call,
        {"type": "state_changed", "state": "completed", "note": "Call completed and persisted"},
    )
    db.add(
        AuditEvent(
            id=f"audit-{uuid4().hex[:10]}",
            organization_id=call.organization_id,
            actor="voxrelay.simulator",
            action="call.completed",
            entity_type="call",
            entity_id=call.id,
            detail={"outcome": call.outcome, "synthetic": True},
        )
    )
    db.commit()


async def stream_scenario(db: Session, call: CallSession):
    scenario = SCENARIOS.get(call.scenario, SCENARIOS["clinic_booking"])
    call.status = "ringing"
    _append_event(
        db,
        call,
        {"type": "state_changed", "state": "ringing", "note": "Local simulation is ringing"},
    )
    db.commit()
    for index, raw in enumerate(scenario.events):
        await asyncio.sleep(0.30 if raw["type"] == "transcript" else 0.16)
        if index == 0:
            call.status = "connected"
        if raw["type"] == "state_changed":
            call.status = raw.get("state", "connected")
        if raw["type"] == "transcript":
            segment = TranscriptSegment(
                id=f"seg-{uuid4().hex[:12]}",
                call_id=call.id,
                speaker=raw["speaker"],
                text=raw["text"],
                confidence=raw.get("confidence", 0.95),
                offset_ms=index * 1350,
                pii_redacted=False,
            )
            db.add(segment)
        if raw["type"] == "field_extracted":
            db.add(
                ExtractedEntity(
                    id=f"entity-{uuid4().hex[:12]}",
                    organization_id=call.organization_id,
                    call_id=call.id,
                    field_name=raw["field"],
                    value=str(raw["value"]),
                    confidence=float(raw.get("confidence", 0.85)),
                    source_segment_id=None,
                    validation_state="rule_assisted",
                    pii_classification=PII_FIELDS.get(raw["field"], "none"),
                    crm_mapping_status="pending",
                )
            )
        _append_event(db, call, raw)
        if raw["type"] == "completed":
            persist_completion(db, call, scenario)
        else:
            db.commit()
        yield event_payload(call, raw, index)
