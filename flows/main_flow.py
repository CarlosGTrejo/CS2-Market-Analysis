# Sample Prefect flow, SUBJECT TO CHANGE as we build out the pipelines and understand the dependencies better.

import os

from dbt.cli.main import dbtRunner, dbtRunnerResult

# Import your dlt pipeline logic from the pipelines/extract directory
from pipelines.extract.pipeline import run_rest_api_to_gcs
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact


@task(retries=2, retry_delay_seconds=60)
def extract_and_load_data():
    """
    Executes the dlt pipeline to pull from the REST API and load to GCS.
    """
    print("Starting dlt extraction...")

    # We call the function defined in pipelines/extract/pipeline.py
    load_info = run_rest_api_to_gcs()

    # Log the dlt load information to Prefect
    print(f"Extraction complete. dlt load info: {load_info}")
    return load_info


@task
def run_dbt_transformations():
    """
    Executes the dbt project programmatically to transform data in BigQuery.
    """
    print("Starting dbt transformations...")

    # Define the path to your dbt project
    dbt_project_dir = os.path.join(os.getcwd(), "pipelines", "transform")

    # Run dbt programmatically (dbt build runs models, tests, and snapshots)
    dbt = dbtRunner()
    cli_args = [
        "build",
        "--project-dir",
        dbt_project_dir,
        "--profiles-dir",
        dbt_project_dir,
    ]

    res: dbtRunnerResult = dbt.invoke(cli_args)

    if not res.success:
        raise Exception(f"dbt transformations failed: {res.exception}")

    print("dbt transformations completed successfully.")
    return True


@flow(name="Daily ELT Pipeline", log_prints=True)
def main_elt_flow():
    """
    The main orchestrator. It ensures extraction happens before transformation.
    """
    # Step 1: Extract from REST API and Load to GCS (dlt)
    load_status = extract_and_load_data()

    # Step 2: Transform data in BigQuery (dbt)
    # The `wait_for` argument ensures dbt doesn't run until dlt finishes successfully
    run_dbt_transformations(wait_for=[load_status])

    # Optional: Create a markdown artifact in the Prefect UI summarizing the run
    create_markdown_artifact(
        key="pipeline-summary",
        markdown=f"## ELT Run Complete 🎉\n- dlt pipeline status: OK\n- dbt models updated successfully.",
        description="Daily Pipeline Summary",
    )


if __name__ == "__main__":
    # You can test the entire flow locally by just running this script
    main_elt_flow()
