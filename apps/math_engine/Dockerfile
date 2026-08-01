FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY apps/math_engine ./apps/math_engine
COPY packages/shared-types ./packages/shared-types

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/math_engine"

EXPOSE 50051

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import grpc; print('gRPC server healthy')"

CMD ["python", "-m", "grpc_server"]
