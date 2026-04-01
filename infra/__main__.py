import base64
import json
import os
from typing import Any

import pulumi
import pulumi_gcp as gcp
import pulumi_prefect as prefect

region = os.getenv("GCP_REGION")
if not region:
    raise ValueError(
        "GCP_REGION environment variable must be set. Add it to .env file.\n"
        "Valid regions: https://docs.cloud.google.com/storage/docs/locations#location-r"
    )

gcp_project = pulumi.Config("gcp").get("project") or gcp.config.project
stack = pulumi.get_stack()
is_prod = stack == "prod"

# 1. Create a GCS Bucket for dlt data lake
bucket = gcp.storage.Bucket(
    "cs2_market_lake",
    name=f"{gcp_project}-cs2-data-lake-{stack}",
    location=region,
    force_destroy=True,
)

# 2. Create Google Artifact Registry for docker images
artifact_repo = gcp.artifactregistry.Repository(
    "cs2-pipeline-repo",
    repository_id=f"cs2-pipeline-repo-{stack}",
    format="DOCKER",
    location=region,
)

# 3. Create a BigQuery Dataset for dbt transformations
# Must exist before external tables and dbt runs
bq_dataset = gcp.bigquery.Dataset(
    "cs2_market_dwh",
    dataset_id=f"cs2_market_dwh_{stack}",
    location=region,
)

# 4. Create a dedicated Service Account for the pipeline
pipeline_sa = gcp.serviceaccount.Account(
    "pipeline-runner-sa",
    account_id=f"pipeline-runner-{stack}",
    display_name="CS2 ELT Pipeline Runner",
)

# 5. Grant the Service Account necessary roles (Least Privilege)
# Bucket specific role
gcp.storage.BucketIAMMember(
    "pipeline-sa-bucket-admin",
    bucket=bucket.name,
    role="roles/storage.objectAdmin",  # For dlt to write to this specific GCS bucket
    member=pulumi.Output.format(
        "serviceAccount:{SA_email}", SA_email=pipeline_sa.email
    ),
)

# Project level roles
roles = [
    "roles/bigquery.dataEditor",  # For dbt to transform data
    "roles/bigquery.jobUser",  # For dbt to run queries
    "roles/bigquery.user",  # For dbt to read from BigQuery
    "roles/run.developer",  # For Prefect to push to Cloud Run
    "roles/iam.serviceAccountUser",  # For Prefect to attach this SA to Cloud Run
]

for role in roles:
    gcp.projects.IAMMember(
        f"pipeline-sa-{role.split('.')[1]}",
        project=gcp_project,
        role=role,
        member=pulumi.Output.format(
            "serviceAccount:{SA_email}", SA_email=pipeline_sa.email
        ),
    )

# 6. Generate a JSON Key for the Service Account
sa_key = gcp.serviceaccount.Key(
    "pipeline-runner-key",
    service_account_id=pipeline_sa.name,
)


# 7. Use Prefect Provider to securely send the key to Prefect Cloud
def create_gcp_creds_data(private_key_data: str) -> str:
    decoded = base64.b64decode(private_key_data).decode("utf-8")
    # parsed = json.loads(decoded)
    # return json.dumps({"service_account_info": parsed})
    return decoded


gcp_credentials_block = prefect.Block(
    "gcp-credentials-block",
    name=f"cs2-gcp-creds-{stack}",
    type_slug="gcp-credentials",
    data=sa_key.private_key.apply(create_gcp_creds_data),  # type: ignore
)


# 8. Create Cloud Run Push Work Pool
def create_job_template(args: list[Any]) -> str:
    return json.dumps(
        {
            "variables": {
                "type": "object",
                "properties": {
                    "image": {
                        "type": "string",
                        "title": "Image",
                        "description": "The container image for the flow run.",
                    },
                    "region": {
                        "type": "string",
                        "title": "Region",
                        "default": region,
                        "description": "The region to run Cloud Run jobs.",
                    },
                    "credentials": {
                        "type": "string",
                        "title": "GCP Credentials",
                        "default": f"{{{{ prefect.blocks.gcp-credentials.{args[0]} }}}}",
                    },
                },
            },
            "job_configuration": {
                "image": "{{ image }}",
                "region": "{{ region }}",
                "credentials": "{{ credentials }}",
            },
        }
    )


cloud_run_push_pool = prefect.WorkPool(
    "cloud-run-push-pool",
    name=f"cs2-push-pool-{stack}",
    type="cloud-run:push",
    # TODO: verify that we are using the correct pulumi design patterns. Are we sure it's not supposed to be `.apply(...)` since we are only working with one output?
    base_job_template=pulumi.Output.all(gcp_credentials_block.name).apply(
        create_job_template  # type: ignore
    ),  # type: ignore
)

# 9. BigQuery External Tables with dynamic bucket paths
items_external_table = gcp.bigquery.Table(
    "items_external",
    dataset_id=bq_dataset.dataset_id,
    table_id="items_external",
    external_data_configuration=gcp.bigquery.TableExternalDataConfigurationArgs(
        source_uris=[
            pulumi.Output.format(
                "{bucket_url}/cs2_market_data/items/*.parquet", bucket_url=bucket.url
            )
        ],
        source_format="PARQUET",
        autodetect=True,
    ),
    deletion_protection=is_prod,
)

item_price_history_external_table = gcp.bigquery.Table(
    "item_price_history_external",
    dataset_id=bq_dataset.dataset_id,
    table_id="item_price_history_external",
    external_data_configuration=gcp.bigquery.TableExternalDataConfigurationArgs(
        source_uris=[
            pulumi.Output.format(
                "{bucket_url}/cs2_market_data/item_price_history/*.parquet",
                bucket_url=bucket.url,
            )
        ],
        source_format="PARQUET",
        autodetect=True,
    ),
    deletion_protection=is_prod,
)


# 10. Frictionless Outputs
def format_outputs(args: list[Any]) -> str:
    return f"""\n
===============================================================
           Infrastructure successfully provisioned! 
===============================================================

The DWH tables and Prefect GCP block have been setup automatically.

* GCS Bucket for Data Lake: {args[0]}
* Artifact Registry for Flow Images: {args[1]}-docker.pkg.dev/{args[2]}/{args[3]}
* Prefect Work Pool Name: {args[4]}


Build and Push your Flow Image with:

  uv run --env-file .env flows/deploy.py


===============================================================
"""


pulumi.export(
    "Next_Steps",
    pulumi.Output.all(  # type: ignore
        bucket.url,
        artifact_repo.location,
        artifact_repo.project,
        artifact_repo.repository_id,
        cloud_run_push_pool.name,
    ).apply(format_outputs),  # type: ignore
)
