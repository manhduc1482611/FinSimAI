# syntax=docker/dockerfile:1
#############################################################################
# FinSimAI — AI Engine (FastAPI Web API + ARQ Async Task Worker)
# Single multi-stage image. Role selected at runtime via AI_ENGINE_ROLE:
#   worker (default) → ARQ background worker  (CMD: python -m tasks.worker)
#   api              → FastAPI web server      (CMD: python -m main_ai)
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

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package finsim-ai-engine

# ─── RUNTIME ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/ai_engine /app/apps/ai_engine

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/ai_engine" \
    PYTHONUNBUFFERED=1 \
    AI_ENGINE_ROLE=worker

EXPOSE 8000

# Worker: process-alive check.  API: HTTP health endpoint check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,sys,urllib.request; r=os.environ.get('AI_ENGINE_ROLE','worker'); sys.exit(0) if r=='worker' else urllib.request.urlopen('http://localhost:'+os.environ.get('PORT','8000')+'/health/live', timeout=5)" || exit 1

CMD ["python", "-m", "tasks.worker"]
