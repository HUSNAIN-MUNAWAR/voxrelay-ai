from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db import AuditEvent, IntegrationJob, Lead, WebhookDelivery
from app.services.redaction import redact_pii


def enqueue_mock_crm_sync(
    db: Session,
    organization_id: str,
    lead: Lead,
    idempotency_key: str,
    simulate_failure: bool = False,
) -> IntegrationJob:
    existing = (
        db.query(IntegrationJob).filter(IntegrationJob.idempotency_key == idempotency_key).first()
    )
    if existing:
        return existing
    status = "failed" if simulate_failure else "succeeded"
    attempts = 3 if simulate_failure else 1
    job = IntegrationJob(
        id=f"job-{uuid4().hex[:12]}",
        organization_id=organization_id,
        job_type="crm_sync",
        provider="local_mock_crm",
        entity_type="lead",
        entity_id=lead.id,
        idempotency_key=idempotency_key,
        status=status,
        attempts=attempts,
        max_attempts=3,
        next_retry_at=datetime.utcnow() + timedelta(minutes=5) if simulate_failure else None,
        last_error="Synthetic local CRM failure requested" if simulate_failure else "",
        payload={
            "lead_id": lead.id,
            "name": redact_pii(lead.name),
            "phone": redact_pii(lead.phone),
            "synthetic": True,
        },
    )
    db.add(job)
    db.add(
        WebhookDelivery(
            id=f"webhook-{uuid4().hex[:12]}",
            organization_id=organization_id,
            event_name="crm.sync_failed" if simulate_failure else "lead.created",
            destination="local://mock-crm",
            status="retrying" if simulate_failure else "delivered",
            attempts=attempts,
            payload_preview=str(job.payload),
            failure_reason=job.last_error,
        )
    )
    db.add(
        AuditEvent(
            id=f"audit-{uuid4().hex[:10]}",
            organization_id=organization_id,
            actor="voxrelay.local_mock_crm",
            action="crm.sync_failed" if simulate_failure else "crm.sync_succeeded",
            entity_type="lead",
            entity_id=lead.id,
            detail={"job_id": job.id, "idempotency_key": idempotency_key, "synthetic": True},
        )
    )
    lead.crm_sync_status = "retrying" if simulate_failure else "synced"
    db.commit()
    db.refresh(job)
    return job


def retry_mock_job(db: Session, job: IntegrationJob) -> IntegrationJob:
    if job.status == "succeeded":
        return job
    job.attempts += 1
    job.status = "succeeded"
    job.last_error = ""
    job.next_retry_at = None
    lead = db.get(Lead, job.entity_id) if job.entity_type == "lead" else None
    if lead:
        lead.crm_sync_status = "synced"
    db.add(
        AuditEvent(
            id=f"audit-{uuid4().hex[:10]}",
            organization_id=job.organization_id,
            actor="demo.operator",
            action="crm.retry_succeeded",
            entity_type="integration_job",
            entity_id=job.id,
            detail={
                "attempt": job.attempts,
                "idempotency_key": job.idempotency_key,
                "synthetic": True,
            },
        )
    )
    db.commit()
    db.refresh(job)
    return job
