# Verification

Phase 3 verification performed in this environment.

## Passed

- Fresh Alembic migration from an empty SQLite database: passed.
- Idempotent seed command: passed.
- Seed verification after repeated local runs:
  - organizations: 3
  - calls: 244
  - transcript segments: 728
  - leads: 242
  - agent versions: 12
  - evaluation suites: 3
- Backend test suite: 10 passed.
- Ruff: passed for `apps/api/app` and `apps/api/tests`.
- MyPy: passed for `apps/api/app`.
- Web TypeScript check: passed.
- ESLint: passed.
- Next.js production build: passed with `NEXT_TELEMETRY_DISABLED=1`.
- API smoke test with live Uvicorn server: passed for `/health` and `/api/v1/auth/login`.
- WebSocket simulation is covered by backend integration tests and validates ordered Phase 3 event envelopes.
- CRM retry, calendar conflict, agent release stage/activate, API-key revocation, redacted call notes, readiness and trace endpoints are covered by tests.

## Blocked / not executed

- Docker Compose verification was not executed because Docker is not installed in this environment.
- Playwright browser execution was attempted, but Chromium was not installed. `npx playwright install chromium` failed because the environment could not resolve `cdn.playwright.dev` (`EAI_AGAIN`). The Playwright smoke test and screenshot script remain in the repository for a browser-capable environment.
- No real external providers were configured or tested. Telephony, STT, TTS, LLM, CRM, calendar and notification integrations beyond the local mocks remain optional provider boundaries.

## Known warnings

The backend test run emits deprecation warnings for `datetime.utcnow()` and FastAPI `on_event`. They are documented as future hardening items and do not affect the deterministic local workflows tested here.
