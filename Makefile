.PHONY: dev build lint clean seed generate-types setup

# ─── Development ───────────────────────────────────────────
dev:
	docker compose up -d postgres redis
	cd apps/frontend && npm run dev

dev-backend:
	cd apps/backend_gateway && WS_LOCAL_MODE=true uv run uvicorn main:app --reload --ws wsproto

dev-math:
	cd apps/math_engine && uv run python http_server.py

dev-ai:
	cd apps/ai_engine && uv run python main_ai.py

# ─── Build ─────────────────────────────────────────────────
build:
	turbo build

# ─── Lint ──────────────────────────────────────────────────
lint:
	turbo lint
	ruff check apps/

# ─── Database ──────────────────────────────────────────────
seed:
	cd packages/database && uv run python ../../scripts/seed_db.py

migrate:
	cd packages/database && alembic upgrade head

# ─── Code Generation ──────────────────────────────────────
generate-types:
	cd scripts && uv run python generate_ts_types.py

# ─── Utilities ─────────────────────────────────────────────
setup:
	docker compose up -d
	cd apps/frontend && npm install
	uv sync

clean:
	docker compose down -v
	rm -rf apps/frontend/.next apps/frontend/node_modules
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
