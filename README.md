# Solana Validator Economics Dashboard

**Are validator economics a threat to Solana's decentralization?**

A data engineering project analyzing on-chain Solana data to show how unsustainable validator economics drove centralization, concentrated block production, and handed control of transaction ordering to a single MEV infrastructure — Jito.

## Problem Statement

Solana validators must pay ~1.1 SOL per day (~$91/day at current prices) in voting transaction fees just to participate in consensus — before any hardware costs. Solana's active validator count collapsed from 5,400 in October 2024 to under 800 today — an 85% decline in 18 months. Thousands of validators couldn't cover the cost and shut down.

The survivors are increasingly concentrated at the top. The top 100 validators produce 71% of all blocks. With economics this brutal, validators adopted Jito — a client that sells transaction ordering to the highest bidder — for any extra revenue they could get. Today, 770 out of 773 validators run Jito. 98.1% of all Solana blocks flow through one company's auction system.

During peak memecoin season (mid-2024), only 441 validators ran Jito and $14.7 million was extracted in a single day. Now 770 run it — nearly double. The Alpenglow upgrade will reduce voting costs and potentially bring new validators online, but if every new validator also runs Jito, the extraction machine only grows. The network needs competing validator infrastructure. This project uses real blockchain data to quantify the problem and tell the story.

## Dashboard

The interactive Streamlit dashboard tells the story in seven sections:

1. **Validator economics are unsustainable** — Profit/loss distribution, Alpenglow upgrade simulator
2. **Decentralization is declining** — Historical validator count (5,400 → 800), Nakamoto coefficient
3. **Where does revenue come from?** — Four-way revenue split (voting rewards, base fees, priority fees, Jito tips) by validator tier
4. **Block production & MEV are concentrated** — Side-by-side horizontal bar charts
5. **Rewards are flowing to the top** — Sankey diagram showing reward flow to validator tiers
6. **Jito controls 98% of blocks** — Dominance metrics, historical MEV vs Jito adoption
7. **The full picture** — Narrative summary connecting all findings

> 🔗 **[Live Dashboard](https://solana-validator-dashboard-7jlzowd9tcm93cafoend66.streamlit.app/)**

## Architecture

```
┌─────────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  BigQuery Public     │  │  Solana RPC API   │  │  Jito API        │  │  CoinGecko API   │
│  Solana Dataset      │  │  getVoteAccounts  │  │  MEV rewards     │  │  SOL/USD price   │
│  (Block Rewards,     │  │  (validator       │  │  Historical      │  │                  │
│   Blocks)            │  │   snapshots)      │  │  epochs          │  │                  │
└────────┬─────────────┘  └────────┬──────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                         │                       │                     │
         ▼                         ▼                       ▼                     ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                          Apache Airflow (Docker)                                        │
│                                                                                         │
│  extract_block_rewards ─┐                                                               │
│  extract_blocks ────────┤                                                               │
│  extract_sol_price ─────┼──► load_to_warehouse ──► run_dbt                              │
│  extract_validators ────┤                                                               │
│  extract_jito_mev ──────┤                                                               │
│  extract_jito_hist ─────┘                                                               │
└─────────────────────────┬───────────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
┌─────────────────────┐     ┌──────────────────────────┐
│  Google Cloud       │     │  BigQuery Warehouse       │
│  Storage (GCS)      │     │                           │
│  Parquet files      │     │  Staging → dbt →          │
│  (Data Lake)        │     │  Materialized Tables →    │
│                     │     │  Fact Tables              │
└─────────────────────┘     └────────────┬──────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │  Streamlit Dashboard  │
                              │  (Streamlit Cloud)    │
                              └──────────────────────┘
```

## Tech Stack

| Component | Tool |
|---|---|
| Infrastructure as Code | Terraform |
| Cloud Platform | Google Cloud (GCS + BigQuery) |
| Containerization | Docker + Docker Compose |
| Workflow Orchestration | Apache Airflow (LocalExecutor) |
| Data Lake | Google Cloud Storage (Parquet) |
| Data Warehouse | BigQuery (partitioned + clustered) |
| Transformations | dbt |
| Dashboard | Streamlit + Plotly |
| Data Sources | BigQuery Public Solana Dataset, Solana RPC API, Jito API, CoinGecko API, Jito Website |

## Data Pipeline

### Data Sources

| Source | What it provides | Table(s) |
|---|---|---|
| BigQuery Public Solana Dataset | Block rewards (voting rewards per validator), block production data (leader, fees, transactions) | `raw_block_rewards`, `raw_blocks` |
| Solana RPC API (`getVoteAccounts`) | Current validator snapshot: stake, commission, vote/node pubkey mapping | `raw_validator_snapshots` |
| Jito API (`kobe.mainnet.jito.network`) | Per-validator MEV rewards, historical epoch-level MEV totals, Jito validator counts | `raw_jito_mev`, `raw_jito_historical` |
| CoinGecko API | Daily SOL/USD price | `raw_sol_price` |
| Jito Website (CSV export) | Official fee breakdown: base fees vs priority fees vs Jito tips | Applied as 18%/65%/17% ratio in dashboard |
| BigQuery Public (one-time historical scan) | Historical validator count 2024–present | `historical_validator_count` |

### Extraction
The Airflow DAG runs six extraction tasks:
- **Block Rewards** — validator voting reward events from BigQuery's public Solana dataset (`bigquery-public-data.crypto_solana_mainnet_us.Block Rewards`)
- **Blocks** — block production data including leader assignment, transaction counts, and leader_reward (fees)
- **SOL Price** — daily SOL/USD from CoinGecko free API
- **Validator Snapshots** — current validator set from Solana RPC `getVoteAccounts`
- **Jito MEV** — per-validator MEV rewards from Jito API
- **Jito Historical** — epoch-level MEV totals and Jito validator counts from Jito API

### Loading
Raw data is exported from BigQuery staging tables to GCS as Parquet files (data lake), then loaded into the warehouse BigQuery dataset.

### Transformation (dbt)
Three layers of dbt models transform raw data into analytics-ready tables:

**Staging** — clean and type-cast raw data, convert lamports to SOL
- `stg_block_rewards` — one row per reward event (filtered to reward_type='Voting')
- `stg_blocks` — one row per block produced
- `stg_sol_price` — daily SOL/USD price

**Intermediate** — aggregations and joins
- `int_validator_daily_rewards` — daily SOL earned per validator
- `int_validator_summary` — overall stats per validator (total earned, avg daily, active days)
- `int_daily_network_stats` — network-wide daily metrics with percentile distributions

**Facts** — business logic answering the core questions
- `fct_validator_profitability` — per-validator profitability analysis, break-even SOL price
- `fct_validator_economics` — three-source revenue calculation (voting + block fees + MEV)
- `fct_network_risk` — daily risk assessment: what % of validators are profitable
- `fct_reward_concentration` — Nakamoto coefficient, reward share of top 10/50/100 validators

### Materialized Tables
To avoid scanning 15+ GB of raw data on every dashboard load, key aggregations are pre-computed:
- `validator_daily_block_fees` — daily block fees per validator from `raw_blocks`
- `validator_daily_voting_rewards` — daily voting rewards from `int_validator_summary`

### Data Warehouse Optimization
- Tables partitioned by `block_timestamp` (monthly)
- Block Rewards clustered by `pubkey` (validator public key)
- Partitioning reduces scan size for date-filtered queries; clustering speeds up per-validator aggregations

## Key Findings

### Validator Economics
- **773 active validators** remain, down from 5,400 in October 2024 — an 85% decline
- **97 validators are underwater** — earning less than the 1.1 SOL/day voting cost
- **98 validators (12%)** earn over 500 SOL/day — the remaining 675 average under 14 SOL/day
- Top tier: 551 SOL/day. Underwater: 0.6 SOL/day — a **920x difference**

### Revenue Breakdown (Jito Official Data, March 2026)
Network-wide daily block revenue:
- Base & vote fees: 18.1% (~1,356 SOL/day)
- Priority fees: 64.9% (~5,032 SOL/day)
- Jito tips: 17.0% (~1,355 SOL/day)

MEV-related revenue (priority fees + Jito tips) as % of total income by tier:
- **Top tier (1M+ SOL):** 6.6%
- **Mid tier (100k-1M):** 25.3%
- **Small profitable:** 13.3%
- **Underwater:** 64.5%

During peak memecoin season (late 2024), Jito tips alone accounted for over 50% of all block revenue.

### Block Production & MEV Concentration
- Top 50 validators produce **54% of all blocks**; top 100 produce **71%**
- Top 10 validators capture **33.2% of MEV revenue** despite producing only **22.8% of blocks**

### Jito Dominance
- **98.1% of blocks** produced by Jito validators (770 out of 773)
- Peak extraction: **116,070 SOL** in a single epoch with only 441 Jito validators
- MEV dropped **97%** since peak, but Jito validator count nearly **doubled** (441 → 770)
- The extraction infrastructure is embedded in 98% of blocks and waiting for the next wave

### What's at Stake
The Alpenglow upgrade will reduce voting costs and potentially bring new validators online. But if every new validator also runs Jito — and there is currently no alternative — the extraction machine only grows. More validators with Jito doesn't mean more decentralization. It means more nodes running the same monopoly software. The network needs competing validator infrastructure that doesn't sell transaction ordering.

## Steps to Reproduce

### Prerequisites
- Docker Desktop
- Terraform
- Google Cloud SDK (`gcloud`)
- Python 3.11+
- A GCP project with billing enabled (free tier is sufficient)

### 1. Clone the repo
```bash
git clone https://github.com/SwagasaurusFLEX/Solana-Validator-Dashboard.git
cd Solana-Validator-Dashboard
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

# Download key
mkdir -p config
gcloud iam service-accounts keys create config/sa-key.json \
  --iam-account=solana-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Set up application default credentials
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
Airflow UI available at `http://localhost:8080` (admin/admin).

### 6. Run the pipeline
In the Airflow UI, enable the `solana_validator_pipeline` DAG and trigger a run. The pipeline will:
1. Extract Block Rewards and Blocks from BigQuery public Solana dataset
2. Extract SOL price from CoinGecko
3. Extract validator snapshot from Solana RPC
4. Extract MEV rewards from Jito API
5. Extract historical MEV data from Jito API
6. Export data to GCS as Parquet files
7. Load into the warehouse BigQuery dataset
8. Run dbt transformations to create fact tables

### 7. View the dashboard
```bash
pip install streamlit plotly google-cloud-bigquery pandas db-dtypes
streamlit run streamlit_app.py
```

## Project Structure
```
solana_validator_dashboard/
├── terraform/                    # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── airflow/
│   ├── dags/
│   │   └── solana_pipeline.py    # Airflow DAG
│   └── scripts/
│       ├── extract_solana_data.py
│       ├── extract_validator_snapshot.py
│       ├── extract_jito_mev.py
│       └── extract_jito_historical.py
├── dbt/
│   └── models/
│       ├── staging/              # stg_block_rewards, stg_blocks, stg_sol_price
│       ├── intermediate/         # int_validator_daily_rewards, int_validator_summary, int_daily_network_stats
│       └── marts/                # fct_validator_profitability, fct_network_risk, fct_reward_concentration, fct_validator_economics
├── streamlit_app.py              # Dashboard (7 sections)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .streamlit/secrets.toml       # GCP credentials (gitignored)
└── README.md
```

## Course
This project was built as the final capstone for the [Data Engineering Zoomcamp 2026](https://github.com/DataTalksClub/data-engineering-zoomcamp) by [DataTalks.Club](https://datatalks.club/).
