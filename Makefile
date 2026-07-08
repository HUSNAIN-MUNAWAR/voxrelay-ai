.PHONY: api-install api-dev web-install web-dev worker test lint format typecheck web-build e2e seed migrate migrate-status screenshots verify

api-install:
	python -m pip install -e "apps/api[dev]"

api-dev:
	cd apps/api && uvicorn app.main:app --reload --port 8000

worker:
	cd apps/api && python -m app.worker

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

migrate:
	cd apps/api && alembic upgrade head

migrate-status:
	cd apps/api && python scripts/check_migrations.py

seed:
	cd apps/api && python -m app.seed_cli

test:
	cd apps/api && pytest -q

lint:
	cd apps/api && ruff check app tests
	cd apps/web && npm run lint

format:
	cd apps/api && ruff format app tests
	cd apps/web && npm run format

typecheck:
	cd apps/api && mypy app
	cd apps/web && npm run typecheck

web-build:
	cd apps/web && npm run build

screenshots:
	cd apps/web && node scripts/capture-phase3-screenshots.mjs

e2e:
	cd apps/web && npx playwright test

verify: test lint typecheck web-build
