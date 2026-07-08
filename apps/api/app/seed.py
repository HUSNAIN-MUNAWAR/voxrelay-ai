from __future__ import annotations

from datetime import datetime, timedelta
from random import Random
from typing import Any

from sqlalchemy.orm import Session

from app.db import (
    AgentReleaseApproval,
    AgentVersion,
    Alert,
    Appointment,
    AuditEvent,
    BookingAttempt,
    CallQueue,
    CallSession,
    CoachingTask,
    DataDeletionRequest,
    EvaluationRun,
    EvaluationSuite,
    ExtractedEntity,
    FollowUpTask,
    HandoffTeam,
    IntegrationJob,
    Lead,
    Notification,
    Organization,
    OrganizationMembership,
    ProviderConfig,
    QualityEvaluation,
    QualityRubric,
    Report,
    RetentionPolicy,
    RoutingRule,
    ScheduledReport,
    TranscriptSegment,
    User,
    VoiceAgent,
    WebhookDelivery,
)
from app.security import ROLE_PERMISSIONS, hash_password

RNG = Random(20260707)

ORGS = [
    ("org-northstar", "Northstar Property Group", "northstar-property"),
    ("org-carebridge", "CareBridge Clinics", "carebridge-clinics"),
    ("org-apex", "Apex Home Services", "apex-home-services"),
]

AGENTS = [
    ("agent-realestate", "org-northstar", "Aster — Buyer Concierge", "Real-estate lead qualification", "Aurora"),
    ("agent-clinic", "org-carebridge", "Mira — Patient Intake", "Clinic appointment booking", "Juniper"),
    ("agent-services", "org-apex", "Relay — Emergency Dispatch", "Home services intake", "Sol"),
    ("agent-property", "org-northstar", "Haven — Resident Support", "Property maintenance", "Willow"),
    ("agent-insurance", "org-carebridge", "Atlas — Claims Intake", "Insurance claim intake", "Nova"),
]

USERS = [
    ("user-demo-admin", "org-northstar", "admin@voxrelay.demo", "Demo Administrator", "organization_admin"),
    ("user-demo-ops", "org-carebridge", "ops@voxrelay.demo", "Operations Manager", "operations_manager"),
    ("user-demo-supervisor", "org-northstar", "supervisor@voxrelay.demo", "Supervisor", "supervisor"),
    ("user-demo-quality", "org-carebridge", "quality@voxrelay.demo", "Quality Reviewer", "quality_reviewer"),
    ("user-demo-scheduler", "org-carebridge", "scheduler@voxrelay.demo", "Scheduler", "scheduler"),
    ("user-demo-sales", "org-northstar", "sales@voxrelay.demo", "Sales Representative", "sales_representative"),
    ("user-demo-compliance", "org-apex", "compliance@voxrelay.demo", "Compliance Reviewer", "compliance_reviewer"),
    ("user-demo-viewer", "org-apex", "viewer@voxrelay.demo", "Viewer", "viewer"),
    ("user-demo-agentmanager", "org-carebridge", "agentmanager@voxrelay.demo", "Voice Agent Manager", "voice_agent_manager"),
]

CONFIG = {
    "greeting": "Thank you for calling. This call may be recorded for service quality.",
    "required_fields": ["name", "phone", "service_type", "urgency"],
    "restricted_topics": ["medical diagnosis", "coverage determination", "legal advice"],
    "business_hours": "Mon–Fri, 08:00–18:00",
    "handoff_destinations": ["Emergency Dispatch", "Operations Queue", "Human Review"],
    "consent_required": True,
    "flow": ["Greeting", "Intent", "Qualification", "Booking / Handoff", "Summary", "End"],
}


def ensure(db: Session, model: type[Any], identity: str, **fields: Any) -> Any:
    instance = db.get(model, identity)
    if instance is None:
        instance = model(id=identity, **fields)
        db.add(instance)
    return instance


def synthetic_cases() -> list[dict[str, Any]]:
    topics = [
        ("real_estate", "real-estate inquiry", "qualified", "none"),
        ("clinic_booking", "clinic booking", "booked", "none"),
        ("plumbing_emergency", "emergency plumbing", "escalated", "emergency"),
        ("property_maintenance", "property maintenance", "qualified", "none"),
        ("insurance_claim", "insurance intake", "transferred", "restricted_topic"),
        ("low_confidence", "low-confidence caller", "needs_review", "low_confidence"),
        ("consent_refusal", "consent refusal", "handoff", "consent"),
        ("booking_failure", "booking failure", "follow_up", "booking_failure"),
        ("incorrect_contact", "incorrect contact details", "needs_review", "validation"),
        ("after_hours", "after-hours request", "callback", "business_hours"),
        ("restricted_topic", "restricted-topic request", "handoff", "restricted_topic"),
        ("repeat_customer", "repeat customer", "qualified", "none"),
        ("interruption", "caller interruption", "qualified", "none"),
        ("human_handoff", "human handoff request", "transferred", "handoff"),
        ("crm_failure", "CRM sync failure", "qualified", "crm_failure"),
        ("multiple_appointments", "multiple appointments", "needs_review", "booking_policy"),
        ("sentiment_risk", "sentiment escalation", "escalated", "sentiment"),
        ("language_route", "language routing", "transferred", "language"),
        ("vip_route", "VIP routing", "transferred", "vip"),
        ("no_answer", "no-answer callback", "callback", "no_answer"),
    ]
    cases: list[dict[str, Any]] = []
    for index in range(40):
        scenario, label, outcome, policy = topics[index % len(topics)]
        cases.append(
            {
                "id": f"eval-case-{index + 1:02d}",
                "scenario": scenario,
                "label": label,
                "expected_entities": ["name", "service_type", "urgency"],
                "expected_outcome": outcome,
                "expected_policy": policy,
                "synthetic": True,
            }
        )
    return cases


def seed_demo(db: Session) -> None:
    """Idempotently populate the three-tenant synthetic demo workspace."""
    now = datetime.utcnow()
    for org_id, name, slug in ORGS:
        ensure(
            db,
            Organization,
            org_id,
            name=name,
            slug=slug,
            plan="synthetic-demo",
            settings={"synthetic": True, "pii_retention_days": 30, "timezone": "America/New_York"},
        )

    # Demo credentials are intentionally local-only. Passwords are stored as bcrypt hashes.
    for user_id, org_id, email, name, role in USERS:
        user = db.get(User, user_id)
        if user is None:
            user = User(
                id=user_id,
                organization_id=org_id,
                email=email,
                name=name,
                role=role,
                password_hash=hash_password("DemoPass123!"),
                is_active=True,
            )
            db.add(user)
        elif user.password_hash.startswith("demo:"):
            user.password_hash = hash_password("DemoPass123!")
            user.role = role
            user.organization_id = org_id
        memberships = [(org_id, role)]
        if user_id == "user-demo-admin":
            memberships = [(o[0], "organization_admin") for o in ORGS]
        for workspace_id, workspace_role in memberships:
            ensure(
                db,
                OrganizationMembership,
                f"membership-{user_id}-{workspace_id}",
                organization_id=workspace_id,
                user_id=user_id,
                role=workspace_role,
                permissions=sorted(ROLE_PERMISSIONS.get(workspace_role, set())),
                is_active=True,
            )

    for agent_id, org_id, name, use_case, voice in AGENTS:
        ensure(
            db,
            VoiceAgent,
            agent_id,
            organization_id=org_id,
            name=name,
            status="active",
            use_case=use_case,
            language="en-US",
            voice=voice,
            version=3,
            config=CONFIG | {"use_case": use_case},
        )
        for version_number, status in [(3, "active"), (4, "approved")]:
            version_id = f"agent-version-{agent_id}-{version_number}"
            config = CONFIG | {
                "use_case": use_case,
                "version": version_number,
                "booking_policy": "confirm_only_after_provider_success",
                "routing_policy": "policy_driven",
            }
            ensure(
                db,
                AgentVersion,
                version_id,
                organization_id=org_id,
                agent_id=agent_id,
                version_number=version_number,
                status=status,
                config_snapshot=config,
                release_notes=("Baseline active synthetic demo version" if version_number == 3 else "Improves explicit booking-failure fallback."),
                owner_id="user-demo-agentmanager" if org_id == "org-carebridge" else "user-demo-admin",
                evaluation_summary={"pass_rate": 97.5, "critical_failures": 0, "synthetic": True},
                release_gates={
                    "required_scenarios_passed": True,
                    "emergency_behavior_valid": True,
                    "consent_flow_valid": True,
                    "restricted_topic_policy_valid": True,
                    "required_extraction_valid": True,
                    "critical_failures": 0,
                    "approval_granted": version_number == 4,
                },
                activated_at=now - timedelta(days=20) if version_number == 3 else None,
            )
        ensure(
            db,
            AgentReleaseApproval,
            f"approval-{agent_id}-4",
            organization_id=org_id,
            agent_version_id=f"agent-version-{agent_id}-4",
            approver_id="user-demo-admin",
            decision="approved",
            note="Synthetic Phase 2 release gate approval.",
        )

    teams = [
        ("team-dispatch", "org-apex", "Emergency Dispatch", "+1 (555) 010-9110", "24/7"),
        ("team-clinic", "org-carebridge", "Clinic Intake", "intake-queue", "Mon–Fri 08:00–18:00"),
        ("team-review", "org-northstar", "Human Review Queue", "review-queue", "24/7"),
        ("team-sales", "org-northstar", "Property Sales", "sales-queue", "Mon–Sat 08:00–19:00"),
        ("team-claims", "org-carebridge", "Claims Intake", "claims-queue", "Mon–Fri 08:00–18:00"),
    ]
    for team_id, org_id, name, destination, availability in teams:
        ensure(
            db,
            HandoffTeam,
            team_id,
            organization_id=org_id,
            name=name,
            destination=destination,
            availability=availability,
        )

    queues = [
        ("queue-northstar-sales", "org-northstar", "Property Sales Queue", "real_estate", 2, 90),
        ("queue-northstar-review", "org-northstar", "Human Review Queue", "review", 1, 300),
        ("queue-carebridge-intake", "org-carebridge", "Clinic Intake Queue", "clinic", 2, 120),
        ("queue-apex-emergency", "org-apex", "Emergency Dispatch Queue", "emergency", 1, 30),
        ("queue-apex-services", "org-apex", "Service Operations Queue", "maintenance", 3, 180),
    ]
    for queue_id, org_id, name, service_type, priority, sla in queues:
        ensure(
            db,
            CallQueue,
            queue_id,
            organization_id=org_id,
            name=name,
            service_type=service_type,
            priority=priority,
            sla_seconds=sla,
            business_hours="Mon–Fri 08:00–18:00" if priority > 1 else "24/7",
            overflow_policy="Create callback task after SLA / route to fallback team",
            is_active=True,
        )

    routing_rules = [
        ("route-emergency", "org-apex", "Emergency escalation", {"urgency": "emergency"}, 1, "human_team", "Emergency Dispatch", "Create incident task"),
        ("route-low-confidence", "org-northstar", "Low-confidence review", {"confidence_below": 0.65}, 2, "queue", "Human Review Queue", "Create callback task"),
        ("route-clinic-booking", "org-carebridge", "Clinic booking failure", {"booking_failed": True}, 3, "human_team", "Clinic Intake", "Create scheduler task"),
        ("route-insurance-restricted", "org-carebridge", "Restricted claims guidance", {"restricted_topic": True}, 2, "human_team", "Claims Intake", "Escalate to compliance"),
        ("route-after-hours", "org-northstar", "After-hours callback", {"business_hours": False}, 5, "callback", "Next business day callback", "Notify sales"),
        ("route-language", "org-northstar", "Language routing", {"language": "es"}, 4, "queue", "Bilingual Support", "Create callback task"),
        ("route-vip", "org-northstar", "VIP routing placeholder", {"vip": True}, 1, "human_team", "Property Sales", "Notify supervisor"),
        ("route-sentiment", "org-apex", "Sentiment-risk escalation", {"sentiment_risk": True}, 2, "queue", "Emergency Dispatch Queue", "Notify supervisor"),
        ("route-crm-failure", "org-carebridge", "CRM failure recovery", {"crm_failed": True}, 5, "queue", "Clinic Intake Queue", "Create CRM retry job"),
        ("route-no-answer", "org-northstar", "No-answer callback", {"no_answer": True}, 8, "callback", "Sales follow-up", "Create callback task"),
    ]
    for rule_id, org_id, name, condition, priority, destination_type, destination, fallback in routing_rules:
        ensure(
            db,
            RoutingRule,
            rule_id,
            organization_id=org_id,
            name=name,
            condition=condition,
            priority=priority,
            destination_type=destination_type,
            destination=destination,
            fallback=fallback,
            notification="in_app",
            audit_required=True,
            is_active=True,
        )

    names = [
        "Amelia Grant", "Noah Kim", "Priya Shah", "Lucas Reed", "Ibrahim Khan", "Sofia Flores",
        "Ethan Ross", "Ava Price", "Theo Mason", "Mina Park",
    ]
    services = [
        "Buyer consultation", "Primary care intake", "Emergency plumbing", "Heating maintenance",
        "Auto claim intake", "Roof inspection",
    ]
    outcomes = ["qualified", "booked", "transferred", "escalated", "needs_review", "abandoned"]
    statuses = {
        "qualified": "qualified",
        "booked": "appointment_booked",
        "transferred": "follow_up_required",
        "escalated": "human_review",
        "needs_review": "human_review",
        "abandoned": "disqualified",
    }
    for idx in range(240):
        agent_id, org_id, _, _, _ = AGENTS[idx % len(AGENTS)]
        outcome = outcomes[idx % len(outcomes)]
        name = f"{names[idx % len(names)]} {idx + 1}"
        call_id = f"call-seed-{idx:03d}"
        score = float(RNG.randint(18, 98))
        quality = float(RNG.randint(54, 98))
        created_at = now - timedelta(hours=idx * 2)
        ensure(
            db,
            CallSession,
            call_id,
            organization_id=org_id,
            agent_id=agent_id,
            scenario="seeded_synthetic",
            direction="inbound" if idx % 5 else "outbound",
            status="completed" if outcome != "abandoned" else "abandoned",
            caller_name=name,
            caller_phone=f"+1 (555) 01{idx % 10}-{1000 + idx:04d}",
            duration_seconds=RNG.randint(38, 680),
            outcome=outcome,
            lead_score=score,
            quality_score=quality,
            consent_state="granted" if idx % 7 else "not_captured",
            escalation_level="emergency" if outcome == "escalated" else ("human_review" if outcome in ["transferred", "needs_review"] else "none"),
            metadata_json={"synthetic": True, "campaign": "Website inbound" if idx % 2 else "Referral campaign"},
            created_at=created_at,
        )
        lead_id = f"lead-seed-{idx:03d}"
        ensure(
            db,
            Lead,
            lead_id,
            organization_id=org_id,
            call_id=call_id,
            name=name,
            phone=f"+1 (555) 01{idx % 10}-{1000 + idx:04d}",
            email=f"lead{idx}@example.test",
            service_type=services[idx % len(services)],
            urgency="emergency" if outcome == "escalated" else ("high" if idx % 4 == 0 else "normal"),
            location=["Riverside", "Downtown", "Oakview", "Eastbridge"][idx % 4],
            status=statuses[outcome],
            score=score,
            owner=["Acquisitions Team", "Clinic Intake", "Operations Queue", "Human Review"][idx % 4],
            tags=["synthetic", outcome],
            source_campaign="Website inbound" if idx % 2 else "Referral campaign",
            crm_sync_status="synced" if idx % 3 else "retrying",
            fields_json={"preferred_time": "Weekday afternoon", "synthetic": True},
            created_at=created_at,
        )
        ensure(
            db,
            QualityEvaluation,
            f"qe-seed-{idx:03d}",
            call_id=call_id,
            quality_score=quality,
            transcript_completeness=float(RNG.randint(45, 100)),
            hallucination_risk="medium" if idx % 17 == 0 else "low",
            policy_risk="medium" if outcome in ["transferred", "needs_review"] else "low",
            latency_ms=RNG.randint(420, 1400),
            sentiment_trend="improving" if idx % 3 else "stable",
            findings=["Synthetic evaluation record.", "Review required when policy risk is medium."],
            created_at=created_at,
        )
        if outcome == "booked" or idx % 7 == 0:
            start = now + timedelta(days=(idx % 21) - 7, hours=9 + (idx % 7))
            ensure(
                db,
                Appointment,
                f"apt-seed-{idx:03d}",
                organization_id=org_id,
                lead_id=lead_id,
                agent_id=agent_id,
                title=f"{name} — {services[idx % len(services)]}",
                start_time=start,
                end_time=start + timedelta(minutes=30),
                status="confirmed" if idx % 4 else "pending",
                assignee=["Clinic Intake", "Acquisitions Team", "Field Services"][idx % 3],
                provider="mock_local_calendar",
                created_at=created_at,
            )
            ensure(
                db,
                BookingAttempt,
                f"booking-seed-{idx:03d}",
                organization_id=org_id,
                appointment_id=f"apt-seed-{idx:03d}",
                call_id=call_id,
                status="confirmed" if idx % 4 else "pending",
                provider="mock_local_calendar",
                reason="Synthetic booking event.",
                idempotency_key=f"seed-booking-{idx:03d}",
                created_at=created_at,
            )
        for segment_index in range(3):
            segment_id = f"seg-seed-{idx:03d}-{segment_index}"
            speaker = "caller" if segment_index % 2 == 0 else "agent"
            ensure(
                db,
                TranscriptSegment,
                segment_id,
                call_id=call_id,
                speaker=speaker,
                text=f"Synthetic {speaker} transcript segment {segment_index + 1} for operational review, record {idx + 1}.",
                confidence=round(0.62 + (idx % 35) / 100, 2),
                offset_ms=segment_index * 4200,
                created_at=created_at,
            )
        if idx < 100:
            ensure(
                db,
                ExtractedEntity,
                f"entity-seed-{idx:03d}",
                organization_id=org_id,
                call_id=call_id,
                field_name="service_type",
                value=services[idx % len(services)],
                confidence=0.91,
                source_segment_id=f"seg-seed-{idx:03d}-0",
                validation_state="rule_assisted",
                reviewer_override=None,
                pii_classification="none",
                crm_mapping_status="mapped",
                created_at=created_at,
            )
        if idx < 35:
            ensure(
                db,
                FollowUpTask,
                f"task-seed-{idx:03d}",
                organization_id=org_id,
                lead_id=lead_id,
                call_id=call_id,
                appointment_id=f"apt-seed-{idx:03d}" if (outcome == "booked" or idx % 7 == 0) else None,
                task_type=["callback", "review_transcript", "verify_booking", "update_crm"][idx % 4],
                title=f"Synthetic follow-up for {name}",
                assignee=["Sales Representative", "Quality Reviewer", "Scheduler", "Operations Manager"][idx % 4],
                due_at=now + timedelta(hours=idx + 1),
                priority="high" if idx % 6 == 0 else "normal",
                status="open" if idx % 3 else "completed",
                completion_evidence="Synthetic seed evidence." if idx % 3 == 0 else "",
            )

    for org_id, _, _ in ORGS:
        ensure(
            db,
            QualityRubric,
            f"rubric-{org_id}-v1",
            organization_id=org_id,
            name="Voice operations quality rubric",
            version="v1",
            dimensions=[
                "consent captured", "extraction completeness", "booking correctness", "handoff correctness",
                "emergency routing", "restricted-topic compliance", "PII handling", "call close quality",
            ],
            is_active=True,
        )
        suite_id = f"suite-{org_id}-core"
        ensure(
            db,
            EvaluationSuite,
            suite_id,
            organization_id=org_id,
            name="Core governed voice scenarios",
            use_case="multi_use_case",
            rubric_version="v1",
            cases=synthetic_cases(),
        )
        agent = next(agent for agent in AGENTS if agent[1] == org_id)
        ensure(
            db,
            EvaluationRun,
            f"eval-run-{org_id}-seed",
            organization_id=org_id,
            suite_id=suite_id,
            agent_version_id=f"agent-version-{agent[0]}-4",
            status="completed",
            pass_rate=97.5,
            critical_failures=0,
            result_json={"passed": 39, "failed": 1, "synthetic": True, "note": "Rule-assisted demo evaluation."},
        )
        ensure(
            db,
            RetentionPolicy,
            f"retention-{org_id}-transcripts",
            organization_id=org_id,
            name="Transcript retention",
            resource_type="transcript",
            retention_days=90,
            action="delete_after_retention",
            legal_hold_enabled=False,
        )
        ensure(
            db,
            RetentionPolicy,
            f"retention-{org_id}-recording-metadata",
            organization_id=org_id,
            name="Recording metadata retention",
            resource_type="recording_metadata",
            retention_days=30,
            action="delete_after_retention",
            legal_hold_enabled=False,
        )
        ensure(
            db,
            ScheduledReport,
            f"schedule-{org_id}-weekly-quality",
            organization_id=org_id,
            report_type="Weekly Call Quality Report",
            cadence="weekly",
            next_run_at=now + timedelta(days=7),
            destination="in_app (simulated delivery)",
            is_active=True,
        )
        ensure(
            db,
            Report,
            f"report-{org_id}-weekly-quality",
            organization_id=org_id,
            report_type="Weekly Call Quality Report",
            title="Weekly Call Quality Report — Synthetic Preview",
            date_range="Last 7 days",
            generated_by="voxrelay.demo",
            data_freshness="Synthetic demo data, generated during seeding",
            content_json={"quality_score": 89.7, "policy_flags": 3, "booking_integrity": "confirmed", "synthetic": True},
            export_id=f"export-{org_id}-weekly-quality",
        )
        ensure(
            db,
            Notification,
            f"notification-{org_id}-release",
            organization_id=org_id,
            user_id=None,
            category="agent_release",
            title="Agent evaluation report is ready",
            body="Synthetic demo notification. No external delivery has occurred.",
            delivery="in_app",
        )
        ensure(
            db,
            DataDeletionRequest,
            f"deletion-{org_id}-seed",
            organization_id=org_id,
            requester_reference="synthetic-request-001",
            scope="Transcript metadata",
            status="pending_review",
            reason="Synthetic privacy workflow example.",
        )
        ensure(
            db,
            ProviderConfig,
            f"provider-{org_id}-local-sim",
            organization_id=org_id,
            provider_name="Local deterministic simulator",
            provider_type="telephony_orchestration",
            status="demo_provider",
            environment="demo",
            credential_state="not_required",
            last_health_check=now,
            last_success_at=now,
            failure_count=0,
            retry_policy={"max_attempts": 3, "backoff": "exponential"},
            settings_json={"fully_local": True, "synthetic": True},
        )
        for provider_type, provider_name in [
            ("stt", "Deepgram-compatible adapter"),
            ("tts", "ElevenLabs-compatible adapter"),
            ("crm", "HubSpot adapter"),
            ("calendar", "Google Calendar-compatible adapter"),
            ("webhook", "Generic webhook adapter"),
        ]:
            ensure(
                db,
                ProviderConfig,
                f"provider-{org_id}-{provider_type}",
                organization_id=org_id,
                provider_name=provider_name,
                provider_type=provider_type,
                status="not_configured",
                environment="demo",
                credential_state="not_configured",
                failure_count=0,
                retry_policy={"max_attempts": 3, "backoff": "exponential"},
                settings_json={"optional_adapter": True},
            )

    # Integration and review data that makes reliability and governance workflows demonstrable.
    for idx in range(15):
        org_id = ORGS[idx % len(ORGS)][0]
        lead_id = f"lead-seed-{idx:03d}"
        status = "failed" if idx % 5 == 0 else ("retrying" if idx % 4 == 0 else "succeeded")
        ensure(
            db,
            IntegrationJob,
            f"integration-seed-{idx:03d}",
            organization_id=org_id,
            job_type="crm_sync",
            provider="local_mock_crm",
            entity_type="lead",
            entity_id=lead_id,
            idempotency_key=f"seed-crm-{idx:03d}",
            status=status,
            attempts=3 if status == "failed" else 1,
            max_attempts=3,
            next_retry_at=now + timedelta(minutes=15) if status == "retrying" else None,
            last_error="Synthetic CRM adapter timeout" if status in {"failed", "retrying"} else "",
            payload={"lead_id": lead_id, "synthetic": True, "phone": "[REDACTED_PHONE]"},
        )
        ensure(
            db,
            WebhookDelivery,
            f"webhook-seed-{idx:03d}",
            organization_id=org_id,
            event_name="crm.sync_failed" if status == "failed" else "lead.created",
            destination="https://example.test/webhooks/voxrelay",
            status="retrying" if status in {"failed", "retrying"} else "delivered",
            attempts=3 if status == "failed" else 1,
            payload_preview='{"lead":"[REDACTED]","status":"synthetic"}',
            failure_reason="Synthetic delivery timeout" if status == "failed" else "",
        )
    for idx in range(18):
        org_id = ORGS[idx % len(ORGS)][0]
        severity = ["low", "medium", "high", "critical"][idx % 4]
        ensure(
            db,
            Alert,
            f"alert-seed-{idx:03d}",
            organization_id=org_id,
            category=["queue_threshold", "booking_failure", "crm_sync_failure", "policy_violation", "emergency_detected", "quality_drop"][idx % 6],
            severity=severity,
            title=["Queue SLA threshold exceeded", "Booking failed safely", "CRM mock delivery needs retry", "Policy review required", "Emergency escalation detected", "Quality score needs review"][idx % 6],
            detail="Synthetic demo alert. Evidence and remediation are available in the related workspace.",
            status="open" if idx % 3 else "acknowledged",
            entity_type="call",
            entity_id=f"call-seed-{idx:03d}",
            assignee="Supervisor" if severity in {"high", "critical"} else "Operations Manager",
        )
    for idx in range(12):
        org_id = ORGS[idx % len(ORGS)][0]
        agent = next(a for a in AGENTS if a[1] == org_id)
        ensure(
            db,
            CoachingTask,
            f"coaching-seed-{idx:03d}",
            organization_id=org_id,
            agent_version_id=f"agent-version-{agent[0]}-3",
            call_id=f"call-seed-{idx:03d}",
            owner="Quality Reviewer",
            title="Improve extraction confirmation behavior",
            remediation="Add a confirmation turn for phone number and preferred appointment time.",
            due_at=now + timedelta(days=idx + 1),
            status="open" if idx % 2 else "in_progress",
        )

    for idx in range(80):
        org_id = ORGS[idx % len(ORGS)][0]
        ensure(
            db,
            AuditEvent,
            f"audit-seed-{idx:03d}",
            organization_id=org_id,
            actor="voxrelay.system" if idx % 2 else "demo.operator",
            action=[
                "agent.release_approved", "call.reviewed", "routing.rule_evaluated", "lead.exported",
                "report.generated", "provider.health_checked", "workspace.switched", "crm.retry_requested",
            ][idx % 8],
            entity_type=["agent_version", "call", "routing_rule", "lead_export", "report", "provider", "workspace", "integration_job"][idx % 8],
            entity_id=f"entity-{idx:03d}",
            detail={"synthetic": True, "sequence": idx, "request_id": f"seed-{idx:03d}"},
            created_at=now - timedelta(hours=idx),
        )

    db.commit()


def reset_and_seed(db: Session) -> None:
    from app.db import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_demo(db)
