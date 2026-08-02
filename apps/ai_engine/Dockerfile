# syntax=docker/dockerfile:1
#############################################################################
# FinSimAI — AI Engine (FastAPI Web API + ARQ Async Task Worker)
# Chạy đồng thời API + worker trong cùng một container (free tier Render
# chỉ hỗ trợ web services, không cho private/background worker riêng).
# Entry: ./start.sh (python -m main_ai & python -m tasks.worker & wait)
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

RUN chmod +x /app/start.sh

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/apps/ai_engine" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# FastAPI luôn chạy trong container → health check qua HTTP /health/live
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://localhost:{p}/health/live', timeout=5)" || exit 1

CMD ["sh", "/app/start.sh"]
