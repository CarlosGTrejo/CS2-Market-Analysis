# CS2 Market Analysis ELT Pipeline

An end-to-end, cloud-native data engineering ELT pipeline for analyzing CS2 market data.

## Architecture & Tech Stack

This project uses the modern data stack:

* **Infrastructure as Code (IaC)** | [Pulumi](https://www.pulumi.com/) (Python)
  - Provisioning GCP resources: Google Cloud Storage (GCS), BigQuery, Artifact Registry, and Service Accounts
  - Configures Prefect Work Pools and Variables (creates Prefect Block for GCP credentials)
* **Orchestration** | [Prefect](https://www.prefect.io/)
  - Orchestrates the execution of dlt pipelines and dbt transformations
  - Uses Google Cloud Run Push for serverless execution of flows (scales to zero, pay per second)
  - Uses image-based deployments with a custom Docker image containing all necessary dependencies (dlt, dbt, flow code)
  - Handles image building and pushing to Artifact Registry as part of the deployment process
* **Data Extraction/Loading (EL)** | [dlt](https://dlthub.com/)
  - Extracts data from Steam's REST APIs for CS2 market items and price history using proxy rotation and pagination
  - Normalizes and loads raw data into GCS (data lake) as Parquet files for staging
  - Loads data from GCS to BigQuery (data warehouse)
* **Data Transformation (T)** | [dbt](https://www.getdbt.com/)
  - Transforms raw data in BigQuery into cleaned and modeled tables for analysis
  - Implements data quality tests and documentation for transformed models
* **Proxy Provider** | [Webshare.io](https://www.webshare.io/?referral_code=1omcktoaxbhl)
  - Rotating proxies to avoid rate limits when extracting data from Steam's APIs
* **Data Lake** | Google Cloud Storage Bucket
* **Data Warehouse** | Google BigQuery
* **Data Transformation (T)** | [dbt](https://www.getdbt.com/)
* **BI Dashboard** | TBD (considering Evidence or Rill Data)

## Project Structure

<!-- TODO: Verify project structure reflects most recent changes -->
```
CS2-Market-Analysis/
├── .python-version               # Specifies the Python version for uv
├── .env.example                  # Example environment variables
├── pyproject.toml                # Python dependencies (uv)
├── uv.lock                       # Locked dependencies for reproducible environments
├── .gitignore
├── .prefectignore                # Prevents unnecessary files from being uploaded during Prefect deployments
│
├── infra/                        # Pulumi Infrastructure as Code (Python)
│   ├── __main__.py               # Main Pulumi script defining GCP resources (GCS, BigQuery, Artifact Registry) and Service Accounts
│   ├── Pulumi.yaml               # Pulumi project configuration
│   └── Pulumi.prod.yaml          # Prod-specific configuration (blank for now)
│
├── pipelines/                    # Data Pipelines (Extract, Load, Transform)
│   ├── extract_load/             # dlt pipeline (Extract & Load)
│   │   └── ingest_market_data.py # extracts and loads market data (items and price history)
│   │  
│   └── transform/                # dbt project (Transform)
│       ├── dbt_project.yml       # dbt configuration
│       ├── profiles.yml          # TODO: describe
│       ├── models/               # dbt SQL transformation models for BigQuery
│       └── tests/                # Data quality tests
│
├── flows/                        # Prefect Orchestration & Deployments
│   ├── main_flow.py              # Prefect flows that orchestrate dlt and dbt
│   └── deploy.py                 # Python-based Prefect deployment script (builds Docker image & deploys)
│
├── dashboards/                   # BI & Visualization
│   └── README.md                 # TODO: shift to Evidence or Rill Data
│
└── Dockerfile                    # Defines the image for Prefect workers containing dlt, dbt, and flow code
```

## Quick Start (Frictionless Deployment)
<!-- TODO: Verify quickstart prerequisites and setup instructions -->
### 1. Prerequisites

- Accounts:
  - Google Cloud Project with Billing Enabled (free credits available).
    - Authentication configured (`gcloud auth application-default login`).
    - Enable [Artifact Registry API](https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com).
  - [Prefect Cloud](https://app.prefect.cloud/auth/sign-up) account (Free tier is sufficient)
  - [Pulumi Cloud](https://app.pulumi.com/signup) account (Free tier is sufficient)
  - [Webshare.io](https://www.webshare.io/?referral_code=1omcktoaxbhl) to avoid IP blocking and rate limits ($9/month for 3GB bandwidth is enough for 2 days of data extraction)
- Tools:
  - git (for cloning the repo)
  - Google Cloud CLI (`gcloud`) for authentication
  - [uv](https://docs.astral.sh/uv/getting-started/installation)
  - [Pulumi CLI](https://www.pulumi.com/docs/get-started/download-install/)
  - [Docker](https://docs.docker.com/engine/install/)

### 2. Setup & Running the pipeline

```bash
# 1. Get the code
git clone https://github.com/CarlosGTrejo/CS2-Market-Analysis.git
cd CS2-Market-Analysis

# 2. Authenticate local machine with Google Cloud
gcloud auth login
gcloud auth application-default login

# 3. Fill in the specific API keys
cp .env.example .env
nano .env

# 4. Install python dependencies
uv sync --locked

# 5. Authenticate with Pulumi
pulumi login

# 6. Authenticate with Prefect Cloud (follow interactive prompts)
uv run prefect cloud login

# 7. Stand up the GCP infrastructure (GCS, BigQuery, Artifact Registry)
# (Pulumi will automatically use the gcloud credentials from step 2)
uv run --env-file .env pulumi up -C infra/

# 8. Build the Docker image (locally) and deploy the flow to Prefect Cloud
# (Prefect will use the local Docker daemon to build, and gcloud creds to push)
uv run --env-file .env flows/deploy.py
```

---

## Documentation & Notes

#### Relevant Docs

- Prefect:
  - [Run flows on serverless compute (Google Cloud Run Push)](https://docs.prefect.io/v3/how-to-guides/deployment_infra/serverless#google-cloud-run)
- Pulumi:
  - [Configure Acccess to GCP (env vars)](https://www.pulumi.com/docs/iac/get-started/gcp/configure/)
- Steam API:
  - get CS2 market items: https://steamcommunity.com/market/search/render/?query=&start=0&count=10&search_descriptions=0&sort_column=name&sort_dir=asc&appid=730&norender=1
  - get item median price history: https://steamcommunity.com/market/pricehistory/?appid=APPID&market_hash_name=ITEMNAME
    - Requires authentication, will have to extract from html for unauthenticated requests, use `Referer: https://steamcommunity.com/market/search?appid=730` header.
- dlt:
  - [pagination](https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/basic#pagination)
  - [File layout](https://dlthub.com/docs/dlt-ecosystem/destinations/filesystem#files-layout)
    - Can be set through env vars OR pipeline code
  - Config for GCS:
    - `DESTINATION__FILESYSTEM__BUCKET_URL="gs://my_bucket"` needs to be set
    - `client_email`, `private_key`, and `project_id` can be fetched through default credentials, so they are not needed.
- dbt:
  - Least privilege needed for BigQuery:
    - BigQuery Data Editor
    - BigQuery Job User
    - BigQuery User


---


<details>
<summary></summary>
<!-- Task Log -->

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
- [ ] Create prefect workflow
  - [ ] Task to run dlt pipeline (extract & load)
  - [ ] Task to run dbt transformations
  - [/] Create **Dockerfile** for Prefect workers that includes dlt, dbt, and flow code
  - [ ] Write Prefect deployment script to build Docker image and deploy flow to Prefect Cloud
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
- Investigate if we should enable metadata caching for performance:
  - [Metadata caching for Performance BigQuery](https://docs.cloud.google.com/bigquery/docs/biglake-intro?authuser=1&hl=en#metadata_caching_for_performance)
- [ ] Explore using **mise** to install all tools needed for the project.
- [ ] README:
  - [ ] Mention data volume and how it impacts our decisions
    - 31,000+ items, each with 4,000+ historical price points, results in 124 million+ records
    - 3,100 requests just to get the item list, and 31,000+ requests to get price history (rate limits are a concern). Daily requests: 34,000+ just to keep data up to date.
    - ~440KB per page for item list and items' history = 1.364GB of requested data per day.
  - [ ] Explain choices and decision of our stack and deployment stragegy in the README.
    - e.g. why we are using Google Cloud Run Push? Cloud run push scales to zero, only pay for exact seconds flow is running
    - even though dlt can create the datasets automatically, we are creating them with Pulumi to have better control and visibility over permissions and configurations.
  - [ ] Explain our problem statement in the README
  - [ ] Do we need to specify if the user needs to select a specific Pulumi stack, or will Pulumi us prod by default??
- [ ] Investigate if our dlt pipeline properly handles retrying and resuming from failures. Do we need a dlt Runner?
- [ ] Should we add code somewhere that checks if the necessary environment variables are set? If so, how early in the process should we add the checks?
- [ ] make sure that the bucket_url env variable is available to dlt (DESTINATION__FILESYSTEM__BUCKET_URL="gs://your-staging-bucket")


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

</details>