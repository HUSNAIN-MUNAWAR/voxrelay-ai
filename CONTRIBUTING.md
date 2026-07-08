# Contributing to VoxRelay AI

Thanks for considering a contribution. VoxRelay AI is intended to be a credible, runnable reference for governed voice operations, so changes should preserve that bar.

## Ground rules

- Keep all demo content synthetic. Do not add real customer data, credentials, call recordings, or private infrastructure details.
- Preserve the no-paid-keys local path. A contributor should be able to run the core demo with deterministic local data.
- Document integration boundaries honestly. If a provider adapter is incomplete or mocked, say so in code comments and docs.
- Add or update tests for tenant isolation, release governance, irreversible state changes, and API surface changes.

## Local setup

Backend:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e "apps/api[dev]"
cd apps/api
..\..\.venv\Scripts\python -m alembic upgrade head
```

Frontend:

```powershell
cd apps/web
npm ci
```

If you prefer the documented cross-platform flow, use the commands in [README.md](README.md).

## Development workflow

1. Create a focused branch.
2. Make the smallest coherent change that solves the problem.
3. Run the relevant checks before opening a pull request.
4. Update docs or screenshots when the visible product behavior changes.

## Recommended checks

```powershell
cd apps/api
..\..\.venv\Scripts\python -m pytest -q tests
..\..\.venv\Scripts\python -m ruff check app tests
..\..\.venv\Scripts\python -m mypy app
cd apps/web
npm run lint
npm run typecheck
npm run build
```

## Pull requests

- Describe what changed and why.
- Call out any limitations, skipped checks, or environment-specific constraints.
- Include updated screenshots for meaningful UI changes.
- Keep commit messages clear and production-friendly.
