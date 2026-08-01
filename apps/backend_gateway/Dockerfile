FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY apps/backend_gateway ./apps/backend_gateway
COPY packages/shared-types ./packages/shared-types
COPY scripts ./scripts

RUN uv sync --frozen --no-dev
RUN uv run python scripts/generate_ts_types.py

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/backend_gateway"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uv", "run", "python", "-m", "apps.backend_gateway.main"]
