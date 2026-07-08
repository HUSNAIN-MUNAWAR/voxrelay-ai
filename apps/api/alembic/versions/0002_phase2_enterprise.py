"""phase 2 enterprise tables

Revision ID: 0002_phase2_enterprise
Revises: 0001_initial
Create Date: 2026-07-07

The Phase 1 migration intentionally used SQLAlchemy metadata creation. This migration
extends that same portable development approach to create Phase 2 tables when the
repository is upgraded in-place. Production deployments should generate explicit DDL
from this metadata as part of their migration review process.
"""

from alembic import op
from app.db import Base

revision = "0002_phase2_enterprise"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Reversing selectively would risk deleting Phase 1 data. Local demo resets use seed_cli.
    pass
