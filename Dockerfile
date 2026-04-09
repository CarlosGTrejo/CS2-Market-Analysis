# ==========================================
# Stage 1: Builder
# ==========================================
FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie-slim AS builder
WORKDIR /app

# Optimize python environment compilation and linking
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Copy workspace members strictly to satisfy uv workspace validation
COPY infra/sdks/ infra/sdks/

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Sync dependencies EXCLUDING the dev group
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy pipeline code so uv can compile the bytecode for these files
COPY flows/ flows/
COPY pipelines/ pipelines/

# Final sync to compile bytecode for the copied source files
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ==========================================
# Stage 2: Runner (Production Image)
# ==========================================
FROM python:3.13-slim
WORKDIR /app

# Ensure correct module resolution and pre-compiled env in PATH
ENV PYTHONPATH="/app"
ENV PATH="/app/.venv/bin:$PATH"

# Set the dbt profiles directory so dbt knows where to find profiles.yml
ENV DBT_PROFILES_DIR=/app/pipelines/transform

# (Optional but recommended): If any of your dbt packages in packages.yml 
# pull directly from a GitHub URL instead of the dbt Hub, you must install git.
# RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy the compiled environment AND the compiled application code from the builder.
# This ensures we get the bytecode while leaving the infra/ directory behind.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/flows /app/flows
COPY --from=builder /app/pipelines /app/pipelines

# Pre-compile dbt dependencies to ensure a frictionless runtime
RUN dbt deps --project-dir /app/pipelines/transform

# NO ENTRYPOINT REQUIRED
# Prefect's Cloud Run Push work pool will automatically supply the execution command.