# API guide

All Phase 2 APIs sit under `/api/v1`. Requests use `Authorization: Bearer <access_token>` or a scoped `X-API-Key`. List endpoints return tenant-scoped `items`; sensitive actions enforce role permissions.

Core groups: authentication/workspace, agents/versions/release, calls/WebSocket/takeover, leads/CRM jobs, appointments, review/rubrics/coaching, queues/routing, analytics, reports, providers, security, retention and global search.

The FastAPI OpenAPI interface at `/docs` is the canonical local schema. Client code should send idempotency keys for external-action-like requests such as CRM delivery.
