from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.db import (
    AgentReleaseApproval,
    AgentVersion,
    Alert,
    ApiKey,
    Appointment,
    AuditEvent,
    Base,
    BookingAttempt,
    CallEvent,
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
    ReviewerFeedback,
    RoutingRule,
    ScheduledReport,
    SessionLocal,
    TranscriptSegment,
    User,
    VoiceAgent,
    WebhookDelivery,
    engine,
    get_db,
)
from app.security import (
    Principal,
    create_access_token,
    create_refresh_session,
    get_principal,
    permission_set,
    require_permissions,
    revoke_refresh_session,
    rotate_refresh_session,
    verify_password,
)
from app.seed import seed_demo
from app.services.integrations import enqueue_mock_crm_sync, retry_mock_job
from app.services.redaction import redact_pii
from app.services.reporting import generate_report, minimal_pdf
from app.services.routing import evaluate_routing
from app.services.scenarios import SCENARIOS
from app.services.simulation import create_simulated_call, stream_scenario


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get("X-Request-ID", f"req-{uuid4().hex[:12]}")
        request.state.request_id = request_id
        client = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = self.requests[client]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute and request.url.path.startswith(settings.api_prefix):
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"X-Request-ID": request_id},
            )
        bucket.append(now)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response


app = FastAPI(
    title="VoxRelay AI API",
    version="3.0.0",
    description="Tenant-isolated, deterministic demo API for governed voice operations. External providers are optional adapters.",
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Db = Annotated[Session, Depends(get_db)]
Current = Annotated[Principal, Depends(get_principal)]


class LoginInput(BaseModel):
    email: str
    password: str


class RefreshInput(BaseModel):
    refresh_token: str


class LogoutInput(BaseModel):
    refresh_token: str


class WorkspaceInput(BaseModel):
    organization_id: str


class CreateAgentInput(BaseModel):
    name: str
    use_case: str
    language: str = "en-US"
    voice: str = "Aurora"
    config: dict[str, Any] = Field(default_factory=dict)


class UpdateAgentInput(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    status: str | None = None


class AgentVersionInput(BaseModel):
    release_notes: str = ""
    config_snapshot: dict[str, Any] | None = None


class ApprovalInput(BaseModel):
    note: str = ""


class SimulateInput(BaseModel):
    scenario: str = "clinic_booking"


class TransferInput(BaseModel):
    team_id: str
    note: str = ""


class OutcomeInput(BaseModel):
    outcome: str


class NoteInput(BaseModel):
    note: str


class CancelInput(BaseModel):
    reason: str = "Cancelled by supervisor in deterministic local mode"


class ReviewInput(BaseModel):
    feedback: str
    score: float = Field(default=85, ge=0, le=100)
    mark_training_example: bool = False
    policy_violation: bool = False
    request_second_review: bool = False


class FollowUpInput(BaseModel):
    task_type: str = "callback"
    title: str
    assignee: str = "Unassigned"
    due_at: datetime | None = None
    priority: str = "normal"


class LeadInput(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    service_type: str = "General inquiry"
    urgency: str = "normal"
    location: str = ""
    status: str = "new"
    score: float = 50
    owner: str = "Unassigned"


class LeadStageInput(BaseModel):
    status: str


class MergeLeadInput(BaseModel):
    duplicate_lead_id: str


class AppointmentInput(BaseModel):
    title: str
    lead_id: str | None = None
    start_time: datetime
    end_time: datetime
    assignee: str = "Intake Team"
    agent_id: str | None = None


class RescheduleInput(BaseModel):
    start_time: datetime
    end_time: datetime
    assignee: str | None = None


class RoutingEvaluateInput(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class RoutingRuleInput(BaseModel):
    name: str
    condition: dict[str, Any]
    priority: int = Field(default=50, ge=1, le=999)
    destination_type: str
    destination: str
    fallback: str = "Create callback task"
    notification: str = "in_app"
    audit_required: bool = True


class CrmSyncInput(BaseModel):
    simulate_failure: bool = False
    idempotency_key: str | None = None


class ReportInput(BaseModel):
    report_type: str = "Daily Voice Operations Brief"


class ScheduleReportInput(BaseModel):
    report_type: str
    cadence: str
    next_run_at: datetime
    destination: str = "in_app (simulated delivery)"


class ApiKeyInput(BaseModel):
    name: str
    scopes: list[str] = Field(default_factory=lambda: ["calls:read"])
    expires_at: datetime | None = None


class AlertActionInput(BaseModel):
    action: str = "acknowledged"


class ProviderActionInput(BaseModel):
    status: str | None = None


class RetentionInput(BaseModel):
    name: str
    resource_type: str
    retention_days: int = Field(ge=1, le=3650)
    action: str = "delete_after_retention"


class DeletionRequestInput(BaseModel):
    requester_reference: str
    scope: str
    reason: str = ""


class CoachingInput(BaseModel):
    title: str
    remediation: str
    owner: str = "Quality Team"
    due_at: datetime | None = None
    call_id: str | None = None
    agent_version_id: str | None = None


@app.on_event("startup")
def bootstrap() -> None:
    insecure_secrets = {"change-me-in-production", "development-only-change-me", "production-change-me"}
    if settings.environment not in {"development", "test"} and settings.jwt_secret in insecure_secrets:
        raise RuntimeError("JWT_SECRET must be replaced before starting a non-development VoxRelay environment")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


def audit(
    db: Session,
    organization_id: str,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            id=f"audit-{uuid4().hex[:12]}",
            organization_id=organization_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail or {},
        )
    )


def require_org_record(record: Any, organization_id: str, label: str) -> Any:
    if not record or getattr(record, "organization_id", None) != organization_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record


def call_dict(call: CallSession) -> dict[str, Any]:
    return {
        "id": call.id,
        "organization_id": call.organization_id,
        "agent_id": call.agent_id,
        "scenario": call.scenario,
        "direction": call.direction,
        "status": call.status,
        "caller_name": call.caller_name,
        "caller_phone": call.caller_phone,
        "duration_seconds": call.duration_seconds,
        "outcome": call.outcome,
        "lead_score": call.lead_score,
        "quality_score": call.quality_score,
        "consent_state": call.consent_state,
        "escalation_level": call.escalation_level,
        "created_at": call.created_at.isoformat(),
        "synthetic": bool(call.metadata_json.get("synthetic", False)),
        "provider_mode": call.metadata_json.get("provider_mode", "deterministic_local"),
    }


def lead_dict(lead: Lead) -> dict[str, Any]:
    return {
        "id": lead.id,
        "organization_id": lead.organization_id,
        "call_id": lead.call_id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "service_type": lead.service_type,
        "urgency": lead.urgency,
        "location": lead.location,
        "status": lead.status,
        "score": lead.score,
        "owner": lead.owner,
        "tags": lead.tags,
        "source_campaign": lead.source_campaign,
        "crm_sync_status": lead.crm_sync_status,
        "fields": lead.fields_json,
        "created_at": lead.created_at.isoformat(),
    }


def appointment_dict(appointment: Appointment) -> dict[str, Any]:
    return {
        "id": appointment.id,
        "organization_id": appointment.organization_id,
        "title": appointment.title,
        "lead_id": appointment.lead_id,
        "agent_id": appointment.agent_id,
        "start_time": appointment.start_time.isoformat(),
        "end_time": appointment.end_time.isoformat(),
        "status": appointment.status,
        "assignee": appointment.assignee,
        "provider": appointment.provider,
    }


def agent_dict(agent: VoiceAgent) -> dict[str, Any]:
    return {
        "id": agent.id,
        "organization_id": agent.organization_id,
        "name": agent.name,
        "status": agent.status,
        "use_case": agent.use_case,
        "language": agent.language,
        "voice": agent.voice,
        "version": agent.version,
        "config": agent.config,
    }


def version_dict(version: AgentVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "organization_id": version.organization_id,
        "agent_id": version.agent_id,
        "version_number": version.version_number,
        "status": version.status,
        "config_snapshot": version.config_snapshot,
        "release_notes": version.release_notes,
        "evaluation_summary": version.evaluation_summary,
        "release_gates": version.release_gates,
        "activated_at": version.activated_at.isoformat() if version.activated_at else None,
        "created_at": version.created_at.isoformat(),
    }


def job_dict(job: IntegrationJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "organization_id": job.organization_id,
        "job_type": job.job_type,
        "provider": job.provider,
        "entity_type": job.entity_type,
        "entity_id": job.entity_id,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
        "last_error": job.last_error,
        "idempotency_key": job.idempotency_key,
        "payload_preview": job.payload,
    }


def _workspace_memberships(db: Session, user_id: str) -> list[dict[str, Any]]:
    records = (
        db.query(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(OrganizationMembership.user_id == user_id, OrganizationMembership.is_active.is_(True))
        .all()
    )
    return [
        {"id": organization.id, "name": organization.name, "slug": organization.slug, "role": membership.role}
        for membership, organization in records
    ]


def _issue_login_payload(db: Session, user: User, organization_id: str, role: str) -> dict[str, Any]:
    return {
        "access_token": create_access_token(user, organization_id, role),
        "refresh_token": create_refresh_session(db, user, organization_id),
        "token_type": "bearer",
        "demo_mode": True,
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": role},
        "workspace": {"organization_id": organization_id, "role": role},
        "workspaces": _workspace_memberships(db, user.id),
    }


@app.get("/health")
def health(db: Db) -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "voxrelay-api",
        "version": "3.0.0",
        "demo_mode": settings.demo_mode,
        "database": "connected",
        "calls": db.query(CallSession).count(),
        "organizations": db.query(Organization).count(),
        "websocket": "available",
    }


@app.post(f"{settings.api_prefix}/auth/login")
def login(payload: LoginInput, db: Db) -> dict[str, Any]:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == user.organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No active workspace membership")
    audit(db, user.organization_id, user.email, "auth.login", "user", user.id, {"synthetic": True})
    db.commit()
    return _issue_login_payload(db, user, membership.organization_id, membership.role)


@app.post(f"{settings.api_prefix}/auth/refresh")
def refresh(payload: RefreshInput, db: Db) -> dict[str, Any]:
    user, access_token, refresh_token = rotate_refresh_session(db, payload.refresh_token)
    membership = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.organization_id == user.organization_id)
        .first()
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "workspace": {"organization_id": user.organization_id, "role": membership.role if membership else user.role},
    }


@app.post(f"{settings.api_prefix}/auth/logout", status_code=204)
def logout(payload: LogoutInput, db: Db, current: Current) -> None:
    revoke_refresh_session(db, payload.refresh_token)
    audit(db, current.organization_id, current.email, "auth.logout", "user", current.user_id)
    db.commit()


@app.get(f"{settings.api_prefix}/auth/me")
def me(db: Db, current: Current) -> dict[str, Any]:
    user = db.get(User, current.user_id)
    return {
        "id": current.user_id,
        "email": current.email,
        "name": user.name if user else current.email,
        "role": current.role,
        "organization_id": current.organization_id,
        "permissions": sorted(current.permissions),
        "workspaces": _workspace_memberships(db, current.user_id),
    }


@app.get(f"{settings.api_prefix}/auth/workspaces")
def workspaces(db: Db, current: Current) -> dict[str, Any]:
    return {"items": _workspace_memberships(db, current.user_id)}


@app.post(f"{settings.api_prefix}/auth/switch-workspace")
def switch_workspace(payload: WorkspaceInput, db: Db, current: Current) -> dict[str, Any]:
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == current.user_id,
            OrganizationMembership.organization_id == payload.organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="You do not have access to this workspace")
    user = db.get(User, current.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User is unavailable")
    audit(
        db,
        payload.organization_id,
        current.email,
        "workspace.switched",
        "organization",
        payload.organization_id,
        {"from": current.organization_id},
    )
    db.commit()
    return _issue_login_payload(db, user, payload.organization_id, membership.role)


# ------------------- Agents, versions, evaluation, and releases -------------------


@app.get(f"{settings.api_prefix}/voice-agents")
def list_agents(db: Db, current: Current) -> list[dict[str, Any]]:
    agents = (
        db.query(VoiceAgent)
        .filter(VoiceAgent.organization_id == current.organization_id)
        .order_by(VoiceAgent.name)
        .all()
    )
    return [agent_dict(agent) for agent in agents]


@app.post(f"{settings.api_prefix}/voice-agents", status_code=201)
def create_agent(payload: CreateAgentInput, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:manage"))]) -> dict[str, Any]:
    agent = VoiceAgent(
        id=f"agent-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        name=payload.name,
        use_case=payload.use_case,
        language=payload.language,
        voice=payload.voice,
        status="draft",
        version=1,
        config=payload.config,
    )
    db.add(agent)
    audit(db, current.organization_id, current.email, "agent.created", "voice_agent", agent.id)
    db.commit()
    return agent_dict(agent)


@app.get(f"{settings.api_prefix}/voice-agents/{{agent_id}}")
def get_agent(agent_id: str, db: Db, current: Current) -> dict[str, Any]:
    return agent_dict(require_org_record(db.get(VoiceAgent, agent_id), current.organization_id, "Agent"))


@app.patch(f"{settings.api_prefix}/voice-agents/{{agent_id}}")
def update_agent(agent_id: str, payload: UpdateAgentInput, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:manage"))]) -> dict[str, Any]:
    agent = require_org_record(db.get(VoiceAgent, agent_id), current.organization_id, "Agent")
    if payload.name:
        agent.name = payload.name
    if payload.config is not None:
        agent.config = payload.config
    if payload.status:
        agent.status = payload.status
    audit(db, current.organization_id, current.email, "agent.updated", "voice_agent", agent.id)
    db.commit()
    return agent_dict(agent)


@app.post(f"{settings.api_prefix}/voice-agents/{{agent_id}}/versions", status_code=201)
def create_agent_version(agent_id: str, payload: AgentVersionInput, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:manage"))]) -> dict[str, Any]:
    agent = require_org_record(db.get(VoiceAgent, agent_id), current.organization_id, "Agent")
    last = (
        db.query(func.max(AgentVersion.version_number))
        .filter(AgentVersion.agent_id == agent.id, AgentVersion.organization_id == current.organization_id)
        .scalar()
        or agent.version
    )
    version = AgentVersion(
        id=f"agent-version-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        agent_id=agent.id,
        version_number=int(last) + 1,
        status="draft",
        config_snapshot=payload.config_snapshot or agent.config,
        release_notes=payload.release_notes,
        owner_id=current.user_id,
        evaluation_summary={},
        release_gates={
            "required_scenarios_passed": False,
            "emergency_behavior_valid": False,
            "consent_flow_valid": False,
            "restricted_topic_policy_valid": False,
            "required_extraction_valid": False,
            "critical_failures": 0,
            "approval_granted": False,
        },
    )
    db.add(version)
    audit(db, current.organization_id, current.email, "agent.version_created", "agent_version", version.id)
    db.commit()
    return version_dict(version)


@app.get(f"{settings.api_prefix}/voice-agents/{{agent_id}}/versions")
def list_agent_versions(agent_id: str, db: Db, current: Current) -> dict[str, Any]:
    require_org_record(db.get(VoiceAgent, agent_id), current.organization_id, "Agent")
    versions = (
        db.query(AgentVersion)
        .filter(AgentVersion.agent_id == agent_id, AgentVersion.organization_id == current.organization_id)
        .order_by(AgentVersion.version_number.desc())
        .all()
    )
    return {"items": [version_dict(version) for version in versions]}


@app.get(f"{settings.api_prefix}/voice-agents/{{agent_id}}/versions/compare")
def compare_versions(agent_id: str, from_version: int, to_version: int, db: Db, current: Current) -> dict[str, Any]:
    require_org_record(db.get(VoiceAgent, agent_id), current.organization_id, "Agent")
    versions = {
        version.version_number: version
        for version in db.query(AgentVersion)
        .filter(AgentVersion.agent_id == agent_id, AgentVersion.organization_id == current.organization_id)
        .all()
    }
    source, target = versions.get(from_version), versions.get(to_version)
    if not source or not target:
        raise HTTPException(status_code=404, detail="Requested versions are unavailable")
    keys = sorted(set(source.config_snapshot) | set(target.config_snapshot))
    changes = [
        {"field": key, "from": source.config_snapshot.get(key), "to": target.config_snapshot.get(key)}
        for key in keys
        if source.config_snapshot.get(key) != target.config_snapshot.get(key)
    ]
    return {
        "from": version_dict(source),
        "to": version_dict(target),
        "configuration_changes": changes,
        "metric_comparison": {
            "evaluation_pass_rate": [source.evaluation_summary.get("pass_rate", 0), target.evaluation_summary.get("pass_rate", 0)],
            "critical_failures": [source.evaluation_summary.get("critical_failures", 0), target.evaluation_summary.get("critical_failures", 0)],
            "latency_difference_ms": 18,
            "human_handoff_rate_difference": -1.8,
            "synthetic": True,
        },
    }


@app.post(f"{settings.api_prefix}/voice-agents/versions/{{version_id}}/evaluate")
def evaluate_agent_version(version_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:manage"))]) -> dict[str, Any]:
    version = require_org_record(db.get(AgentVersion, version_id), current.organization_id, "Agent version")
    suite = db.query(EvaluationSuite).filter(EvaluationSuite.organization_id == current.organization_id).first()
    if not suite:
        raise HTTPException(status_code=404, detail="Evaluation suite not found")
    cases = suite.cases
    # Deterministic, transparent local evaluation: current policy configuration gates synthetic expected behavior.
    critical_failures = 0
    pass_rate = 97.5
    if not version.config_snapshot.get("required_fields", []):
        critical_failures = 1
        pass_rate = 82.5
    gates = {
        "required_scenarios_passed": critical_failures == 0,
        "emergency_behavior_valid": critical_failures == 0,
        "consent_flow_valid": bool(version.config_snapshot.get("consent_required", True)),
        "restricted_topic_policy_valid": bool(version.config_snapshot.get("restricted_topics", CONFIGURED_RESTRICTED_TOPICS)),
        "required_extraction_valid": bool(version.config_snapshot.get("required_fields", [])),
        "critical_failures": critical_failures,
        "approval_granted": False,
    }
    version.status = "testing"
    version.evaluation_summary = {"pass_rate": pass_rate, "critical_failures": critical_failures, "cases": len(cases), "synthetic": True}
    version.release_gates = gates
    run = EvaluationRun(
        id=f"eval-run-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        suite_id=suite.id,
        agent_version_id=version.id,
        status="completed",
        pass_rate=pass_rate,
        critical_failures=critical_failures,
        result_json={"passed": int(len(cases) * pass_rate / 100), "failed": len(cases) - int(len(cases) * pass_rate / 100), "synthetic": True},
    )
    db.add(run)
    audit(db, current.organization_id, current.email, "agent.evaluation_completed", "agent_version", version.id, {"run_id": run.id, "pass_rate": pass_rate})
    db.commit()
    return {"version": version_dict(version), "run_id": run.id, "suite": suite.name}


CONFIGURED_RESTRICTED_TOPICS = ["medical diagnosis", "coverage determination", "legal advice"]


@app.post(f"{settings.api_prefix}/voice-agents/versions/{{version_id}}/submit")
def submit_agent_version(version_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:manage"))]) -> dict[str, Any]:
    version = require_org_record(db.get(AgentVersion, version_id), current.organization_id, "Agent version")
    gates = version.release_gates or {}
    blockers = [key for key, value in gates.items() if key != "approval_granted" and value is False]
    if blockers or int(gates.get("critical_failures", 0)) > 0:
        raise HTTPException(status_code=422, detail={"message": "Release gate blocked", "blockers": blockers or ["critical_failures"]})
    version.status = "in_review"
    audit(db, current.organization_id, current.email, "agent.version_submitted", "agent_version", version.id)
    db.commit()
    return version_dict(version)


@app.post(f"{settings.api_prefix}/voice-agents/versions/{{version_id}}/approve")
def approve_agent_version(version_id: str, payload: ApprovalInput, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:approve"))]) -> dict[str, Any]:
    version = require_org_record(db.get(AgentVersion, version_id), current.organization_id, "Agent version")
    if version.status not in {"in_review", "testing", "approved"}:
        raise HTTPException(status_code=422, detail="Version must be in review after evaluation before approval")
    if int(version.release_gates.get("critical_failures", 0)) > 0:
        raise HTTPException(status_code=422, detail="Critical evaluation failures block approval")
    version.status = "approved"
    version.release_gates = {**version.release_gates, "approval_granted": True}
    db.add(
        AgentReleaseApproval(
            id=f"approval-{uuid4().hex[:12]}",
            organization_id=current.organization_id,
            agent_version_id=version.id,
            approver_id=current.user_id,
            decision="approved",
            note=payload.note,
        )
    )
    audit(db, current.organization_id, current.email, "agent.release_approved", "agent_version", version.id)
    db.commit()
    return version_dict(version)


@app.post(f"{settings.api_prefix}/voice-agents/versions/{{version_id}}/stage")
def stage_agent_version(version_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:approve"))]) -> dict[str, Any]:
    version = require_org_record(db.get(AgentVersion, version_id), current.organization_id, "Agent version")
    if version.status != "approved":
        raise HTTPException(status_code=409, detail="Only approved versions can be staged")
    version.status = "staged"
    audit(db, current.organization_id, current.email, "agent_version.staged", "agent_version", version.id)
    db.commit()
    return {"version": version_dict(version), "status": "staged"}


@app.post(f"{settings.api_prefix}/voice-agents/versions/{{version_id}}/activate")
def activate_agent_version(version_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:activate"))]) -> dict[str, Any]:
    version = require_org_record(db.get(AgentVersion, version_id), current.organization_id, "Agent version")
    gates = version.release_gates or {}
    allowed = version.status in {"approved", "staged"} and gates.get("approval_granted") and int(gates.get("critical_failures", 0)) == 0
    if not allowed:
        raise HTTPException(status_code=422, detail="Release gate prevents activation")
    agent = require_org_record(db.get(VoiceAgent, version.agent_id), current.organization_id, "Agent")
    db.query(AgentVersion).filter(
        AgentVersion.agent_id == agent.id,
        AgentVersion.organization_id == current.organization_id,
        AgentVersion.status == "active",
    ).update({"status": "deprecated"})
    version.status = "active"
    version.activated_at = datetime.utcnow()
    agent.version = version.version_number
    agent.status = "active"
    agent.config = version.config_snapshot
    audit(db, current.organization_id, current.email, "agent.version_activated", "agent_version", version.id)
    db.commit()
    return {"version": version_dict(version), "agent": agent_dict(agent)}


@app.post(f"{settings.api_prefix}/voice-agents/{{agent_id}}/rollback")
def rollback_agent(agent_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("agents:activate"))]) -> dict[str, Any]:
    agent = require_org_record(db.get(VoiceAgent, agent_id), current.organization_id, "Agent")
    previous = (
        db.query(AgentVersion)
        .filter(AgentVersion.agent_id == agent_id, AgentVersion.organization_id == current.organization_id, AgentVersion.status.in_(["deprecated", "approved"]))
        .order_by(AgentVersion.version_number.desc())
        .first()
    )
    active = (
        db.query(AgentVersion)
        .filter(AgentVersion.agent_id == agent_id, AgentVersion.organization_id == current.organization_id, AgentVersion.status == "active")
        .first()
    )
    if not previous or not active:
        raise HTTPException(status_code=422, detail="No rollback target is available")
    active.status = "rolled_back"
    active.rolled_back_at = datetime.utcnow()
    previous.status = "active"
    previous.activated_at = datetime.utcnow()
    agent.version = previous.version_number
    agent.config = previous.config_snapshot
    audit(db, current.organization_id, current.email, "agent.version_rolled_back", "voice_agent", agent.id, {"target": previous.id})
    db.commit()
    return {"agent": agent_dict(agent), "activated_version": version_dict(previous)}


@app.post(f"{settings.api_prefix}/voice-agents/{{agent_id}}/simulate", status_code=201)
def simulate_agent(agent_id: str, payload: SimulateInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:read"))]) -> dict[str, Any]:
    agent = require_org_record(db.get(VoiceAgent, agent_id), current.organization_id, "Agent")
    if payload.scenario not in SCENARIOS:
        raise HTTPException(status_code=422, detail={"message": "Unknown scenario", "available": list(SCENARIOS)})
    call = create_simulated_call(db, payload.scenario, agent.id, current.organization_id, current.email)
    return {
        "call": call_dict(call),
        "websocket_path": f"{settings.api_prefix}/ws/calls/{call.id}",
        "scenario": SCENARIOS[payload.scenario].label,
        "mode": "deterministic_local_simulation",
    }


# ------------------- Calls, transcript evidence, supervisor operations -------------------


@app.get(f"{settings.api_prefix}/calls")
def list_calls(
    db: Db,
    current: Current,
    q: str = "",
    outcome: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    query = db.query(CallSession).filter(CallSession.organization_id == current.organization_id)
    if q:
        query = query.filter(CallSession.caller_name.ilike(f"%{q}%"))
    if outcome:
        query = query.filter(CallSession.outcome == outcome)
    if status:
        query = query.filter(CallSession.status == status)
    total = query.count()
    records = query.order_by(CallSession.created_at.desc()).limit(limit).all()
    return {"items": [call_dict(call) for call in records], "total": total}


@app.post(f"{settings.api_prefix}/calls/simulated", status_code=201)
def create_call(payload: SimulateInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:read"))]) -> dict[str, Any]:
    scenario = SCENARIOS.get(payload.scenario)
    if not scenario:
        raise HTTPException(status_code=422, detail={"message": "Unknown scenario", "available": list(SCENARIOS)})
    agent = db.get(VoiceAgent, scenario.agent_id)
    if not agent or agent.organization_id != current.organization_id:
        agent = db.query(VoiceAgent).filter(VoiceAgent.organization_id == current.organization_id).order_by(VoiceAgent.name).first()
    if not agent:
        raise HTTPException(status_code=422, detail="No agent is configured in this workspace")
    return simulate_agent(agent.id, payload, db, current)


@app.get(f"{settings.api_prefix}/calls/{{call_id}}")
def call_detail(call_id: str, db: Db, current: Current) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    segments = db.query(TranscriptSegment).filter(TranscriptSegment.call_id == call_id).order_by(TranscriptSegment.offset_ms).all()
    events = db.query(CallEvent).filter(CallEvent.call_id == call_id, CallEvent.organization_id == current.organization_id).order_by(CallEvent.occurred_at).all()
    entities = db.query(ExtractedEntity).filter(ExtractedEntity.call_id == call_id, ExtractedEntity.organization_id == current.organization_id).all()
    lead = db.query(Lead).filter(Lead.call_id == call_id, Lead.organization_id == current.organization_id).first()
    appointment = (
        db.query(Appointment)
        .join(Lead, Appointment.lead_id == Lead.id)
        .filter(Lead.call_id == call_id, Appointment.organization_id == current.organization_id)
        .first()
    )
    quality = db.query(QualityEvaluation).filter(QualityEvaluation.call_id == call_id).first()
    feedback = db.query(ReviewerFeedback).filter(ReviewerFeedback.call_id == call_id, ReviewerFeedback.organization_id == current.organization_id).all()
    return {
        "call": call_dict(call),
        "transcript": [
            {
                "id": segment.id,
                "speaker": segment.speaker,
                "text": segment.text,
                "confidence": segment.confidence,
                "offset_ms": segment.offset_ms,
                "redacted_log_preview": redact_pii(segment.text),
            }
            for segment in segments
        ],
        "events": [
            {
                "id": event.id,
                "type": event.event_type,
                "event_type": event.payload.get("event_type", event.event_type),
                "sequence": event.payload.get("sequence"),
                "trace_id": event.payload.get("trace_id", call.metadata_json.get("trace_id", f"trace-{call.id}")),
                "schema_version": event.payload.get("schema_version", "legacy"),
                "state": event.state,
                "payload": event.payload,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in events
        ],
        "entities": [
            {
                "id": entity.id,
                "field": entity.field_name,
                "value": entity.value,
                "confidence": entity.confidence,
                "source_segment_id": entity.source_segment_id,
                "validation_state": entity.validation_state,
                "reviewer_override": entity.reviewer_override,
                "pii_classification": entity.pii_classification,
                "crm_mapping_status": entity.crm_mapping_status,
            }
            for entity in entities
        ],
        "lead": lead_dict(lead) if lead else None,
        "appointment": appointment_dict(appointment) if appointment else None,
        "quality": (
            {
                "score": quality.quality_score,
                "transcript_completeness": quality.transcript_completeness,
                "hallucination_risk": quality.hallucination_risk,
                "policy_risk": quality.policy_risk,
                "latency_ms": quality.latency_ms,
                "sentiment_trend": quality.sentiment_trend,
                "findings": quality.findings,
                "mode": "synthetic_rule_assisted",
            }
            if quality
            else None
        ),
        "reviewer_feedback": [
            {"id": item.id, "score": item.score, "feedback": item.feedback, "policy_violation": item.policy_violation, "training_example": item.training_example}
            for item in feedback
        ],
    }


@app.patch(f"{settings.api_prefix}/calls/{{call_id}}/outcome")
def update_outcome(call_id: str, payload: OutcomeInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:transfer"))]) -> dict[str, str]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    call.outcome = payload.outcome
    audit(db, current.organization_id, current.email, "call.outcome_updated", "call", call.id, {"outcome": payload.outcome})
    db.commit()
    return {"id": call.id, "outcome": call.outcome}


@app.post(f"{settings.api_prefix}/calls/{{call_id}}/notes", status_code=201)
def add_call_note(call_id: str, payload: NoteInput, db: Db, current: Annotated[Principal, Depends(require_permissions("quality:review"))]) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    redacted = redact_pii(payload.note)
    event = CallEvent(
        id=f"call-event-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        call_id=call.id,
        event_type="note.added",
        state=call.status,
        payload={"note_redacted": redacted, "trace_id": call.metadata_json.get("trace_id", f"trace-{call.id}"), "schema_version": "2026-07.phase3"},
    )
    db.add(event)
    audit(db, current.organization_id, current.email, "call.note_added", "call", call.id, {"redacted": True})
    db.commit()
    return {"status": "noted", "event_id": event.id, "note_redacted": redacted}


@app.post(f"{settings.api_prefix}/calls/{{call_id}}/cancel")
def cancel_call(call_id: str, payload: CancelInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:transfer"))]) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    if call.status in {"completed", "failed", "abandoned"}:
        return {"status": call.status, "detail": "Call was already terminal; no duplicate cancellation was applied."}
    call.status = "abandoned"
    call.outcome = "cancelled"
    event = CallEvent(
        id=f"call-event-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        call_id=call.id,
        event_type="simulation.cancelled",
        state="abandoned",
        payload={"reason": payload.reason, "trace_id": call.metadata_json.get("trace_id", f"trace-{call.id}"), "schema_version": "2026-07.phase3"},
    )
    db.add(event)
    audit(db, current.organization_id, current.email, "simulation.cancelled", "call", call.id, {"reason": payload.reason})
    db.commit()
    return {"status": "abandoned", "event_id": event.id}


@app.post(f"{settings.api_prefix}/calls/{{call_id}}/transfer")
def transfer_call(call_id: str, payload: TransferInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:transfer"))]) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    team = require_org_record(db.get(HandoffTeam, payload.team_id), current.organization_id, "Handoff team")
    call.outcome = "transferred"
    call.escalation_level = "human"
    call.status = "handoff_pending"
    db.add(
        CallEvent(
            id=f"call-event-{uuid4().hex[:12]}",
            organization_id=current.organization_id,
            call_id=call.id,
            event_type="handoff",
            state="handoff_pending",
            payload={"team": team.name, "destination": team.destination, "note": payload.note, "human_controlled": True},
        )
    )
    audit(db, current.organization_id, current.email, "call.transferred", "call", call.id, {"team": team.name, "note": payload.note})
    db.commit()
    return {"call_id": call.id, "status": "handoff_pending", "team": {"id": team.id, "name": team.name, "destination": team.destination}, "summary": "Structured handoff summary is stored locally; no external transfer carrier was invoked."}


@app.post(f"{settings.api_prefix}/calls/{{call_id}}/takeover")
def takeover_call(call_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:takeover"))]) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    call.status = "human_takeover"
    call.escalation_level = "human_takeover"
    db.add(
        CallEvent(
            id=f"call-event-{uuid4().hex[:12]}",
            organization_id=current.organization_id,
            call_id=call.id,
            event_type="human_takeover",
            state="human_takeover",
            payload={"supervisor": current.email, "simulated": True},
        )
    )
    audit(db, current.organization_id, current.email, "call.human_takeover", "call", call.id, {"synthetic": True})
    db.commit()
    return {"call_id": call.id, "status": "human_takeover", "notice": "Supervisor takeover is simulated locally; carrier audio control is an optional telephony adapter capability."}


@app.post(f"{settings.api_prefix}/calls/{{call_id}}/review-feedback")
def add_review_feedback(call_id: str, payload: ReviewInput, db: Db, current: Annotated[Principal, Depends(require_permissions("quality:review"))]) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    review = ReviewerFeedback(
        id=f"review-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        call_id=call.id,
        reviewer_id=current.user_id,
        score=payload.score,
        feedback=payload.feedback,
        policy_violation=payload.policy_violation,
        training_example=payload.mark_training_example,
        second_review_requested=payload.request_second_review,
    )
    db.add(review)
    audit(
        db,
        current.organization_id,
        current.email,
        "review.feedback_added",
        "call",
        call.id,
        {"training_example": payload.mark_training_example, "policy_violation": payload.policy_violation},
    )
    db.commit()
    return {"status": "saved", "review_id": review.id, "training_example": payload.mark_training_example}


@app.post(f"{settings.api_prefix}/calls/{{call_id}}/follow-up", status_code=201)
def create_follow_up(call_id: str, payload: FollowUpInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:transfer"))]) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    lead = db.query(Lead).filter(Lead.call_id == call.id, Lead.organization_id == current.organization_id).first()
    task = FollowUpTask(
        id=f"task-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        lead_id=lead.id if lead else None,
        call_id=call.id,
        task_type=payload.task_type,
        title=payload.title,
        assignee=payload.assignee,
        due_at=payload.due_at,
        priority=payload.priority,
        status="open",
    )
    db.add(task)
    audit(db, current.organization_id, current.email, "follow_up.created", "call", call.id, {"task_id": task.id})
    db.commit()
    return {"id": task.id, "status": task.status, "title": task.title}


@app.websocket(f"{settings.api_prefix}/ws/calls/{{call_id}}")
async def websocket_call(websocket: WebSocket, call_id: str, token: str | None = None) -> None:
    await websocket.accept()
    db = SessionLocal()
    try:
        if not token:
            await websocket.send_json({"type": "error", "detail": "token query parameter is required"})
            await websocket.close(code=4401)
            return
        from app.security import _principal_from_token

        principal = _principal_from_token(token, db)
        call = db.get(CallSession, call_id)
        if not call or call.organization_id != principal.organization_id:
            await websocket.send_json({"type": "error", "detail": "Call not found"})
            await websocket.close(code=4404)
            return
        async for event in stream_scenario(db, call):
            await websocket.send_json(event)
        await websocket.close()
    except WebSocketDisconnect:
        pass
    finally:
        db.close()


# ------------------- Leads, CRM reliability, appointments -------------------


@app.get(f"{settings.api_prefix}/leads")
def list_leads(db: Db, current: Current, status: str | None = None, q: str = "", limit: int = Query(100, ge=1, le=200)) -> dict[str, Any]:
    query = db.query(Lead).filter(Lead.organization_id == current.organization_id)
    if status:
        query = query.filter(Lead.status == status)
    if q:
        query = query.filter(Lead.name.ilike(f"%{q}%"))
    total = query.count()
    items = query.order_by(Lead.created_at.desc()).limit(limit).all()
    return {"items": [lead_dict(lead) for lead in items], "total": total}


@app.post(f"{settings.api_prefix}/leads", status_code=201)
def create_lead(payload: LeadInput, db: Db, current: Annotated[Principal, Depends(require_permissions("leads:manage"))]) -> dict[str, Any]:
    lead = Lead(
        id=f"lead-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        **payload.model_dump(),
        tags=["manual", "synthetic"],
        fields_json={"synthetic": True},
    )
    db.add(lead)
    audit(db, current.organization_id, current.email, "lead.created", "lead", lead.id)
    db.commit()
    return lead_dict(lead)


@app.get(f"{settings.api_prefix}/leads/{{lead_id}}")
def get_lead(lead_id: str, db: Db, current: Current) -> dict[str, Any]:
    lead = require_org_record(db.get(Lead, lead_id), current.organization_id, "Lead")
    calls = db.query(CallSession).filter(CallSession.id == lead.call_id, CallSession.organization_id == current.organization_id).all() if lead.call_id else []
    tasks = db.query(FollowUpTask).filter(FollowUpTask.lead_id == lead.id, FollowUpTask.organization_id == current.organization_id).all()
    appointments = db.query(Appointment).filter(Appointment.lead_id == lead.id, Appointment.organization_id == current.organization_id).all()
    return {
        "lead": lead_dict(lead),
        "linked_calls": [call_dict(call) for call in calls],
        "follow_up_tasks": [{"id": task.id, "title": task.title, "status": task.status, "priority": task.priority} for task in tasks],
        "appointments": [appointment_dict(appointment) for appointment in appointments],
    }


@app.patch(f"{settings.api_prefix}/leads/{{lead_id}}")
def update_lead(lead_id: str, payload: LeadInput, db: Db, current: Annotated[Principal, Depends(require_permissions("leads:manage"))]) -> dict[str, Any]:
    lead = require_org_record(db.get(Lead, lead_id), current.organization_id, "Lead")
    for key, value in payload.model_dump().items():
        setattr(lead, key, value)
    audit(db, current.organization_id, current.email, "lead.updated", "lead", lead.id)
    db.commit()
    return lead_dict(lead)


@app.post(f"{settings.api_prefix}/leads/{{lead_id}}/stage")
def update_lead_stage(lead_id: str, payload: LeadStageInput, db: Db, current: Annotated[Principal, Depends(require_permissions("leads:manage"))]) -> dict[str, Any]:
    lead = require_org_record(db.get(Lead, lead_id), current.organization_id, "Lead")
    lead.status = payload.status
    audit(db, current.organization_id, current.email, "lead.stage_updated", "lead", lead.id, {"status": payload.status})
    db.commit()
    return lead_dict(lead)


@app.post(f"{settings.api_prefix}/leads/{{lead_id}}/merge")
def merge_leads(lead_id: str, payload: MergeLeadInput, db: Db, current: Annotated[Principal, Depends(require_permissions("leads:manage"))]) -> dict[str, Any]:
    primary = require_org_record(db.get(Lead, lead_id), current.organization_id, "Lead")
    duplicate = require_org_record(db.get(Lead, payload.duplicate_lead_id), current.organization_id, "Duplicate lead")
    if primary.id == duplicate.id:
        raise HTTPException(status_code=422, detail="A lead cannot be merged into itself")
    duplicate.status = "archived"
    duplicate.tags = list(set(duplicate.tags + [f"merged_into:{primary.id}"]))
    audit(db, current.organization_id, current.email, "lead.merged", "lead", primary.id, {"duplicate_lead_id": duplicate.id})
    db.commit()
    return {"primary": lead_dict(primary), "merged": duplicate.id}


@app.get(f"{settings.api_prefix}/leads/pipeline")
def lead_pipeline(db: Db, current: Current) -> dict[str, Any]:
    statuses = ["new", "contacted", "qualified", "appointment_booked", "follow_up_required", "human_review", "disqualified", "won", "lost", "archived"]
    return {
        "columns": [
            {
                "status": status,
                "count": db.query(Lead).filter(Lead.organization_id == current.organization_id, Lead.status == status).count(),
                "leads": [
                    lead_dict(lead)
                    for lead in db.query(Lead)
                    .filter(Lead.organization_id == current.organization_id, Lead.status == status)
                    .order_by(Lead.score.desc())
                    .limit(8)
                    .all()
                ],
            }
            for status in statuses
        ]
    }


@app.get(f"{settings.api_prefix}/leads/export", response_class=PlainTextResponse)
def export_leads(db: Db, current: Annotated[Principal, Depends(require_permissions("leads:manage"))]) -> str:
    rows = ["id,name,service_type,status,score,owner,crm_sync_status"]
    for lead in db.query(Lead).filter(Lead.organization_id == current.organization_id).order_by(Lead.created_at.desc()).all():
        safe_name = redact_pii(lead.name).replace(",", " ")
        rows.append(f"{lead.id},{safe_name},{lead.service_type},{lead.status},{lead.score},{lead.owner},{lead.crm_sync_status}")
    audit(db, current.organization_id, current.email, "lead.exported", "lead_export", f"export-{uuid4().hex[:8]}")
    db.commit()
    return "\n".join(rows)


@app.post(f"{settings.api_prefix}/leads/{{lead_id}}/crm-sync")
def crm_sync(lead_id: str, payload: CrmSyncInput, db: Db, current: Annotated[Principal, Depends(require_permissions("leads:manage"))], x_idempotency_key: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    lead = require_org_record(db.get(Lead, lead_id), current.organization_id, "Lead")
    key = payload.idempotency_key or x_idempotency_key or f"manual-{lead.id}-{uuid4().hex[:8]}"
    job = enqueue_mock_crm_sync(db, current.organization_id, lead, key, payload.simulate_failure)
    return {"job": job_dict(job), "mode": "local_mock_crm", "external_delivery": False}


@app.get(f"{settings.api_prefix}/integrations/jobs")
def integration_jobs(db: Db, current: Current, status: str | None = None) -> dict[str, Any]:
    query = db.query(IntegrationJob).filter(IntegrationJob.organization_id == current.organization_id)
    if status:
        query = query.filter(IntegrationJob.status == status)
    return {"items": [job_dict(job) for job in query.order_by(IntegrationJob.created_at.desc()).all()]}


@app.post(f"{settings.api_prefix}/integrations/jobs/{{job_id}}/retry")
def retry_integration_job(job_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("providers:manage"))]) -> dict[str, Any]:
    job = require_org_record(db.get(IntegrationJob, job_id), current.organization_id, "Integration job")
    retried = retry_mock_job(db, job)
    return {"job": job_dict(retried), "mode": "local_mock_crm", "idempotent": True}


@app.get(f"{settings.api_prefix}/appointments")
def list_appointments(db: Db, current: Current) -> dict[str, Any]:
    items = db.query(Appointment).filter(Appointment.organization_id == current.organization_id).order_by(Appointment.start_time).all()
    return {"items": [appointment_dict(appointment) for appointment in items]}


def _appointment_conflict(db: Session, organization_id: str, assignee: str, start_time: datetime, end_time: datetime, exclude_id: str | None = None) -> Appointment | None:
    query = db.query(Appointment).filter(
        Appointment.organization_id == organization_id,
        Appointment.assignee == assignee,
        Appointment.status.notin_(["cancelled"]),
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)
    return query.first()


@app.post(f"{settings.api_prefix}/appointments", status_code=201)
def create_appointment(payload: AppointmentInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calendar:manage"))]) -> dict[str, Any]:
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="Appointment end must be after start")
    if payload.lead_id:
        require_org_record(db.get(Lead, payload.lead_id), current.organization_id, "Lead")
    conflict = _appointment_conflict(db, current.organization_id, payload.assignee, payload.start_time, payload.end_time)
    if conflict:
        db.add(
            BookingAttempt(
                id=f"booking-{uuid4().hex[:12]}",
                organization_id=current.organization_id,
                appointment_id=None,
                call_id=None,
                status="failed",
                provider="mock_local_calendar",
                reason=f"Conflict with {conflict.id}",
                idempotency_key=f"conflict-{uuid4().hex[:12]}",
            )
        )
        db.commit()
        raise HTTPException(status_code=409, detail={"message": "Calendar conflict detected", "conflicting_appointment_id": conflict.id})
    appointment = Appointment(
        id=f"apt-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        agent_id=payload.agent_id,
        status="confirmed",
        provider="mock_local_calendar",
        **payload.model_dump(exclude={"agent_id"}),
    )
    db.add(appointment)
    db.add(
        BookingAttempt(
            id=f"booking-{uuid4().hex[:12]}",
            organization_id=current.organization_id,
            appointment_id=appointment.id,
            call_id=None,
            status="confirmed",
            provider="mock_local_calendar",
            reason="Local deterministic provider accepted the booking.",
            idempotency_key=f"booking-{appointment.id}",
        )
    )
    audit(db, current.organization_id, current.email, "appointment.booked", "appointment", appointment.id, {"provider": "mock_local_calendar"})
    db.commit()
    return {"appointment": appointment_dict(appointment), "provider_mode": "fully_working_local_mock"}


@app.post(f"{settings.api_prefix}/appointments/{{appointment_id}}/reschedule")
def reschedule(appointment_id: str, payload: RescheduleInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calendar:manage"))]) -> dict[str, Any]:
    appointment = require_org_record(db.get(Appointment, appointment_id), current.organization_id, "Appointment")
    assignee = payload.assignee or appointment.assignee
    conflict = _appointment_conflict(db, current.organization_id, assignee, payload.start_time, payload.end_time, appointment.id)
    if conflict:
        raise HTTPException(status_code=409, detail={"message": "Calendar conflict detected", "conflicting_appointment_id": conflict.id})
    appointment.start_time = payload.start_time
    appointment.end_time = payload.end_time
    appointment.assignee = assignee
    appointment.status = "rescheduled"
    audit(db, current.organization_id, current.email, "appointment.rescheduled", "appointment", appointment.id)
    db.commit()
    return appointment_dict(appointment)


@app.post(f"{settings.api_prefix}/appointments/{{appointment_id}}/cancel")
def cancel(appointment_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("calendar:manage"))]) -> dict[str, str]:
    appointment = require_org_record(db.get(Appointment, appointment_id), current.organization_id, "Appointment")
    appointment.status = "cancelled"
    audit(db, current.organization_id, current.email, "appointment.cancelled", "appointment", appointment.id)
    db.commit()
    return {"id": appointment.id, "status": "cancelled"}


@app.get(f"{settings.api_prefix}/appointments/availability")
def availability(current: Current) -> dict[str, Any]:
    return {
        "provider": "mock_local_calendar",
        "timezone": "America/New_York",
        "slots": ["2026-07-08T10:00:00", "2026-07-08T13:30:00", "2026-07-09T09:00:00"],
        "note": "Synthetic availability from the fully working local deterministic provider; no external calendar is connected.",
        "organization_id": current.organization_id,
    }


@app.get(f"{settings.api_prefix}/appointments/booking-attempts")
def booking_attempts(db: Db, current: Current) -> dict[str, Any]:
    items = db.query(BookingAttempt).filter(BookingAttempt.organization_id == current.organization_id).order_by(BookingAttempt.created_at.desc()).all()
    return {"items": [{"id": item.id, "status": item.status, "reason": item.reason, "provider": item.provider, "appointment_id": item.appointment_id} for item in items]}


# ------------------- Supervisor, queues, routing -------------------


@app.get(f"{settings.api_prefix}/supervisor/overview")
def supervisor_overview(db: Db, current: Annotated[Principal, Depends(require_permissions("calls:read"))]) -> dict[str, Any]:
    active_states = ["queued", "ringing", "connected", "listening", "reasoning", "speaking", "booking", "handoff_pending", "human_takeover"]
    active_calls = db.query(CallSession).filter(CallSession.organization_id == current.organization_id, CallSession.status.in_(active_states)).order_by(CallSession.created_at.desc()).all()
    escalated = db.query(CallSession).filter(CallSession.organization_id == current.organization_id, CallSession.escalation_level.in_(["emergency", "human", "human_takeover", "human_review"])).order_by(CallSession.created_at.desc()).limit(20).all()
    review = db.query(CallSession).filter(CallSession.organization_id == current.organization_id, CallSession.outcome.in_(["needs_review", "transferred", "escalated"])).limit(20).all()
    queues = db.query(CallQueue).filter(CallQueue.organization_id == current.organization_id).all()
    return {
        "active_calls": [call_dict(call) for call in active_calls],
        "waiting_calls": [call_dict(call) for call in active_calls if call.status in {"queued", "ringing"}],
        "escalated_calls": [call_dict(call) for call in escalated],
        "calls_requiring_review": [call_dict(call) for call in review],
        "agent_status": {"available": 5, "busy": len(active_calls), "offline": 0, "synthetic": True},
        "queue_status": [{"id": queue.id, "name": queue.name, "sla_seconds": queue.sla_seconds, "active": queue.is_active} for queue in queues],
    }


@app.get(f"{settings.api_prefix}/queues")
def list_queues(db: Db, current: Current) -> dict[str, Any]:
    queues = db.query(CallQueue).filter(CallQueue.organization_id == current.organization_id).order_by(CallQueue.priority).all()
    items = []
    for queue in queues:
        waiting = db.query(CallSession).filter(CallSession.organization_id == current.organization_id, CallSession.status.in_(["queued", "ringing"])).count()
        items.append(
            {
                "id": queue.id,
                "name": queue.name,
                "service_type": queue.service_type,
                "priority": queue.priority,
                "sla_seconds": queue.sla_seconds,
                "business_hours": queue.business_hours,
                "overflow_policy": queue.overflow_policy,
                "waiting_calls": waiting if queue.priority < 3 else max(0, waiting - 1),
                "average_wait_seconds": 34 + queue.priority * 8,
                "abandonment_rate": round(1.2 + queue.priority * 0.7, 1),
                "synthetic": True,
            }
        )
    return {"items": items}


@app.get(f"{settings.api_prefix}/queues/operations")
def queue_operations(db: Db, current: Current) -> dict[str, Any]:
    queues = list_queues(db, current)["items"]
    return {
        "queues": queues,
        "trend": [{"hour": f"{hour:02d}:00", "volume": 9 + (hour * 3) % 18, "wait_seconds": 22 + (hour * 5) % 45} for hour in range(8, 19)],
        "business_hours_status": "open" if 8 <= datetime.utcnow().hour <= 18 else "after_hours",
        "note": "Queue telemetry is a deterministic synthetic demo estimate; no carrier queue is connected.",
    }


@app.get(f"{settings.api_prefix}/routing/rules")
def list_routing_rules(db: Db, current: Current) -> dict[str, Any]:
    rules = db.query(RoutingRule).filter(RoutingRule.organization_id == current.organization_id).order_by(RoutingRule.priority).all()
    return {"items": [{"id": rule.id, "name": rule.name, "condition": rule.condition, "priority": rule.priority, "destination_type": rule.destination_type, "destination": rule.destination, "fallback": rule.fallback, "notification": rule.notification, "audit_required": rule.audit_required, "is_active": rule.is_active} for rule in rules]}


@app.post(f"{settings.api_prefix}/routing/rules", status_code=201)
def create_routing_rule(payload: RoutingRuleInput, db: Db, current: Annotated[Principal, Depends(require_permissions("routing:manage"))]) -> dict[str, Any]:
    rule = RoutingRule(id=f"route-{uuid4().hex[:12]}", organization_id=current.organization_id, **payload.model_dump(), is_active=True)
    db.add(rule)
    audit(db, current.organization_id, current.email, "routing.rule_created", "routing_rule", rule.id)
    db.commit()
    return {"id": rule.id, "name": rule.name, "condition": rule.condition}


@app.post(f"{settings.api_prefix}/routing/evaluate")
def evaluate_routing_rule(payload: RoutingEvaluateInput, db: Db, current: Current) -> dict[str, Any]:
    decision = evaluate_routing(db, current.organization_id, payload.context)
    return {"matched": decision.matched, "rule_id": decision.rule_id, "rule_name": decision.rule_name, "destination_type": decision.destination_type, "destination": decision.destination, "fallback": decision.fallback, "notification": decision.notification, "reason": decision.reason, "mode": "deterministic_policy_engine"}


@app.get(f"{settings.api_prefix}/routing/handoff-analytics")
def handoff_analytics(db: Db, current: Current) -> dict[str, Any]:
    total = db.query(CallSession).filter(CallSession.organization_id == current.organization_id).count() or 1
    handoffs = db.query(CallSession).filter(CallSession.organization_id == current.organization_id, CallSession.outcome.in_(["transferred", "escalated", "needs_review"])).count()
    return {
        "handoff_rate": round(handoffs / total * 100, 1),
        "time_to_human_response_seconds": 46,
        "resolved_after_handoff_rate": 82.4,
        "abandoned_after_handoff_rate": 4.1,
        "reasons": [{"reason": "Low confidence", "count": 18}, {"reason": "Emergency", "count": 12}, {"reason": "Restricted topic", "count": 9}],
        "policy_trigger_frequency": [{"trigger": "emergency", "count": 12}, {"trigger": "booking_failure", "count": 8}, {"trigger": "consent", "count": 4}],
        "synthetic": True,
    }


# ------------------- Quality, coaching, governance -------------------


@app.get(f"{settings.api_prefix}/quality/review-queue")
def review_queue(db: Db, current: Annotated[Principal, Depends(require_permissions("quality:review"))]) -> dict[str, Any]:
    calls = (
        db.query(CallSession)
        .filter(CallSession.organization_id == current.organization_id, CallSession.outcome.in_(["needs_review", "escalated", "transferred"]))
        .order_by(CallSession.created_at.desc())
        .limit(50)
        .all()
    )
    return {"items": [call_dict(call) for call in calls]}


@app.get(f"{settings.api_prefix}/quality/rubrics")
def quality_rubrics(db: Db, current: Current) -> dict[str, Any]:
    rubrics = db.query(QualityRubric).filter(QualityRubric.organization_id == current.organization_id).all()
    return {"items": [{"id": rubric.id, "name": rubric.name, "version": rubric.version, "dimensions": rubric.dimensions, "is_active": rubric.is_active} for rubric in rubrics]}


@app.get(f"{settings.api_prefix}/quality/evaluation-suites")
def quality_suites(db: Db, current: Current) -> dict[str, Any]:
    suites = db.query(EvaluationSuite).filter(EvaluationSuite.organization_id == current.organization_id).all()
    return {"items": [{"id": suite.id, "name": suite.name, "use_case": suite.use_case, "rubric_version": suite.rubric_version, "case_count": len(suite.cases), "cases": suite.cases} for suite in suites]}


@app.get(f"{settings.api_prefix}/quality/evaluation-runs")
def evaluation_runs(db: Db, current: Current) -> dict[str, Any]:
    runs = db.query(EvaluationRun).filter(EvaluationRun.organization_id == current.organization_id).order_by(EvaluationRun.created_at.desc()).all()
    return {"items": [{"id": run.id, "suite_id": run.suite_id, "agent_version_id": run.agent_version_id, "status": run.status, "pass_rate": run.pass_rate, "critical_failures": run.critical_failures, "result": run.result_json} for run in runs]}


@app.post(f"{settings.api_prefix}/quality/coaching", status_code=201)
def create_coaching_task(payload: CoachingInput, db: Db, current: Annotated[Principal, Depends(require_permissions("quality:manage"))]) -> dict[str, Any]:
    if payload.call_id:
        require_org_record(db.get(CallSession, payload.call_id), current.organization_id, "Call")
    if payload.agent_version_id:
        require_org_record(db.get(AgentVersion, payload.agent_version_id), current.organization_id, "Agent version")
    task = CoachingTask(id=f"coaching-{uuid4().hex[:12]}", organization_id=current.organization_id, **payload.model_dump(), status="open")
    db.add(task)
    audit(db, current.organization_id, current.email, "coaching.task_created", "coaching_task", task.id)
    db.commit()
    return {"id": task.id, "status": task.status, "title": task.title}


@app.get(f"{settings.api_prefix}/quality/coaching")
def coaching_tasks(db: Db, current: Current) -> dict[str, Any]:
    tasks = db.query(CoachingTask).filter(CoachingTask.organization_id == current.organization_id).order_by(CoachingTask.due_at).all()
    return {"items": [{"id": task.id, "title": task.title, "owner": task.owner, "remediation": task.remediation, "due_at": task.due_at.isoformat() if task.due_at else None, "status": task.status, "call_id": task.call_id, "agent_version_id": task.agent_version_id} for task in tasks]}


@app.get(f"{settings.api_prefix}/governance/audit-events")
def audit_events(db: Db, current: Annotated[Principal, Depends(require_permissions("governance:manage"))], limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    events = db.query(AuditEvent).filter(AuditEvent.organization_id == current.organization_id).order_by(AuditEvent.created_at.desc()).limit(limit).all()
    return {"items": [{"id": event.id, "actor": event.actor, "action": event.action, "entity_type": event.entity_type, "entity_id": event.entity_id, "detail": event.detail, "created_at": event.created_at.isoformat()} for event in events]}


@app.get(f"{settings.api_prefix}/governance/roles-users")
def roles_users(db: Db, current: Annotated[Principal, Depends(require_permissions("workspace:manage"))]) -> dict[str, Any]:
    memberships = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == current.organization_id)
        .all()
    )
    return {
        "users": [{"email": user.email, "name": user.name, "role": membership.role, "active": membership.is_active} for membership, user in memberships],
        "roles": [{"name": name, "permissions": sorted(values)} for name, values in permission_set.__globals__["ROLE_PERMISSIONS"].items()],
    }


# ------------------- Analytics, forecasts, alerts, reports -------------------


@app.get(f"{settings.api_prefix}/analytics/overview")
def analytics_overview(db: Db, current: Current) -> dict[str, Any]:
    query = db.query(CallSession).filter(CallSession.organization_id == current.organization_id)
    total = query.count()
    booked = query.filter(CallSession.outcome == "booked").count()
    qualified = query.filter(CallSession.outcome.in_(["qualified", "booked"])).count()
    handoff = query.filter(CallSession.outcome.in_(["transferred", "escalated", "needs_review"])).count()
    avg_duration = query.with_entities(func.avg(CallSession.duration_seconds)).scalar() or 0
    avg_quality = query.with_entities(func.avg(CallSession.quality_score)).scalar() or 0
    abandoned = query.filter(CallSession.status == "abandoned").count()
    return {
        "total_calls": total,
        "answer_rate": 94.8,
        "qualification_rate": round(qualified / max(total, 1) * 100, 1),
        "booking_conversion": round(booked / max(total, 1) * 100, 1),
        "average_duration_seconds": round(avg_duration),
        "human_handoff_rate": round(handoff / max(total, 1) * 100, 1),
        "abandonment_rate": round(abandoned / max(total, 1) * 100, 1),
        "missed_calls": 3,
        "ai_resolution_rate": round((total - handoff) / max(total, 1) * 100, 1),
        "quality_score": round(avg_quality, 1),
        "latency_ms": 742,
        "estimated_cost_usd": round(total * 0.17, 2),
        "queue_sla": "92.4%",
        "synthetic": True,
        "cost_note": "Demo usage telemetry and estimated cost model; not billing data.",
    }


@app.get(f"{settings.api_prefix}/analytics/trends")
def call_trends(current: Current) -> dict[str, Any]:
    return {"organization_id": current.organization_id, "items": [{"date": f"2026-07-{day:02d}", "calls": 42 + (day * 7) % 28, "bookings": 7 + (day * 3) % 11, "quality": 82 + (day % 8)} for day in range(1, 15)]}


@app.get(f"{settings.api_prefix}/analytics/funnel")
def funnel(db: Db, current: Current) -> dict[str, Any]:
    total = db.query(CallSession).filter(CallSession.organization_id == current.organization_id).count()
    return {"items": [{"stage": "Answered", "value": total}, {"stage": "Qualified", "value": int(total * 0.67)}, {"stage": "Booked", "value": int(total * 0.38)}, {"stage": "Resolved by AI", "value": int(total * 0.71)}, {"stage": "Human handoff", "value": int(total * 0.29)}]}


@app.get(f"{settings.api_prefix}/analytics/quality")
def quality_metrics(db: Db, current: Current) -> dict[str, Any]:
    quality_ids = [row[0] for row in db.query(CallSession.id).filter(CallSession.organization_id == current.organization_id).all()]
    return {
        "flags": {
            "low_transcription_confidence": db.query(QualityEvaluation).filter(QualityEvaluation.call_id.in_(quality_ids), QualityEvaluation.transcript_completeness < 65).count(),
            "policy_review": db.query(QualityEvaluation).filter(QualityEvaluation.call_id.in_(quality_ids), QualityEvaluation.policy_risk == "medium").count(),
            "hallucination_risk": db.query(QualityEvaluation).filter(QualityEvaluation.call_id.in_(quality_ids), QualityEvaluation.hallucination_risk != "low").count(),
        },
        "latency": {"stt_ms": 210, "reasoning_ms": 310, "tts_ms": 222},
        "note": "All values use synthetic evaluation records and rule-assisted signals in demo mode.",
    }


@app.get(f"{settings.api_prefix}/analytics/agent-comparison")
def agent_comparison(db: Db, current: Current) -> dict[str, Any]:
    agents = db.query(VoiceAgent).filter(VoiceAgent.organization_id == current.organization_id).all()
    return {"items": [{"agent": agent.name, "volume": 44 + index * 8, "resolution_rate": 70 + index * 4, "qualification_rate": 62 + index * 5, "booking_rate": 28 + index * 3, "handoff_rate": 21 - index, "average_latency_ms": 690 + index * 30, "quality_score": 87 + index, "compliance_flags": index, "cost_estimate_usd": round(7.4 + index * 1.2, 2), "synthetic": True} for index, agent in enumerate(agents)]}


@app.get(f"{settings.api_prefix}/analytics/forecast")
def forecast(db: Db, current: Current) -> dict[str, Any]:
    volume = db.query(CallSession).filter(CallSession.organization_id == current.organization_id).count()
    return {
        "label": "Baseline forecast — trend-based projection — synthetic demo estimate",
        "expected_inbound_calls": int(volume / 7 * 1.08),
        "expected_appointments": int(volume / 7 * 0.34),
        "staffing_requirement": "2 supervisors during 10:00–14:00",
        "queue_risk": "moderate at 12:00–13:00",
        "method": "Explainable rolling average over synthetic seeded activity; no predictive-accuracy claim.",
    }


@app.get(f"{settings.api_prefix}/alerts")
def alerts(db: Db, current: Current, status: str | None = None) -> dict[str, Any]:
    query = db.query(Alert).filter(Alert.organization_id == current.organization_id)
    if status:
        query = query.filter(Alert.status == status)
    items = query.order_by(Alert.created_at.desc()).all()
    return {"items": [{"id": item.id, "category": item.category, "severity": item.severity, "title": item.title, "detail": item.detail, "status": item.status, "entity_type": item.entity_type, "entity_id": item.entity_id, "assignee": item.assignee, "created_at": item.created_at.isoformat()} for item in items]}


@app.post(f"{settings.api_prefix}/alerts/{{alert_id}}/action")
def alert_action(alert_id: str, payload: AlertActionInput, db: Db, current: Annotated[Principal, Depends(require_permissions("calls:read"))]) -> dict[str, Any]:
    alert = require_org_record(db.get(Alert, alert_id), current.organization_id, "Alert")
    if payload.action not in {"acknowledged", "snoozed", "resolved"}:
        raise HTTPException(status_code=422, detail="Unsupported alert action")
    alert.status = payload.action
    audit(db, current.organization_id, current.email, f"alert.{payload.action}", "alert", alert.id)
    db.commit()
    return {"id": alert.id, "status": alert.status}


@app.get(f"{settings.api_prefix}/notifications")
def notifications(db: Db, current: Current) -> dict[str, Any]:
    items = db.query(Notification).filter(Notification.organization_id == current.organization_id).order_by(Notification.created_at.desc()).all()
    return {"items": [{"id": item.id, "category": item.category, "title": item.title, "body": item.body, "read_at": item.read_at.isoformat() if item.read_at else None, "delivery": item.delivery} for item in items]}


@app.get(f"{settings.api_prefix}/reports")
def reports(db: Db, current: Annotated[Principal, Depends(require_permissions("reports:manage"))]) -> dict[str, Any]:
    items = db.query(Report).filter(Report.organization_id == current.organization_id).order_by(Report.created_at.desc()).all()
    return {"items": [{"id": item.id, "report_type": item.report_type, "title": item.title, "date_range": item.date_range, "generated_by": item.generated_by, "data_freshness": item.data_freshness, "content": item.content_json, "export_id": item.export_id, "created_at": item.created_at.isoformat()} for item in items]}


@app.post(f"{settings.api_prefix}/reports/generate", status_code=201)
def create_report(payload: ReportInput, db: Db, current: Annotated[Principal, Depends(require_permissions("reports:manage"))]) -> dict[str, Any]:
    report = generate_report(db, current.organization_id, payload.report_type, current.email)
    audit(db, current.organization_id, current.email, "report.generated", "report", report.id)
    db.commit()
    return {"id": report.id, "title": report.title, "content": report.content_json, "note": "Generated locally from synthetic demo data."}


@app.get(f"{settings.api_prefix}/reports/{{report_id}}/export")
def export_report(report_id: str, db: Db, current: Current, format: str = "pdf") -> Response:
    report = require_org_record(db.get(Report, report_id), current.organization_id, "Report")
    audit(db, current.organization_id, current.email, "report.exported", "report", report.id, {"format": format})
    db.commit()
    if format == "csv":
        rows = ["metric,value"] + [f"{key},{value}" for key, value in report.content_json.items() if not isinstance(value, (list, dict))]
        return PlainTextResponse("\n".join(rows), media_type="text/csv")
    pdf = minimal_pdf(report.title, "Synthetic demo report. " + str(report.content_json))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{report.export_id}.pdf"'})


@app.get(f"{settings.api_prefix}/reports/schedules")
def report_schedules(db: Db, current: Annotated[Principal, Depends(require_permissions("reports:manage"))]) -> dict[str, Any]:
    items = db.query(ScheduledReport).filter(ScheduledReport.organization_id == current.organization_id).all()
    return {"items": [{"id": item.id, "report_type": item.report_type, "cadence": item.cadence, "next_run_at": item.next_run_at.isoformat(), "destination": item.destination, "is_active": item.is_active} for item in items]}


@app.post(f"{settings.api_prefix}/reports/schedules", status_code=201)
def create_report_schedule(payload: ScheduleReportInput, db: Db, current: Annotated[Principal, Depends(require_permissions("reports:manage"))]) -> dict[str, Any]:
    schedule = ScheduledReport(id=f"schedule-{uuid4().hex[:12]}", organization_id=current.organization_id, **payload.model_dump(), is_active=True)
    db.add(schedule)
    audit(db, current.organization_id, current.email, "report.schedule_created", "scheduled_report", schedule.id)
    db.commit()
    return {"id": schedule.id, "next_run_at": schedule.next_run_at.isoformat(), "delivery": "in_app (simulated)"}


@app.post(f"{settings.api_prefix}/reports/schedules/{{schedule_id}}/run-now")
def run_report_now(schedule_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("reports:manage"))]) -> dict[str, Any]:
    schedule = require_org_record(db.get(ScheduledReport, schedule_id), current.organization_id, "Scheduled report")
    report = generate_report(db, current.organization_id, schedule.report_type, current.email)
    schedule.next_run_at = schedule.next_run_at + timedelta(days=7 if schedule.cadence == "weekly" else 1)
    audit(db, current.organization_id, current.email, "report.schedule_run_now", "scheduled_report", schedule.id, {"report_id": report.id})
    db.commit()
    return {"schedule_id": schedule.id, "report_id": report.id, "delivery": "in_app notification created; email delivery is a mock adapter unless configured."}


# ------------------- Providers, security, privacy, developer surface -------------------


@app.get(f"{settings.api_prefix}/providers")
def providers(db: Db, current: Annotated[Principal, Depends(require_permissions("providers:manage"))]) -> dict[str, Any]:
    items = db.query(ProviderConfig).filter(ProviderConfig.organization_id == current.organization_id).order_by(ProviderConfig.provider_type).all()
    return {"items": [{"id": item.id, "name": item.provider_name, "type": item.provider_type, "status": item.status, "environment": item.environment, "credential_state": item.credential_state, "last_health_check": item.last_health_check.isoformat() if item.last_health_check else None, "last_success_at": item.last_success_at.isoformat() if item.last_success_at else None, "failure_count": item.failure_count, "retry_policy": item.retry_policy, "settings": item.settings_json} for item in items]}


@app.post(f"{settings.api_prefix}/providers/{{provider_id}}/test")
def test_provider(provider_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("providers:manage"))]) -> dict[str, Any]:
    provider = require_org_record(db.get(ProviderConfig, provider_id), current.organization_id, "Provider")
    provider.last_health_check = datetime.utcnow()
    if provider.status == "demo_provider":
        provider.last_success_at = datetime.utcnow()
        outcome = "Local deterministic provider test passed."
    else:
        outcome = "Adapter boundary reachable in demo mode; no credentialed external request was made."
    audit(db, current.organization_id, current.email, "provider.health_checked", "provider", provider.id)
    db.commit()
    return {"provider_id": provider.id, "status": provider.status, "outcome": outcome}


@app.post(f"{settings.api_prefix}/providers/{{provider_id}}/action")
def provider_action(provider_id: str, payload: ProviderActionInput, db: Db, current: Annotated[Principal, Depends(require_permissions("providers:manage"))]) -> dict[str, Any]:
    provider = require_org_record(db.get(ProviderConfig, provider_id), current.organization_id, "Provider")
    if payload.status and payload.status not in {"disabled", "not_configured", "demo_provider"}:
        raise HTTPException(status_code=422, detail="Only safe demo statuses can be selected without credentials")
    provider.status = payload.status or ("disabled" if provider.status != "disabled" else "not_configured")
    audit(db, current.organization_id, current.email, "provider.status_changed", "provider", provider.id, {"status": provider.status})
    db.commit()
    return {"id": provider.id, "status": provider.status}


@app.get(f"{settings.api_prefix}/webhooks/deliveries")
def webhook_logs(db: Db, current: Annotated[Principal, Depends(require_permissions("providers:manage"))]) -> dict[str, Any]:
    items = db.query(WebhookDelivery).filter(WebhookDelivery.organization_id == current.organization_id).order_by(WebhookDelivery.created_at.desc()).all()
    return {"items": [{"id": item.id, "event": item.event_name, "destination": item.destination, "status": item.status, "attempts": item.attempts, "redacted_payload_preview": item.payload_preview, "failure_reason": item.failure_reason} for item in items]}


@app.get(f"{settings.api_prefix}/security/overview")
def security_overview(db: Db, current: Annotated[Principal, Depends(require_permissions("security:manage"))]) -> dict[str, Any]:
    active_keys = db.query(ApiKey).filter(ApiKey.organization_id == current.organization_id, ApiKey.revoked_at.is_(None)).count()
    recent_audits = db.query(AuditEvent).filter(AuditEvent.organization_id == current.organization_id).count()
    return {"security_posture": "Security controls designed to support enterprise deployment.", "active_api_keys": active_keys, "request_id_headers": True, "rate_limiting": True, "cors_configured": True, "sensitive_export_auditing": True, "audit_events": recent_audits, "certification_claim": "No certification claim is made."}


@app.get(f"{settings.api_prefix}/security/api-keys")
def list_api_keys(db: Db, current: Annotated[Principal, Depends(require_permissions("security:manage"))]) -> dict[str, Any]:
    keys = db.query(ApiKey).filter(ApiKey.organization_id == current.organization_id).order_by(ApiKey.created_at.desc()).all()
    return {"items": [{"id": key.id, "name": key.name, "prefix": key.key_prefix, "scopes": key.scopes, "expires_at": key.expires_at.isoformat() if key.expires_at else None, "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None, "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None} for key in keys]}


@app.post(f"{settings.api_prefix}/security/api-keys", status_code=201)
def create_api_key(payload: ApiKeyInput, db: Db, current: Annotated[Principal, Depends(require_permissions("security:manage"))]) -> dict[str, Any]:
    from app.security import _hash_token

    raw = f"vr_{uuid4().hex}{uuid4().hex[:8]}"
    key = ApiKey(
        id=f"api-key-{uuid4().hex[:12]}",
        organization_id=current.organization_id,
        name=payload.name,
        key_prefix=raw[:12],
        key_hash=_hash_token(raw),
        scopes=payload.scopes,
        expires_at=payload.expires_at,
    )
    db.add(key)
    audit(db, current.organization_id, current.email, "api_key.created", "api_key", key.id, {"scopes": payload.scopes})
    db.commit()
    return {"id": key.id, "api_key": raw, "warning": "Copy this value now. The demo returns it once and stores only a hash."}


@app.post(f"{settings.api_prefix}/security/api-keys/{{key_id}}/revoke")
def revoke_api_key(key_id: str, db: Db, current: Annotated[Principal, Depends(require_permissions("security:manage"))]) -> dict[str, str]:
    key = require_org_record(db.get(ApiKey, key_id), current.organization_id, "API key")
    key.revoked_at = datetime.utcnow()
    audit(db, current.organization_id, current.email, "api_key.revoked", "api_key", key.id)
    db.commit()
    return {"id": key.id, "status": "revoked"}


@app.get(f"{settings.api_prefix}/governance/retention-policies")
def retention_policies(db: Db, current: Annotated[Principal, Depends(require_permissions("governance:manage"))]) -> dict[str, Any]:
    items = db.query(RetentionPolicy).filter(RetentionPolicy.organization_id == current.organization_id).all()
    return {"items": [{"id": item.id, "name": item.name, "resource_type": item.resource_type, "retention_days": item.retention_days, "action": item.action, "legal_hold_enabled": item.legal_hold_enabled} for item in items]}


@app.post(f"{settings.api_prefix}/governance/retention-policies", status_code=201)
def create_retention_policy(payload: RetentionInput, db: Db, current: Annotated[Principal, Depends(require_permissions("governance:manage"))]) -> dict[str, Any]:
    policy = RetentionPolicy(id=f"retention-{uuid4().hex[:12]}", organization_id=current.organization_id, **payload.model_dump(), legal_hold_enabled=False)
    db.add(policy)
    audit(db, current.organization_id, current.email, "retention_policy.created", "retention_policy", policy.id)
    db.commit()
    return {"id": policy.id, "name": policy.name}


@app.get(f"{settings.api_prefix}/governance/deletion-requests")
def deletion_requests(db: Db, current: Annotated[Principal, Depends(require_permissions("governance:manage"))]) -> dict[str, Any]:
    items = db.query(DataDeletionRequest).filter(DataDeletionRequest.organization_id == current.organization_id).all()
    return {"items": [{"id": item.id, "requester_reference": item.requester_reference, "scope": item.scope, "status": item.status, "reason": item.reason} for item in items]}


@app.post(f"{settings.api_prefix}/governance/deletion-requests", status_code=201)
def create_deletion_request(payload: DeletionRequestInput, db: Db, current: Annotated[Principal, Depends(require_permissions("governance:manage"))]) -> dict[str, Any]:
    request = DataDeletionRequest(id=f"deletion-{uuid4().hex[:12]}", organization_id=current.organization_id, **payload.model_dump(), status="pending_review")
    db.add(request)
    audit(db, current.organization_id, current.email, "deletion_request.created", "deletion_request", request.id)
    db.commit()
    return {"id": request.id, "status": request.status}


# ------------------- Global search and platform operations -------------------


@app.get(f"{settings.api_prefix}/search")
def global_search(q: str, db: Db, current: Current, limit: int = Query(8, ge=1, le=20)) -> dict[str, Any]:
    needle = f"%{q}%"
    results: list[dict[str, Any]] = []
    for call in db.query(CallSession).filter(CallSession.organization_id == current.organization_id, CallSession.caller_name.ilike(needle)).limit(limit).all():
        results.append({"type": "call", "id": call.id, "title": redact_pii(call.caller_name), "meta": f"{call.status} · {call.outcome}", "status": call.status})
    for lead in db.query(Lead).filter(Lead.organization_id == current.organization_id, Lead.name.ilike(needle)).limit(limit).all():
        results.append({"type": "lead", "id": lead.id, "title": redact_pii(lead.name), "meta": f"{lead.status} · score {lead.score}", "status": lead.status})
    for agent in db.query(VoiceAgent).filter(VoiceAgent.organization_id == current.organization_id, VoiceAgent.name.ilike(needle)).limit(limit).all():
        results.append({"type": "agent", "id": agent.id, "title": agent.name, "meta": agent.use_case, "status": agent.status})
    for report in db.query(Report).filter(Report.organization_id == current.organization_id, Report.title.ilike(needle)).limit(limit).all():
        results.append({"type": "report", "id": report.id, "title": report.title, "meta": report.report_type, "status": "ready"})
    for alert in db.query(Alert).filter(Alert.organization_id == current.organization_id, Alert.title.ilike(needle)).limit(limit).all():
        results.append({"type": "alert", "id": alert.id, "title": alert.title, "meta": alert.category, "status": alert.status})
    return {"items": results[:limit], "organization_id": current.organization_id}


@app.get(f"{settings.api_prefix}/platform/operations")
def platform_operations(db: Db, current: Annotated[Principal, Depends(require_permissions("workspace:manage"))]) -> dict[str, Any]:
    providers = db.query(ProviderConfig).filter(ProviderConfig.organization_id == current.organization_id).all()
    jobs = db.query(IntegrationJob).filter(IntegrationJob.organization_id == current.organization_id).all()
    return {
        "health": {"api": "healthy", "database": "healthy", "redis": "configured_boundary", "websocket": "healthy", "simulation_engine": "healthy", "worker": "boundary_active"},
        "telemetry": {
            "calls_processed": db.query(CallSession).filter(CallSession.organization_id == current.organization_id).count(),
            "active_calls": db.query(CallSession).filter(CallSession.organization_id == current.organization_id, CallSession.status.in_(["queued", "ringing", "connected", "listening", "reasoning", "speaking"])) .count(),
            "average_event_stream_latency_ms": 160,
            "crm_job_queue": len([job for job in jobs if job.job_type == "crm_sync" and job.status != "succeeded"]),
            "report_queue": 0,
            "provider_failures": sum(provider.failure_count for provider in providers),
            "synthetic_demo_cost_estimate_usd": 42.80,
        },
        "notes": ["Redis and worker status are architectural boundaries in local SQLite mode.", "No carrier or external provider status is claimed."],
    }


@app.get(f"{settings.api_prefix}/health/ready")
def readiness(db: Db) -> dict[str, Any]:
    orgs = db.query(Organization).count()
    return {
        "status": "ready" if orgs else "degraded",
        "database": "connected",
        "organizations": orgs,
        "migration_boundary": "alembic",
        "sqlite_development_mode": settings.database_url.startswith("sqlite"),
        "production_sqlite_allowed": settings.environment == "development" or not settings.database_url.startswith("sqlite"),
    }


@app.get(f"{settings.api_prefix}/platform/database")
def database_status(db: Db, current: Current) -> dict[str, Any]:
    return {
        "database_url_mode": "sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
        "tables_ready": True,
        "organizations": db.query(Organization).count(),
        "calls": db.query(CallSession).count(),
        "events": db.query(CallEvent).count(),
        "last_seed": "idempotent demo seed on startup",
        "migration_status": "head assumed after alembic upgrade",
    }


@app.get(f"{settings.api_prefix}/platform/trace/{{call_id}}")
def trace_view(call_id: str, db: Db, current: Current) -> dict[str, Any]:
    call = require_org_record(db.get(CallSession, call_id), current.organization_id, "Call")
    return {
        "trace_id": call.metadata_json.get("trace_id", f"trace-{call.id}"),
        "call": call_dict(call),
        "events": [e.payload | {"id": e.id, "event_type": e.event_type} for e in db.query(CallEvent).filter(CallEvent.call_id == call.id, CallEvent.organization_id == current.organization_id).order_by(CallEvent.occurred_at).all()],
        "transcripts": db.query(TranscriptSegment).filter(TranscriptSegment.call_id == call.id).count(),
        "entities": db.query(ExtractedEntity).filter(ExtractedEntity.call_id == call.id, ExtractedEntity.organization_id == current.organization_id).count(),
        "crm_jobs": [job_dict(j) for j in db.query(IntegrationJob).filter(IntegrationJob.organization_id == current.organization_id, IntegrationJob.entity_type == "lead").limit(10).all()],
        "audit_events": db.query(AuditEvent).filter(AuditEvent.organization_id == current.organization_id, AuditEvent.entity_id == call.id).count(),
    }
