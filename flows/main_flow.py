import os
from pathlib import Path

from prefect import flow, task
from prefect_dbt import PrefectDbtRunner, PrefectDbtSettings
from prefect_shell import ShellOperation

from pipelines.extract_load.ingest_market_data import run_ingest


@task(
    log_prints=True,
    retries=int(os.getenv("PREFECT_TASK_RETRIES", "3")),
    retry_delay_seconds=int(os.getenv("PREFECT_TASK_RETRY_DELAY", "60")),
    timeout_seconds=int(os.getenv("PREFECT_TASK_TIMEOUT", "7200")),  # Default 2 hours
)
def run_dlt_pipeline():
    """Extract and load market data using dlt."""
    print("Starting dlt ingest pipeline...")
    load_info = run_ingest()
    print(f"dlt pipeline completed: {load_info}")
    return load_info


@task(log_prints=True)
def run_dbt_transformations():
    """Run dbt transformations using PrefectDbtRunner."""
    print("Starting dbt transformations...")

    # Path to the dbt project folder
    default_dir = Path(__file__).parent.parent / "pipelines" / "transform"
    project_dir = Path(os.getenv("DBT_PROJECT_DIR", str(default_dir)))
    profiles_dir = Path(os.getenv("DBT_PROFILES_DIR", str(default_dir)))

    print(f"dbt project directory evaluated to: {project_dir}")
    print(f"dbt profiles directory evaluated to: {profiles_dir}")

    # Configure dbt settings to point to our project directory
    settings = PrefectDbtSettings(
        project_dir=project_dir,
        profiles_dir=profiles_dir,
    )

    runner = PrefectDbtRunner(settings=settings)

    # Invoke dbt build (runs tests, seeds, models, snapshots)
    result = runner.invoke(["build"])
    if not result.success:
        error_details = getattr(
            result, "exception", getattr(result, "stdout", str(result))
        )
        raise RuntimeError(f"dbt build failed with error:\n{error_details}")

    print("dbt transformations completed successfully.")
    return result


@task(log_prints=True, retries=2, retry_delay_seconds=30)
def build_dashboard():
    """Build Observable Framework dashboard using bun."""
    print("Starting dashboard build...")
    dashboard_dir = Path(__file__).parent.parent / "dashboard"

    with ShellOperation(
        commands=["bun run build"],
        working_dir=dashboard_dir,
        stream_output=True,
    ) as shell_operation:
        process = shell_operation.trigger()
        process.wait_for_completion()
        if process.return_code != 0:
            output = process.fetch_result()
            raise RuntimeError(
                f"Dashboard build failed with exit code {process.return_code}:\n{output}"
            )

    print(
        "Build complete. Removing oversized WASM files to bypass Cloudflare limits..."
    )
    dist_dir = dashboard_dir / "dist"

    # Hard delete ALL variations of the DuckDB WASM engine
    for wasm_path in dist_dir.rglob("duckdb-*.wasm"):
        print(f"Removing {wasm_path.relative_to(dashboard_dir)}...")
        wasm_path.unlink()

    print("Dashboard build successful.")


@task(log_prints=True, retries=2, retry_delay_seconds=60)
def deploy_dashboard():
    """Deploy the built dashboard to Cloudflare using Wrangler."""
    print("Deploying dashboard to Cloudflare via Workers Static Assets...")
    dashboard_dir = Path(__file__).parent.parent / "dashboard"

    with ShellOperation(
        commands=["wrangler deploy"],
        working_dir=dashboard_dir,
        stream_output=True,
    ) as shell_operation:
        process = shell_operation.trigger()
        process.wait_for_completion()

        if process.return_code != 0:
            output = process.fetch_result()
            raise RuntimeError(
                f"Dashboard deployment failed with exit code {process.return_code}:\n{output}"
            )

    print("Dashboard deployment successful.")


@flow(name="elt_market_data_flow", log_prints=True)
def elt_market_data_flow():
    """Orchestrates the ELT process: dlt extract/load -> dbt transform."""

    # 1. Run dlt extract and load
    dlt_result = run_dlt_pipeline()

    if getattr(dlt_result, "has_failed_jobs", False):
        failed_jobs = getattr(dlt_result, "failed_jobs", "Unknown error")
        raise RuntimeError(f"dlt pipeline failed to load some jobs:\n{failed_jobs}")

    # 2. Run dbt transformations strictly after the extract/load
    dbt_result = run_dbt_transformations(wait_for=[dlt_result])

    # 3. Build the dashboard after transformations are complete
    build_result = build_dashboard(wait_for=[dbt_result])

    # 4. Deploy to Cloudflare Workers after build is complete
    deploy_dashboard(wait_for=[build_result])


if __name__ == "__main__":
    elt_market_data_flow()
