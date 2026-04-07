import os

from main_flow import elt_market_data_flow
from prefect.docker import DockerImage
from pulumi import automation as auto


def get_pulumi_outputs(stack: str) -> dict[str, str]:
    """Fetch outputs from pulumi stack using the native Python Automation API."""
    try:
        # Assumes the user runs deploy.py from the root of the repo mostly.
        # Select the local stack in the 'infra' directory
        stack_obj = auto.select_stack(
            stack_name=stack,
            work_dir="infra",
        )
        outputs = stack_obj.outputs()
        return {key: str(val.value) for key, val in outputs.items()}
    except Exception as e:
        print(
            f"Failed to fetch pulumi stack outputs. Make sure pulumi is logged in and stack '{stack}' exists.\n{e}"
        )
        raise


if __name__ == "__main__":
    # Pull the Artifact Registry path from your .env file to keep it reproducible
    # Example format: us-central1-docker.pkg.dev/your-project-id/cs2-repo/cs2-image
    image_url = os.getenv("ARTIFACT_REGISTRY_IMAGE_URL")
    stack = os.getenv("PULUMI_STACK", "dev")
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    gcp_region = os.getenv("GOOGLE_CLOUD_REGION", "us-central1")
    proxy_url = os.getenv("PROXY_URL")

    if not image_url:
        raise ValueError("ARTIFACT_REGISTRY_IMAGE_URL is missing from your .env file.")
    if not gcp_project:
        raise ValueError("GOOGLE_CLOUD_PROJECT is missing from your .env file.")
    if not proxy_url:
        raise ValueError("PROXY_URL is missing from your .env file.")

    # Dynamically resolve dataset and bucket URL to avoid hardcoded naming drift
    pulumi_outputs = get_pulumi_outputs(stack)
    bucket_url = pulumi_outputs.get("gcs_bucket_url")
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
        image=DockerImage(name=image_url, tag="latest", dockerfile="Dockerfile"),
        build=True,
        push=True,
        cron="0 0 * * *",
        job_variables={
            "env": {
                "PULUMI_STACK": stack,
                "GOOGLE_CLOUD_PROJECT": gcp_project,
                "GOOGLE_CLOUD_REGION": gcp_region,
                "DESTINATION__FILESYSTEM__BUCKET_URL": bucket_url,
                "DESTINATION__BIGQUERY__LOCATION": gcp_region,
                "BQ_DATASET_NAME": bq_dataset_name,
                "PROXY_URL": proxy_url,
            }
        },
    )
