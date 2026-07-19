# Backend image (FastAPI + uv).
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install dependencies first (cached layer), then the project.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker/entrypoint.sh ./docker/entrypoint.sh
RUN uv sync --frozen --no-dev

EXPOSE 8000
ENTRYPOINT ["bash", "/app/docker/entrypoint.sh"]
