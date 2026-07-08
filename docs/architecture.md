# Architecture

VoxRelay AI separates the local deterministic experience from optional production provider boundaries. The API is the organization-scoped source of truth for calls, events, transcript segments, evidence, leads, appointments, governance records, jobs, reports and audit history.

```mermaid
flowchart TB
  Web[Next.js operations console] --> API[FastAPI /api/v1]
  API --> Auth[JWT, memberships, scoped API keys]
  API --> DB[(SQLite local / PostgreSQL)]
  API --> WS[Authenticated WebSocket stream]
  API --> Sim[Deterministic simulator]
  Sim --> Events[Call events / transcript / entities]
  API --> Jobs[Integration job records]
  Jobs --> CRM[Local mock CRM or optional adapter]
  Jobs --> Cal[Local calendar or optional adapter]
  API --> Redis[Redis worker boundary]
```

In demo mode, the deterministic simulator is fully functional and default. External provider records are explicit status/configuration boundaries and do not initiate paid traffic without credentials and an adapter implementation.
