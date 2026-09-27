# Read-only GridLock API for hosting (Railway, Render, Fly). It serves the committed payload, so the
# image needs no PDFs, network or database: only backend/, config/ and data/output/.
# Build from the repository root: docker build -t gridlock-api .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

WORKDIR /app/backend
# Dependencies first, so code-only changes reuse this layer.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY config /app/config
COPY data/output /app/data/output
COPY backend ./
RUN uv sync --frozen --no-dev

# The host supplies PORT; when it doesn't, `gridlock serve` falls back to api.port in config/gridlock.yaml.
ENV GRIDLOCK_API_HOST=0.0.0.0
CMD ["sh", "-c", "GRIDLOCK_API_PORT=\"${PORT:-}\" exec .venv/bin/gridlock serve"]
