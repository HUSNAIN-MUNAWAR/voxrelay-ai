"""phase 3 operational indexes and readiness boundary

Revision ID: 0003_phase3_operational_indexes
Revises: 0002_phase2_enterprise
Create Date: 2026-07-08

This revision keeps the portable local demo schema while adding explicit indexes for
high-traffic, tenant-scoped operational reads. It does not claim zero-downtime
migration support; see docs/database-migrations.md for rollout and rollback notes.
"""

from alembic import op

revision = "0003_phase3_operational_indexes"
down_revision = "0002_phase2_enterprise"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_call_sessions_org_status_created", "call_sessions", ["organization_id", "status", "created_at"]),
    ("ix_call_events_org_call_created", "call_events", ["organization_id", "call_id", "occurred_at"]),
    ("ix_leads_org_status_created", "leads", ["organization_id", "status", "created_at"]),
    ("ix_appointments_org_assignee_start", "appointments", ["organization_id", "assignee", "start_time"]),
    ("ix_agent_versions_org_agent_status", "agent_versions", ["organization_id", "agent_id", "status"]),
    ("ix_integration_jobs_org_status_next", "integration_jobs", ["organization_id", "status", "next_retry_at"]),
    ("ix_alerts_org_status_severity", "alerts", ["organization_id", "status", "severity"]),
    ("ix_audit_events_org_entity_created", "audit_events", ["organization_id", "entity_type", "entity_id", "created_at"]),
]


def upgrade() -> None:
    for name, table, cols in INDEXES:
        op.create_index(name, table, cols, unique=False, if_not_exists=True)


def downgrade() -> None:
    for name, table, _cols in reversed(INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
