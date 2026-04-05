# TODO: verify and finish this deployment script.
# Import your actual main flow function from your flows directory
import json
import os
import subprocess

from main_flow import elt_market_data_flow
from prefect.deployments import DeploymentImage


def get_pulumi_outputs() -> dict[str, str]:
    """Fetch outputs from pulumi stack natively via CLI subprocess."""
    try:
        # Assumes the user runs deploy.py from the root of the repo mostly.
        # Ensure we target the 'infra' pulumi project.
        result = subprocess.run(
            ["pulumi", "stack", "output", "--json", "-C", "infra"],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(
            f"Failed to fetch pulumi stack outputs. Make sure pulumi is logged in and stack is active.\n{e.stderr}"
        )
        raise


if __name__ == "__main__":
    # Pull the Artifact Registry path from your .env file to keep it reproducible
    # Example format: us-central1-docker.pkg.dev/your-project-id/cs2-repo/cs2-image
    image_url = os.getenv("ARTIFACT_REGISTRY_IMAGE_URL")
    stack = os.getenv("PULUMI_STACK", "dev")
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")

    if not image_url:
        raise ValueError("ARTIFACT_REGISTRY_IMAGE_URL is missing from your .env file.")
    if not gcp_project:
        raise ValueError("GOOGLE_CLOUD_PROJECT is missing from your .env file.")

    # Dynamically resolve dataset and bucket URL to avoid hardcoded naming drift
    pulumi_outputs = get_pulumi_outputs()
    bucket_url = pulumi_outputs.get("gcs_bucket_url")
    if bucket_url:
        bucket_url += "/dlt_staging"
    bq_dataset_name = pulumi_outputs.get("bq_dataset_name")

    if not bucket_url or not bq_dataset_name:
        raise ValueError(
            "Failed to retrieve gcs_bucket_url or bq_dataset_name from Pulumi state."
        )

    work_pool_name = f"cs2-push-pool-{stack}"

    print(f"Building and pushing image to: {image_url}")
    print(f"Targeting Work Pool: {work_pool_name}")
    print(f"Injecting GCS Staging Bucket: {bucket_url}")
    print(f"Injecting BQ Dataset Name: {bq_dataset_name}")

    # Deploy the flow
    elt_market_data_flow.deploy(
        name=f"cs2-cloud-run-deployment-{stack}",
        work_pool_name=work_pool_name,
        image=DeploymentImage(name=image_url, tag="latest", dockerfile="Dockerfile"),  # type: ignore
        build=True,
        push=True,
        cron="0 0 * * *",
        job_variables={
            "env": {
                "PULUMI_STACK": stack,
                "GOOGLE_CLOUD_PROJECT": gcp_project,
                "GOOGLE_CLOUD_REGION": os.getenv("GOOGLE_CLOUD_REGION", ""),
                "DESTINATION__FILESYSTEM__BUCKET_URL": bucket_url,
                "BQ_DATASET_NAME": bq_dataset_name,
                "PROXY_TOKEN": os.getenv("PROXY_TOKEN", ""),
                "PROXY_URL": os.getenv("PROXY_URL", ""),
            }
        },
    )
