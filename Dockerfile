# TODO: Finish and optimize this dockerfile.
FROM python:3.14-slim

# Add uv to the image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Optimize python environment compilation and linking
ENV UV_COMPILE_BYTECODE=1

# Ensure correct module resolution and uv env in PATH
ENV PYTHONPATH="/app"
ENV PATH="/app/.venv/bin:$PATH"

# Copy dependency manifests AND the local SDK folder (required for uv to resolve the lockfile)
# Note: we ignore .python-version if we want the builder to use the container's version directly, but if kept, uv uses it safely.
COPY pyproject.toml .python-version* uv.lock ./
COPY infra/sdks/ infra/sdks/

# Sync dependencies EXCLUDING the dev group (stripping out Pulumi and infrastructure bloat)
RUN uv sync --locked --no-dev --no-install-project

# Copy your actual data engineering pipeline code
COPY flows/ flows/
COPY pipelines/ pipelines/

# (Optional) If dbt requires a specific profiles directory, point to it here:
ENV DBT_PROFILES_DIR=/app/pipelines/transform

# Pre-compile dbt dependencies to ensure a frictionless runtime
# Note: Fails gracefully if no packages.yml is present, but ensures we don't need runtime network calls if one is added
RUN dbt deps --project-dir /app/pipelines/transform || true

# NO ENTRYPOINT REQUIRED
# Prefect's Cloud Run Push work pool will automatically supply the execution command.