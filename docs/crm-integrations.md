# CRM integration reliability

The local mock CRM flow is implemented: a lead sync creates an idempotent integration job, a simulated failure can be recorded, a retry safely reuses the job, delivery attempts are stored and audit events preserve context. The lead remains stored locally after failure.

```mermaid
sequenceDiagram
  participant L as Lead
  participant A as API
  participant J as Integration Job
  participant C as Local Mock CRM
  L->>A: sync (idempotency key)
  A->>J: create/reuse job
  J->>C: simulated delivery
  C-->>J: failed or succeeded
  J->>A: status + attempt record
  A->>J: retry when requested
```

HubSpot, Salesforce, Zoho and generic webhook providers are optional adapter boundaries only.
