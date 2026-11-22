from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import Alert, CallSession, Notification, QualityEvaluation, Report


def generate_report(db: Session, organization_id: str, report_type: str, actor: str) -> Report:
    total_calls = (
        db.query(CallSession).filter(CallSession.organization_id == organization_id).count()
    )
    average_quality = (
        db.query(func.avg(QualityEvaluation.quality_score))
        .join(CallSession, CallSession.id == QualityEvaluation.call_id)
        .filter(CallSession.organization_id == organization_id)
        .scalar()
        or 0
    )
    open_alerts = (
        db.query(Alert)
        .filter(Alert.organization_id == organization_id, Alert.status == "open")
        .count()
    )
    report = Report(
        id=f"report-{uuid4().hex[:12]}",
        organization_id=organization_id,
        report_type=report_type,
        title=f"{report_type} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        date_range="Synthetic demo current dataset",
        generated_by=actor,
        data_freshness="Synthetic demo data; deterministic local environment",
        content_json={
            "total_calls": total_calls,
            "average_quality": round(float(average_quality), 1),
            "open_alerts": open_alerts,
            "notices": [
                "This report uses synthetic demo data.",
                "Local mock provider deliveries are not external production deliveries.",
            ],
        },
        export_id=f"export-{uuid4().hex[:10]}",
    )
    db.add(report)
    db.add(
        Notification(
            id=f"notification-{uuid4().hex[:12]}",
            organization_id=organization_id,
            user_id=None,
            category="report_generated",
            title="Report generated",
            body=f"{report_type} is available in the Reporting Center. Local in-app notification only.",
            delivery="in_app",
        )
    )
    db.commit()
    db.refresh(report)
    return report


def minimal_pdf(title: str, body: str) -> bytes:
    """Generate a tiny text-only PDF without claiming a full document rendering service."""
    safe_title = (
        title.replace("(", "[").replace(")", "]").encode("ascii", "replace").decode("ascii")[:96]
    )
    safe_body = (
        body.replace("(", "[").replace(")", "]").encode("ascii", "replace").decode("ascii")[:500]
    )
    stream = f"BT /F1 16 Tf 50 760 Td ({safe_title}) Tj 0 -28 Td /F1 10 Tf ({safe_body}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref_offset = sum(len(part) for part in parts)
    xref = [f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"]
    xref.extend(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    trailer = f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    parts.append("".join(xref).encode("latin-1"))
    parts.append(trailer.encode("latin-1"))
    return b"".join(parts)
