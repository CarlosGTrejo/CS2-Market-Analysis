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

# 1. Copy the bun binary directly from the official image
# Placing it in /usr/local/bin ensures it is automatically in the system PATH
COPY --from=oven/bun:latest /usr/local/bin/bun /usr/local/bin/bun

# Copy the compiled environment AND the compiled application code from the builder.
# This ensures we get the bytecode while leaving the infra/ directory behind.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/flows /app/flows
COPY --from=builder /app/pipelines /app/pipelines

# 2. Copy the dashboard source code into the production image
COPY dashboard /app/dashboard

# 3. Install dashboard dependencies using the copied bun binary
RUN cd /app/dashboard && bun install

# Pre-compile dbt dependencies to ensure a frictionless runtime
RUN dbt deps --project-dir /app/pipelines/transform

# Command to execute the main Prefect flow
CMD ["python", "flows/main_flow.py"]