"""Durable local worker boundary for retry-safe integration and report jobs.

The demo intentionally avoids a paid queue/broker. In Compose, this process polls
persisted database job records and processes only local mock work. Redis remains a
future broker boundary; production deployments should replace the loop with a
supervised task system (Celery, Dramatiq, RQ, Arq, etc.) and observability.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from app.db import IntegrationJob, ScheduledReport, SessionLocal
from app.services.integrations import retry_mock_job
from app.services.reporting import generate_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
POLL_SECONDS = 10


def process_due_work() -> dict[str, int]:
    db = SessionLocal()
    processed_jobs = 0
    reports = 0
    try:
        due_jobs = (
            db.query(IntegrationJob)
            .filter(
                IntegrationJob.status.in_(["retrying", "failed"]),
                IntegrationJob.next_retry_at.is_not(None),
                IntegrationJob.next_retry_at <= datetime.utcnow(),
                IntegrationJob.provider == "local_mock_crm",
            )
            .all()
        )
        for job in due_jobs:
            retry_mock_job(db, job)
            processed_jobs += 1

        due_reports = (
            db.query(ScheduledReport)
            .filter(
                ScheduledReport.is_active.is_(True),
                ScheduledReport.next_run_at <= datetime.utcnow(),
            )
            .all()
        )
        for schedule in due_reports:
            generate_report(
                db, schedule.organization_id, schedule.report_type, "voxrelay.local_worker"
            )
            schedule.next_run_at = datetime.utcnow().replace(microsecond=0)
            db.commit()
            reports += 1
        return {"integration_jobs": processed_jobs, "reports": reports}
    finally:
        db.close()


def main() -> None:
    logging.info("VoxRelay durable local worker started; polling persisted mock jobs.")
    while True:
        result = process_due_work()
        if result["integration_jobs"] or result["reports"]:
            logging.info("Processed local work: %s", result)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
