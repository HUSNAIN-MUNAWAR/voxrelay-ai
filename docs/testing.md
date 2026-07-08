# Testing

Backend coverage exercises login, workspace switch, tenant isolation, deterministic simulation/WebSocket persistence, emergency routing/takeover, agent version release gates, CRM retry idempotency, calendar conflict handling, report export and scoped API key visibility.

Frontend checks use TypeScript, ESLint and Playwright smoke coverage. CI executes API quality/testing and web lint/typecheck/build/smoke jobs. Run `make test`, `make lint`, `make typecheck`, `make web-build`, and `make e2e`.
