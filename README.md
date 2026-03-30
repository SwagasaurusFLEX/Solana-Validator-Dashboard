# Solana Validator Economics Dashboard

**Are validator economics a threat to Solana's decentralization?**

A data engineering project analyzing on-chain Solana validator reward data to determine whether running a validator is economically sustainable, and what happens to network decentralization when it's not.

## Problem Statement

Solana validators must pay ~1.1 SOL per day in voting transaction fees just to participate in consensus. At current SOL prices, that's roughly $88/day or $2,640/month — before any hardware costs. Meanwhile, validator rewards are heavily concentrated: the top 100 validators capture over 70% of all rewards, leaving the remaining 650+ validators to split the rest.

The result? Solana's active validator count has dropped from ~2,500 in 2023 to roughly 750 in early 2026 — a 68% decline. The Nakamoto coefficient (minimum validators needed to control 33% of the network) has fallen into the concerning range of 15-19. This project uses real blockchain data to quantify the problem and model what protocol changes like the upcoming Alpenglow upgrade could do to fix it.

## Dashboard

The interactive Streamlit dashboard answers four key questions:

1. **How many validators are profitable?** — A profit/loss distribution showing net daily SOL after voting costs
2. **What if voting costs change?** — An interactive slider modeling the impact of Alpenglow (which eliminates voting fees)
3. **How decentralized is the network?** — Nakamoto coefficient tracked over time
4. **Where are rewards going?** — Concentration analysis showing top 10/50/100 validator reward share

> 🔗 **[Live Dashboard](#)** *(link to be added after deployment)*

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  BigQuery Public     │     │  CoinGecko API   │     │                  │
│  Solana Dataset      │     │  (SOL price)     │     │   Terraform      │
│  (Block Rewards,     │     │                  │     │   (IaC)          │
│   Blocks)            │     │                  │     │                  │
└────────┬────────────┘     └────────┬─────────┘     └──────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────┐
│          Apache Airflow (Docker)            │
│                                             │
│  extract_block_rewards ─┐                   │
│  extract_blocks ────────┼─► load_to_warehouse ─► run_dbt │
│  extract_sol_price ─────┘                   │
└─────────────────────┬───────────────────────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
┌─────────────────┐     ┌──────────────────────┐
│  Google Cloud    │     │  BigQuery Warehouse   │
│  Storage (GCS)   │     │                      │
│  Parquet files   │     │  Staging → dbt →     │
│  (Data Lake)     │     │  Fact Tables         │
└─────────────────┘     └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Streamlit Dashboard  │
                        │  (deployed)           │
                        └──────────────────────┘
```

## Tech Stack

| Component | Tool |
|---|---|
| Infrastructure as Code | Terraform |
| Cloud Platform | Google Cloud (GCS + BigQuery) |
| Containerization | Docker + Docker Compose |
| Workflow Orchestration | Apache Airflow |
| Data Lake | Google Cloud Storage (Parquet) |
| Data Warehouse | BigQuery (partitioned + clustered) |
| Transformations | dbt |
| Dashboard | Streamlit + Plotly |
| Data Sources | BigQuery Public Solana Dataset, CoinGecko API |

## Data Pipeline

### Extraction
The Airflow DAG runs three extraction tasks in parallel:
- **Block Rewards** — validator reward events from BigQuery's public Solana dataset (`bigquery-public-data.crypto_solana_mainnet_us.Block Rewards`)
- **Blocks** — block production data including leader assignment and transaction counts
- **SOL Price** — daily SOL/USD price from the CoinGecko free API

### Loading
Raw data is exported from BigQuery staging tables to GCS as Parquet files (data lake), then loaded into the warehouse BigQuery dataset.

### Transformation (dbt)
Three layers of dbt models transform raw data into analytics-ready tables:

**Staging** — clean and type-cast raw data, convert lamports to SOL
- `stg_block_rewards` — one row per reward event
- `stg_blocks` — one row per block produced
- `stg_sol_price` — daily SOL/USD price

**Intermediate** — aggregations and joins
- `int_validator_daily_rewards` — daily SOL earned per validator
- `int_validator_summary` — overall stats per validator (total earned, avg daily, active days)
- `int_daily_network_stats` — network-wide daily metrics with percentile distributions

**Facts** — business logic answering the core questions
- `fct_validator_profitability` — per-validator profitability analysis, break-even SOL price calculations, tier classification (whale/medium/small/underwater)
- `fct_network_risk` — daily risk assessment: what % of validators are profitable at current SOL prices
- `fct_reward_concentration` — Nakamoto coefficient, reward share of top 10/50/100 validators

### Data Warehouse Optimization
- Tables partitioned by `block_timestamp` (monthly)
- Block Rewards clustered by `pubkey` (validator public key)
- This makes sense because downstream queries filter by date range and group by validator — partitioning reduces scan size and clustering speeds up per-validator aggregations

## Key Findings

- **The vast majority of validators are underwater** — they earn less than the 1.1 SOL/day voting cost
- **Only ~750 active validators remain**, down from ~2,500 in 2023
- **The Nakamoto coefficient sits at 15-19**, meaning fewer than 20 validators could collude to control a third of the network
- **The top 100 validators capture ~73% of all rewards**, leaving 650+ validators to share the remaining 27%
- **Alpenglow could help** — if voting costs drop to zero, the number of underwater validators drops significantly, though most tiny validators still earn negligible amounts

## Steps to Reproduce

### Prerequisites
- Docker Desktop
- Terraform
- Google Cloud SDK (`gcloud`)
- Python 3.11+
- A GCP project with billing enabled (free tier is sufficient)

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/solana-validator-economics-dashboard.git
cd solana-validator-economics-dashboard
```

### 2. Set up GCP credentials
```bash
# Create a service account
gcloud iam service-accounts create solana-pipeline --display-name="Solana Pipeline"

# Grant permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:solana-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:solana-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:solana-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:solana-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

# Download key
mkdir -p config
gcloud iam service-accounts keys create config/sa-key.json \
  --iam-account=solana-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Also set up application default credentials (needed for BigQuery public dataset access)
gcloud auth application-default login
cp $APPDATA/gcloud/application_default_credentials.json config/gcp-key.json
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your GCP project ID and bucket name

cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Edit terraform.tfvars with your GCP project ID
```

### 4. Provision infrastructure
```bash
cd terraform
terraform init
terraform apply
cd ..
```

### 5. Start Airflow
```bash
docker-compose up -d --build
```
Airflow UI will be available at `http://localhost:8080` (admin/admin).

### 6. Run the pipeline
In the Airflow UI, enable the `solana_validator_pipeline` DAG and trigger a run. The pipeline will:
1. Extract Block Rewards and Blocks from BigQuery public Solana dataset
2. Extract SOL price from CoinGecko
3. Export data to GCS as Parquet files
4. Load into the warehouse BigQuery dataset
5. Run dbt transformations to create fact tables

### 7. View the dashboard
```bash
pip install streamlit plotly google-cloud-bigquery pandas db-dtypes
streamlit run streamlit_app.py
```

## Future Improvements (Attempt 2)
- Add MEV/Jito tip analysis — how much do validators earn from transaction ordering vs inflation
- Geographic concentration — map validator locations by data center and country
- Model Alpenglow impact with real projected parameters
- Track validator count daily to build a longer time series
- Add sniper/bundle correlation analysis with validator concentration

## Course
This project was built as the final capstone for the [Data Engineering Zoomcamp 2026](https://github.com/DataTalksClub/data-engineering-zoomcamp) by [DataTalks.Club](https://datatalks.club/).