# syntax=docker/dockerfile:1
#############################################################################
# FinSimAI — Backend Gateway (FastAPI Web Server + WebSocket)
# Multi-stage build: builder compiles deps + TS types → runtime slim image
#############################################################################

# ─── BUILDER ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/

# Copy the entire uv workspace so the lock file resolves correctly
COPY pyproject.toml uv.lock ./
COPY apps/ ./apps/
COPY packages/ ./packages/
COPY scripts/ ./scripts/

# Install only backend-gateway + its transitive deps; then generate TS types
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package finsim-backend-gateway \
    && uv run python scripts/generate_ts_types.py

# ─── RUNTIME ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual-env and application code from the builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/backend_gateway /app/apps/backend_gateway

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/backend_gateway" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://localhost:{p}/health/live', timeout=5)" || exit 1

CMD ["python", "-m", "main"]
