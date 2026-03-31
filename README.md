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
* **Data Extraction (EL)** | [dlt](https://dlthub.com/)
  - Extracts data from Steam's REST APIs for CS2 market items and price history using proxy rotation and pagination
  - Normalizes and loads raw data into GCS as Parquet files (data lake)
* **Proxy Provider**: Rotating proxies to avoid rate limits when extracting data from Steam's APIs
  - [Scrape.do](https://scrape.do?fpr=k1frxj) or...
  - [Webshare.io](https://www.webshare.io/?referral_code=1omcktoaxbhl)
* **Data Lake** | Google Cloud Storage Bucket
* **Data Warehouse** | Google BigQuery
* **Data Transformation (T)** | [dbt](https://www.getdbt.com/)
* **BI Dashboard** | [Looker Studio](https://lookerstudio.google.com/)

## Project Structure

```
CS2-Market-Analysis/
├── .python-version             # Specifies the Python version for uv
├── .env.example                # Example environment variables
├── pyproject.toml              # Manages Python dependencies (uv)
├── uv.lock                     # Locked dependencies for reproducible environments
├── .gitignore
├── .prefectignore              # Prevents unnecessary files from being uploaded during Prefect deployments
│
├── infra/                      # Pulumi Infrastructure as Code (Python)
│   ├── __main__.py             # Main Pulumi script defining GCP resources (GCS, BigQuery, Artifact Registry) and Service Accounts
│   ├── Pulumi.yaml             # Pulumi project configuration
│   └── Pulumi.prod.yaml        # Environment-specific configuration (e.g., prod, dev)
│
├── pipelines/                  # Data Pipelines (Extract, Load, Transform)
│   ├── extract-load/           # dlt pipelines (Extract & Load)
│   │   ├── items.py            # pipeline for extracting and loading CS2 market items data
│   │   └── sales_history.py    # pipeline for extracting and loading item's median sales price history
│   │
│   └── transform/              # dbt project (Transform)
│       ├── dbt_project.yml     # Main dbt configuration
│       ├── models/             # dbt SQL transformation models for BigQuery
│       ├── macros/             # Reusable dbt SQL macros
│       └── tests/              # Data quality tests
│
├── flows/                      # Prefect Orchestration & Deployments
│   ├── main_flow.py            # Prefect flows that orchestrate dlt and dbt
│   └── deploy.py               # Python-based Prefect deployment script (builds Docker image & deploys)
│
├── dashboards/                 # BI & Visualization
│   └── README.md               # Looker Studio dashboard links, configuration details, or embedded templates
│
└── Dockerfile                  # Defines the image for Prefect workers containing dlt, dbt, and flow code
```

## Quick Start (Frictionless Deployment)

### 1. Prerequisites

- Accounts:
  - Google Cloud Project with Billing Enabled (free credits available).
    - Authentication configured (`gcloud auth application-default login`).
  - Prefect Cloud account (Free tier is sufficient)
  - Pulumi Cloud account (Free tier is sufficient)
  - Your own proxy provider account (rate limits will be an issue)
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

# 3. Authenticate with Pulumi
pulumi login

# 4. Fill in the specific API keys
cp .env.example .env
nano .env

# 5. Install python dependencies
uv sync --locked

# 6. Stand up the GCP infrastructure (GCS, BigQuery, Artifact Registry)
# (Pulumi will automatically use the gcloud credentials from step 2)
uv run --env-file .env pulumi up -C infra/

# 7. Build the Docker image (locally) and deploy the flow to Prefect Cloud
# (Prefect will use the local Docker daemon to build, and gcloud creds to push)
uv run --env-file .env flows/deploy.py
```

---

## Documentation & Notes

### GCP Infrastructure

- Service accounts are created with least privilege for both dlt and dbt to access GCS and BigQuery.
  - dbt service account permissions:
    - BigQuery Data Editor
    - BigQuery Job User
    - BigQuery User

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

## README TODOs

- Explain why we are using Google Cloud Run Push (cloud run push scales to zero, only pay for exact seconds flow is running)


---

## Tasks

- [x] Initialize **Python** project with `uv init`
- [/] Add **Python dependencies** for:
  - [x] development: `uv add --dev prefect pulumi pulumi-gcp`
  - [x] extract-load pipeline: `uv add "dlt[filesystem,gs,parquet]"`
  - [ ] transform pipeline: dbt Fusion
- [/] Create pipelines
  - [x] dlt pipeline for cs2 market items (extract & load to GCS/BigQuery)
  - [x] dlt pipeline for cs2 market item price history (extract & load to GCS/BigQuery)
  - [/] dbt transformations for cleaned and modeled tables in BigQuery
- [x] Initialize **Prefect** project with `prefect init`
- [ ] Create prefect workflow
  - [ ] Task to run dlt pipeline (extract & load)
  - [ ] Task to run dbt transformations
  - [/] Create **Dockerfile** for Prefect workers that includes dlt, dbt, and flow code
  - [ ] Write Prefect deployment script to build Docker image and deploy flow to Prefect Cloud
- [x] Initialize **Pulumi** project with `pulumi new gcp-python`
- [/] Write Pulumi code to **provision infrastructure**:
  - [ ] GCS bucket for data lake
  - [ ] BigQuery dataset for data warehouse
  - [x] BigQuery external tables pointing to raw data in GCS Bucket
  - [ ] Service accounts with least privilege for dlt and dbt
    - [ ] IAM permissions for service accounts
  - [ ] Google Artifact Registry for container images (for Cloud Run Push)
  - [ ] Looker Studio BI dashboard (if possible via IaC, otherwise document manual steps)
- [x] Initialize **dbt** project
  - [x] Add BigQuery adapter
- [ ] Explore using **mise** to install all tools needed for the project.