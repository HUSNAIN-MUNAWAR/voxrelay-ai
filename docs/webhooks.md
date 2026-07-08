# Webhooks

Event names reserved by the integration boundary include `call.started`, `call.connected`, `call.completed`, `call.escalated`, `call.handoff_requested`, `lead.created`, `lead.qualified`, `appointment.booked`, `appointment.failed`, `crm.sync_failed`, `quality.reviewed`, `agent.version_activated`, `agent.version_rolled_back`, `policy.violation_detected`, `emergency.escalated` and `report.generated`.

Webhook delivery logs store a redacted payload preview, attempt, result and failure reason. Demo mode is a mock delivery surface; request signing, endpoint verification, retries and dead-letter handling must be completed for a live provider integration.
