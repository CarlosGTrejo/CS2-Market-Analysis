# ==========================================
# Stage 1: Python Builder
# ==========================================
FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie-slim AS py-builder
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY flows/ flows/
COPY pipelines/ pipelines/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Resolve dbt dependencies in the builder stage
RUN /app/.venv/bin/dbt deps --project-dir /app/pipelines/transform

# ==========================================
# Stage 2: JS Dependencies Cache
# ==========================================
FROM oven/bun:latest AS js-builder
WORKDIR /app/dashboard

# Install deps, leveraging layer caching for fast rebuilds.
COPY dashboard/package.json dashboard/bun.lock* ./
RUN bun install --frozen-lockfile

# Copy the rest of the source code
COPY dashboard/ ./

# ==========================================
# Stage 3: Runner (Production Image)
# ==========================================
FROM python:3.13-slim
WORKDIR /app

ENV WRANGLER_SEND_METRICS=false

ENV PYTHONPATH="/app"
# We add /app/dashboard/node_modules/.bin so 'wrangler' works natively
ENV PATH="/app/dashboard/node_modules/.bin:/app/.venv/bin:$PATH"
ENV DBT_PROFILES_DIR=/app/pipelines/transform

# 1. Copy Node (for Wrangler because bun doesn't execute it correctly) AND Bun (for Prefect)
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=oven/bun:latest /usr/local/bin/bun /usr/local/bin/bun

# 2. Copy the compiled Python environment
COPY --from=py-builder /app/.venv /app/.venv

# 3. Copy the dashboard (now contains source code + installed node_modules)
COPY --from=js-builder /app/dashboard /app/dashboard

# 4. Copy the Python application code last (now includes downloaded dbt packages)
COPY --from=py-builder /app/flows /app/flows
COPY --from=py-builder /app/pipelines /app/pipelines

CMD ["python", "flows/main_flow.py"]