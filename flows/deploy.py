import os

from google.cloud import run_v2
from pulumi import automation as auto
from python_on_whales import docker
from python_on_whales.exceptions import DockerException


def get_pulumi_outputs(stack: str) -> dict[str, str]:
    """Fetch outputs from pulumi stack using the native Python Automation API."""
    try:
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


def update_cloud_run_job(
    project: str, location: str, job_name: str, full_image_url: str
):
    """Updates the Cloud Run Job template with the newly pushed image."""
    client = run_v2.JobsClient()
    job_path = client.job_path(project, location, job_name)

    # Fetch existing job definition
    job = client.get_job(name=job_path)

    # Update the container image
    job.template.template.containers[0].image = full_image_url

    print(f"Updating Cloud Run Job '{job_name}' to use image: {full_image_url}...")
    operation = client.update_job(job=job)
    operation.result()  # Wait for the operation to complete
    print(f"Successfully updated Cloud Run Job '{job_name}'.")


if __name__ == "__main__":
    stack = os.getenv("PULUMI_STACK", "dev")

    pulumi_outputs = get_pulumi_outputs(stack)
    registry_url = pulumi_outputs.get("artifact_registry_url")
    cloud_run_job_name = pulumi_outputs.get("cloud_run_job_name")
    cloud_run_job_location = pulumi_outputs.get("cloud_run_job_location")

    gcp_project = os.getenv("GOOGLE_PROJECT")
    gcp_region = os.getenv("GOOGLE_REGION", "us-central1")
    image_tag = os.getenv("IMAGE_TAG", "rev-1")

    if not registry_url:
        registry_url = os.getenv("ARTIFACT_REGISTRY_IMAGE_URL")
    if not registry_url:
        raise ValueError("Artifact registry URL is missing.")
    if not gcp_project:
        raise ValueError("GOOGLE_PROJECT is missing from your .env file.")
    if not cloud_run_job_name:
        raise ValueError("Cloud Run Job Name missing from Pulumi outputs.")

    full_image_url = f"{registry_url}/cs2-market-analysis:{image_tag}"

    print(f"Building image: {full_image_url}...")
    try:
        docker.build(
            context_path=".",
            file="Dockerfile",
            tags=[full_image_url],
            cache=True,
            pull=False,
        )
    except DockerException as e:
        raise RuntimeError(
            f"Docker build failed for image '{full_image_url}'.\n{e}"
        ) from e

    print("Build successful.")

    print("Pushing image to Google Artifact Registry...")
    # NOTE: You must be authenticated locally with gcloud (e.g. gcloud auth configure-docker <region>-docker.pkg.dev)
    # in order for the local docker credential helper to push successfully.
    try:
        docker.push(full_image_url)
    except DockerException as e:
        raise RuntimeError(
            f"Docker push failed for image '{full_image_url}'.\n{e}"
        ) from e

    print("Push successful.")

    print("Deploying image to Cloud Run...")
    update_cloud_run_job(
        gcp_project,
        cloud_run_job_location or gcp_region,
        cloud_run_job_name,
        full_image_url,
    )

    print("Deployment completed successfully!")
