
# Agent Builder

VoxRelay AI Phase 3 is a production-oriented reference implementation. This document describes the implemented local deterministic path, the optional provider boundary, and the honest operational limits.

## Implemented local behavior

- Tenant-scoped FastAPI endpoints under `/api/v1`.
- Synthetic demo seed data for Northstar Property Group, CareBridge Clinics and Apex Home Services.
- Deterministic call simulation, persisted events, transcript segments, entity evidence, quality records, alerts, reports and audits.
- Local mock CRM/calendar/reporting behavior where relevant.

## Production boundary

Before production use, replace local defaults with managed PostgreSQL, Redis, object storage, centralized logging/metrics, a secrets manager, reviewed migrations, provider credentials, access reviews and incident response runbooks.

## Limitations

No live carrier telephony, real STT/TTS/LLM, real CRM, real calendar sync, compliance certification or real customer metrics are claimed by this repository.
