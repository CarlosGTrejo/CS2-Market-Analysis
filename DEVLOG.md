## Task log

Legend
- [/] In progress
- [-] Cancelled
- [>] Deferred
- [?] Question
- [!] Important
- [*] Star/highlight


- [x] Initialize **Python** project with `uv init`
- [x] Add **Python dependencies** for:
  - [x] development: `uv add --dev prefect pulumi pulumi-gcp`
  - [x] extract_load pipeline:
    - `uv add "dlt[filesystem,gs,parquet]"`
    - `uv add --group inspection marimo "dlt[workspace]"`
  - [x] transform pipeline:
    - `uv add "prefect[dbt]" dbt-bigquery`
- [x] Create pipelines
  - [x] dlt pipeline for cs2 market items (extract & load to GCS/BigQuery)
  - [x] dlt pipeline for cs2 market item price history (extract & load to GCS/BigQuery)
  - [x] dbt transformations for cleaned and modeled tables in BigQuery
    - [x] items staging model
    - [x] item price history staging model
    - [x] add documentation and tests to dbt models
- [x] Initialize **dbt** project
  - [x] Add BigQuery adapter
- [x] Initialize **Prefect** project with `prefect init`
- [x] Create prefect workflow
  - [x] Task to run dlt pipeline (extract & load)
  - [x] Task to run dbt transformations
  - [x] Create **Dockerfile** for Prefect workers that includes dlt, dbt, and flow code
  - [x] Write Prefect deployment script to build Docker image and deploy flow to Prefect Cloud
- [x] Initialize **Pulumi** project with `pulumi new gcp-python`
- [x] Write Pulumi code to **provision infrastructure**:
  - [x] GCS bucket for data lake
  - [x] BigQuery dataset for data warehouse
  - [x] BigQuery external tables pointing to raw data in GCS Bucket
  - [x] Service accounts with least privilege for dlt and dbt
    - dbt service account permissions:
      - BigQuery Data Editor
      - BigQuery Job User
      - BigQuery User
    - dlt service account permissions:
      - storage.objectAdmin (for writing to GCS)
  - [x] Google Artifact Registry for container images (for Cloud Run Push)
- [x] Verify Pulumi provisioning works and infrastructure is set up correctly
- [x] Explore using **mise** to install all tools needed for the project.
- [x] README:
  - [x] Mention data volume and how it impacts our decisions
    - 31,000+ items, each with 4,000+ historical price points, results in 124 million+ records
    - 3,100 requests just to get the item list, and 31,000+ requests to get price history (rate limits are a concern). Daily requests: 34,000+ just to keep data up to date.
    - ~440KB per page for item list and items' history = 1.364GB of requested data per day.
  - [x] Explain choices and decision of our stack and deployment strategy.
    - even though dlt can create the datasets automatically, we are creating them with Pulumi to have better control and visibility over permissions and configurations.
  - [x] Explain our problem statement in the README
- [-] Investigate if our dlt pipeline properly handles retrying and resuming from failures. Do we need a dlt Runner?
  - dlt Runners require a license, the pipeline already handles retries by default. We just have to persist the pipeline dir.
- [x] make sure that the bucket_url env variable is available to dlt (DESTINATION__FILESYSTEM__BUCKET_URL="gs://your-staging-bucket")
- [x] Add bun and deps and optimize Dockerfile to build dashboard and deploy it
- [x] Consider batch yielding in dlt pipeline if throughput is low
  ```py
  # consider batch yielding if throughput is low.
  BATCH_SIZE = 1000
  current_batch = []
  for data_point in price_history:
      current_batch.append({ ... })
      if len(current_batch) >= BATCH_SIZE:
          yield current_batch
          current_batch = []
  if current_batch:
      yield current_batch
  ```
