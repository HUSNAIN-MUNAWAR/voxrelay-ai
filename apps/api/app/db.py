from __future__ import annotations

from collections.abc import Generator
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="demo")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="viewer")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OrganizationMembership(Base, TimestampMixin):
    __tablename__ = "organization_memberships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RefreshSession(Base, TimestampMixin):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class VoiceAgent(Base, TimestampMixin):
    __tablename__ = "voice_agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="published")
    use_case: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en-US")
    voice: Mapped[str] = mapped_column(String(80), default="Aurora")
    version: Mapped[int] = mapped_column(Integer, default=1)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentVersion(Base, TimestampMixin):
    __tablename__ = "agent_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("voice_agents.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    release_notes: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    evaluation_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    release_gates: Mapped[dict] = mapped_column(JSON, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentReleaseApproval(Base, TimestampMixin):
    __tablename__ = "agent_release_approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    agent_version_id: Mapped[str] = mapped_column(ForeignKey("agent_versions.id"), nullable=False)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")


class EvaluationSuite(Base, TimestampMixin):
    __tablename__ = "evaluation_suites"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    use_case: Mapped[str] = mapped_column(String(120), nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(40), default="v1")
    cases: Mapped[list] = mapped_column(JSON, default=list)


class EvaluationRun(Base, TimestampMixin):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    suite_id: Mapped[str] = mapped_column(ForeignKey("evaluation_suites.id"), nullable=False)
    agent_version_id: Mapped[str] = mapped_column(ForeignKey("agent_versions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    pass_rate: Mapped[float] = mapped_column(Float, default=0)
    critical_failures: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)


class CallSession(Base, TimestampMixin):
    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("voice_agents.id"), nullable=False)
    scenario: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="inbound")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    caller_name: Mapped[str] = mapped_column(String(150), default="Synthetic caller")
    caller_phone: Mapped[str] = mapped_column(String(50), default="+1 (555) 010-0000")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(60), default="in_progress")
    lead_score: Mapped[float] = mapped_column(Float, default=0)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    consent_state: Mapped[str] = mapped_column(String(40), default="pending")
    escalation_level: Mapped[str] = mapped_column(String(40), default="none")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class CallEvent(Base, TimestampMixin):
    __tablename__ = "call_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str | None] = mapped_column(String(60), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CallQueue(Base, TimestampMixin):
    __tablename__ = "call_queues"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    service_type: Mapped[str] = mapped_column(String(120), default="general")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    sla_seconds: Mapped[int] = mapped_column(Integer, default=120)
    business_hours: Mapped[str] = mapped_column(String(160), default="Mon-Fri 08:00-18:00")
    overflow_policy: Mapped[str] = mapped_column(String(160), default="Create callback task")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class QueueEvent(Base, TimestampMixin):
    __tablename__ = "queue_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    queue_id: Mapped[str] = mapped_column(ForeignKey("call_queues.id"), nullable=False)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("call_sessions.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    wait_seconds: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class TranscriptSegment(Base, TimestampMixin):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.id"), nullable=False)
    speaker: Mapped[str] = mapped_column(String(30), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.95)
    offset_ms: Mapped[int] = mapped_column(Integer, default=0)
    pii_redacted: Mapped[bool] = mapped_column(Boolean, default=False)


class ExtractedEntity(Base, TimestampMixin):
    __tablename__ = "extracted_entities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    source_segment_id: Mapped[str | None] = mapped_column(ForeignKey("transcript_segments.id"), nullable=True)
    validation_state: Mapped[str] = mapped_column(String(40), default="rule_assisted")
    reviewer_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    pii_classification: Mapped[str] = mapped_column(String(60), default="none")
    crm_mapping_status: Mapped[str] = mapped_column(String(40), default="pending")


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("call_sessions.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(60), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    service_type: Mapped[str] = mapped_column(String(150), default="General inquiry")
    urgency: Mapped[str] = mapped_column(String(40), default="normal")
    location: Mapped[str] = mapped_column(String(180), default="")
    status: Mapped[str] = mapped_column(String(50), default="new")
    score: Mapped[float] = mapped_column(Float, default=0)
    owner: Mapped[str] = mapped_column(String(120), default="Unassigned")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    source_campaign: Mapped[str] = mapped_column(String(120), default="Inbound voice")
    crm_sync_status: Mapped[str] = mapped_column(String(50), default="queued")
    fields_json: Mapped[dict] = mapped_column(JSON, default=dict)


class FollowUpTask(Base, TimestampMixin):
    __tablename__ = "follow_up_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("call_sessions.id"), nullable=True)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    assignee: Mapped[str] = mapped_column(String(150), default="Unassigned")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    priority: Mapped[str] = mapped_column(String(30), default="normal")
    status: Mapped[str] = mapped_column(String(30), default="open")
    completion_evidence: Mapped[str] = mapped_column(Text, default="")


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("voice_agents.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="confirmed")
    assignee: Mapped[str] = mapped_column(String(120), default="Intake Team")
    provider: Mapped[str] = mapped_column(String(80), default="mock_local_calendar")


class BookingAttempt(Base, TimestampMixin):
    __tablename__ = "booking_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey("appointments.id"), nullable=True)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("call_sessions.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="mock_local_calendar")
    reason: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(150), nullable=False)


class QualityEvaluation(Base, TimestampMixin):
    __tablename__ = "quality_evaluations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.id"), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0)
    transcript_completeness: Mapped[float] = mapped_column(Float, default=0)
    hallucination_risk: Mapped[str] = mapped_column(String(30), default="low")
    policy_risk: Mapped[str] = mapped_column(String(30), default="low")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_trend: Mapped[str] = mapped_column(String(50), default="stable")
    findings: Mapped[list] = mapped_column(JSON, default=list)


class QualityRubric(Base, TimestampMixin):
    __tablename__ = "quality_rubrics"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    dimensions: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReviewerFeedback(Base, TimestampMixin):
    __tablename__ = "reviewer_feedback"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_sessions.id"), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    policy_violation: Mapped[bool] = mapped_column(Boolean, default=False)
    training_example: Mapped[bool] = mapped_column(Boolean, default=False)
    second_review_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class CoachingTask(Base, TimestampMixin):
    __tablename__ = "coaching_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    agent_version_id: Mapped[str | None] = mapped_column(ForeignKey("agent_versions.id"), nullable=True)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("call_sessions.id"), nullable=True)
    owner: Mapped[str] = mapped_column(String(150), default="Quality Team")
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    remediation: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")


class HandoffTeam(Base, TimestampMixin):
    __tablename__ = "handoff_teams"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    destination: Mapped[str] = mapped_column(String(160), nullable=False)
    availability: Mapped[str] = mapped_column(String(100), default="24/7")


class RoutingRule(Base, TimestampMixin):
    __tablename__ = "routing_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    condition: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    destination_type: Mapped[str] = mapped_column(String(60), nullable=False)
    destination: Mapped[str] = mapped_column(String(160), nullable=False)
    fallback: Mapped[str] = mapped_column(String(160), default="Create callback task")
    notification: Mapped[str] = mapped_column(String(160), default="in_app")
    audit_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class IntegrationJob(Base, TimestampMixin):
    __tablename__ = "integration_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="not_configured")
    environment: Mapped[str] = mapped_column(String(40), default="demo")
    credential_state: Mapped[str] = mapped_column(String(60), default="not_configured")
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    retry_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)


class WebhookDelivery(Base, TimestampMixin):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload_preview: Mapped[str] = mapped_column(Text, default="")
    failure_reason: Mapped[str] = mapped_column(Text, default="")


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="medium")
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="open")
    entity_type: Mapped[str] = mapped_column(String(80), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    assignee: Mapped[str] = mapped_column(String(150), default="")


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery: Mapped[str] = mapped_column(String(40), default="in_app")


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    date_range: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(120), nullable=False)
    data_freshness: Mapped[str] = mapped_column(String(100), default="synthetic demo data")
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    export_id: Mapped[str] = mapped_column(String(100), nullable=False)


class ScheduledReport(Base, TimestampMixin):
    __tablename__ = "scheduled_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(120), nullable=False)
    cadence: Mapped[str] = mapped_column(String(50), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    destination: Mapped[str] = mapped_column(String(160), default="in_app")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RetentionPolicy(Base, TimestampMixin):
    __tablename__ = "retention_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(80), default="delete_after_retention")
    legal_hold_enabled: Mapped[bool] = mapped_column(Boolean, default=False)


class DataDeletionRequest(Base, TimestampMixin):
    __tablename__ = "data_deletion_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    requester_reference: Mapped[str] = mapped_column(String(150), nullable=False)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    reason: Mapped[str] = mapped_column(Text, default="")


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    actor: Mapped[str] = mapped_column(String(150), nullable=False)
    action: Mapped[str] = mapped_column(String(150), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
