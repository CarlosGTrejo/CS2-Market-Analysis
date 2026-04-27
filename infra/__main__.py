import pulumi
import pulumi_gcp as gcp
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL
from preflight import check_env

env = check_env(
    required_vars=[
        (
            "GOOGLE_REGION",
            "GOOGLE_REGION must be set. \n    Valid regions: https://docs.cloud.google.com/storage/docs/locations#location-r",
        ),
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        (
            "PROXY_URL",
            "PROXY_URL is not set. This is required to avoid rate limits.",
        ),
    ],
    optional_vars=[
        (
            "GOOGLE_CLOUD_SCHEDULER_REGION",
            "GOOGLE_CLOUD_SCHEDULER_REGION is not set, `GOOGLE_REGION` will be used instead. \n    Valid regions: https://docs.cloud.google.com/scheduler/docs/locations",
        ),
    ],
)


region = env["GOOGLE_REGION"]
scheduler_region = env.get("GOOGLE_CLOUD_SCHEDULER_REGION", region)
cloudflare_account_id = env["CLOUDFLARE_ACCOUNT_ID"]
cloudflare_api_token = env["CLOUDFLARE_API_TOKEN"]
proxy_url = env["PROXY_URL"]

gcp_project = pulumi.Config("gcp").get("project") or gcp.config.project
stack = pulumi.get_stack()
is_prod = stack == "prod"  # Safety switch to prevent destructive actions in prod

# dev/prod resource configs
CLOUD_RUN_CPU = "2" if stack == "prod" else "1"
CLOUD_RUN_MEMORY = "4Gi" if stack == "prod" else "1Gi"
SCHEDULER_CRON = "0 5 * * *" if stack == "prod" else "0 0 * * *"  # 5 hours apart

# 1. Create a GCS Bucket for dlt data lake
bucket = gcp.storage.Bucket(
    "cs2_market_lake",
    name=f"{gcp_project}-cs2-data-lake-{stack}",
    location=region,
    force_destroy=not is_prod,  # Prevent accidental deletion of prod data with force_destroy in non-prod only
    uniform_bucket_level_access=True,
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
    delete_contents_on_destroy=not is_prod,  # Allow dataset deletion in dev, protect in prod
)

# dlt also needs a "staging" dataset:
bq_staging_dataset = gcp.bigquery.Dataset(
    "cs2_market_dwh_staging",
    dataset_id=f"cs2_market_dwh_{stack}_staging",
    location=region,
    delete_contents_on_destroy=not is_prod,  # Allow dataset deletion in dev, protect in prod
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
    "roles/bigquery.dataEditor",  # As specified in dlt and dbt docs
    "roles/bigquery.jobUser",  # As specified in dlt and dbt docs
    "roles/bigquery.readSessionUser",  # As specified in dlt docs for BigQuery
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

# 6. Prefect API Credentials AND Cloudflare Credentials via GCP Secret Manager
prefect_api_url = PREFECT_API_URL.value()

prefect_api_key = PREFECT_API_KEY.value()

if not prefect_api_key or not prefect_api_url:
    raise ValueError(
        "PREFECT_API_KEY and PREFECT_API_URL must be available. Run `uv run prefect cloud login` or set them in your .env file."
    )

prefect_api_key_secret = gcp.secretmanager.Secret(
    "prefect-api-key-secret",
    secret_id=f"prefect-api-key-{stack}",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs()
    ),
)

prefect_api_key_secret_version = gcp.secretmanager.SecretVersion(
    "prefect-api-key-secret-version",
    secret=prefect_api_key_secret.id,
    secret_data=prefect_api_key,
)

gcp.secretmanager.SecretIamMember(
    "prefect-api-key-accessor",
    secret_id=prefect_api_key_secret.id,
    role="roles/secretmanager.secretAccessor",
    member=pulumi.Output.format(
        "serviceAccount:{SA_email}", SA_email=pipeline_sa.email
    ),
)


# Cloudflare API Token via GCP Secret Manager
cloudflare_api_token_secret = gcp.secretmanager.Secret(
    "cloudflare-api-token-secret",
    secret_id=f"cloudflare-api-token-{stack}",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs()
    ),
)

gcp.secretmanager.SecretVersion(
    "cloudflare-api-token-secret-version",
    secret=cloudflare_api_token_secret.id,
    secret_data=cloudflare_api_token,
)

gcp.secretmanager.SecretIamMember(
    "cloudflare-api-token-accessor",
    secret_id=cloudflare_api_token_secret.id,
    role="roles/secretmanager.secretAccessor",
    member=pulumi.Output.format(
        "serviceAccount:{SA_email}", SA_email=pipeline_sa.email
    ),
)

# Proxy URL via GCP Secret Manager
proxy_url_secret = gcp.secretmanager.Secret(
    "proxy-url-secret",
    secret_id=f"proxy-url-{stack}",
    replication=gcp.secretmanager.SecretReplicationArgs(
        auto=gcp.secretmanager.SecretReplicationAutoArgs()
    ),
)

gcp.secretmanager.SecretVersion(
    "proxy-url-secret-version",
    secret=proxy_url_secret.id,
    secret_data=proxy_url,
)

gcp.secretmanager.SecretIamMember(
    "proxy-url-accessor",
    secret_id=proxy_url_secret.id,
    role="roles/secretmanager.secretAccessor",
    member=pulumi.Output.format(
        "serviceAccount:{SA_email}", SA_email=pipeline_sa.email
    ),
)

# 7. Cloud Run V2 Job
placeholder_image = "us-docker.pkg.dev/cloudrun/container/job:latest"

envs = [
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="PREFECT_API_URL",
        value=prefect_api_url,
    ),
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="GOOGLE_PROJECT",
        value=gcp_project,
    ),
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="GOOGLE_REGION",
        value=region,
    ),
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="DESTINATION__FILESYSTEM__BUCKET_URL",
        value=bucket.url,
    ),
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="DESTINATION__BIGQUERY__LOCATION",
        value=region,
    ),
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="BQ_DATASET_NAME",
        value=bq_dataset.dataset_id,
    ),
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="PULUMI_STACK",
        value=stack,
    ),
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="CLOUDFLARE_ACCOUNT_ID",
        value=cloudflare_account_id,
    ),
]

envs.append(
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="PREFECT_API_KEY",
        value_source=gcp.cloudrunv2.JobTemplateTemplateContainerEnvValueSourceArgs(
            secret_key_ref=gcp.cloudrunv2.JobTemplateTemplateContainerEnvValueSourceSecretKeyRefArgs(
                secret=prefect_api_key_secret.secret_id,
                version="latest",
            )
        ),
    )
)

# Inject Cloudflare API Token
envs.append(
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="CLOUDFLARE_API_TOKEN",
        value_source=gcp.cloudrunv2.JobTemplateTemplateContainerEnvValueSourceArgs(
            secret_key_ref=gcp.cloudrunv2.JobTemplateTemplateContainerEnvValueSourceSecretKeyRefArgs(
                secret=cloudflare_api_token_secret.secret_id,
                version="latest",
            )
        ),
    )
)

# Inject Proxy URL
envs.append(
    gcp.cloudrunv2.JobTemplateTemplateContainerEnvArgs(
        name="PROXY_URL",
        value_source=gcp.cloudrunv2.JobTemplateTemplateContainerEnvValueSourceArgs(
            secret_key_ref=gcp.cloudrunv2.JobTemplateTemplateContainerEnvValueSourceSecretKeyRefArgs(
                secret=proxy_url_secret.secret_id,
                version="latest",
            )
        ),
    )
)

cloud_run_job = gcp.cloudrunv2.Job(
    "cs2-market-analysis-job",
    name=f"cs2-elt-job-{stack}",
    location=region,
    template=gcp.cloudrunv2.JobTemplateArgs(
        template=gcp.cloudrunv2.JobTemplateTemplateArgs(
            service_account=pipeline_sa.email,
            max_retries=0,
            containers=[
                gcp.cloudrunv2.JobTemplateTemplateContainerArgs(
                    image=placeholder_image,
                    envs=envs,
                    resources=gcp.cloudrunv2.JobTemplateTemplateContainerResourcesArgs(
                        limits={
                            "cpu": CLOUD_RUN_CPU,
                            "memory": CLOUD_RUN_MEMORY,  # Adjust memory up or down based on your data volume
                        }
                    ),
                )
            ],
            timeout="28800s",  # 8 hours
        )
    ),
    deletion_protection=is_prod,
    opts=pulumi.ResourceOptions(
        ignore_changes=["template.template.containers[0].image"]
    ),
)

# 8. Cloud Scheduler Job
scheduler_sa = gcp.serviceaccount.Account(
    "scheduler-sa",
    account_id=f"scheduler-{stack}",
    display_name="Cloud Scheduler Service Account",
)

gcp.cloudrunv2.JobIamMember(
    "scheduler-run-invoker",
    name=cloud_run_job.name,
    project=gcp_project,
    location=region,
    role="roles/run.invoker",
    member=pulumi.Output.format(
        "serviceAccount:{SA_email}", SA_email=scheduler_sa.email
    ),
)

cloud_scheduler_job = gcp.cloudscheduler.Job(
    "cs2-elt-scheduler",
    name=f"cs2-elt-schedule-{stack}",
    region=scheduler_region,
    schedule=SCHEDULER_CRON,
    time_zone="UTC",
    http_target=gcp.cloudscheduler.JobHttpTargetArgs(
        http_method="POST",
        # Using the standard v1 run.googleapis.com URL format
        uri=pulumi.Output.format(
            "https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{project}/jobs/{job_name}:run",
            region=region,
            project=gcp_project,
            job_name=cloud_run_job.name,
        ),
        oauth_token=gcp.cloudscheduler.JobHttpTargetOauthTokenArgs(
            service_account_email=scheduler_sa.email,
        ),
    ),
)

pulumi.export("gcp_project", gcp_project)
pulumi.export("gcs_bucket_url", bucket.url)
pulumi.export("bq_dataset_name", bq_dataset.dataset_id)
pulumi.export("pipeline_sa_email", pipeline_sa.email)
pulumi.export("cloud_run_job_name", cloud_run_job.name)
pulumi.export("cloud_run_job_location", cloud_run_job.location)
pulumi.export(
    "artifact_registry_url",
    pulumi.Output.format(
        "{location}-docker.pkg.dev/{project}/{repository_id}",
        location=artifact_repo.location,
        project=artifact_repo.project,
        repository_id=artifact_repo.repository_id,
    ),
)
