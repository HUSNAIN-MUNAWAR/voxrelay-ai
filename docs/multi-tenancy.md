# Multi-tenancy and RBAC

Every critical Phase 2 record has an `organization_id`; tenant scope is enforced from JWT membership or a scoped API key, not a frontend selection. Calls, leads, appointments, agents, agent versions, reports, providers, alerts and audit events are fetched with organization predicates. `require_org_record` denies cross-tenant entity access.

```mermaid
sequenceDiagram
  participant U as User
  participant A as API
  participant M as Membership
  participant D as Tenant-scoped DB
  U->>A: JWT request / workspace switch
  A->>M: validate user + organization membership
  M-->>A: role + permissions
  A->>D: query WHERE organization_id = token.org
  D-->>A: scoped result only
```

| Role | Primary controls |
|---|---|
| Organization Admin | Workspace, users, APIs, providers, approvals, retention |
| Operations Manager | Calls, leads, calendars, routing, reports, analytics |
| Voice Agent Manager | Agent configuration, versions, evaluation, submission |
| Supervisor | Monitor, transfer, takeover, review, escalations |
| Quality Reviewer | Review, feedback, coaching, training examples |
| Scheduler | Calendar, booking/reschedule/cancel |
| Sales Representative | Assigned leads and follow-ups |
| Compliance Reviewer | Consent, risk, governance, reports |
| Viewer | Tenant-scoped read-only surfaces |

The test suite verifies calls, leads, agents and reports cannot be read from another workspace.
