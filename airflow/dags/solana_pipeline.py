"""
Solana Validator Economics Pipeline

DAG that orchestrates:
1. Extract block rewards from public BigQuery dataset
2. Extract blocks data
3. Extract SOL price from CoinGecko
4. Load data from GCS into warehouse BigQuery dataset
5. Run dbt transformations
"""

import os
import sys
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# Add scripts folder to path so we can import our extraction functions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from extract_solana_data import extract_block_rewards, extract_blocks, extract_sol_price


def load_to_warehouse():
    """Load Parquet files from GCS into the warehouse BigQuery dataset."""

    from google.cloud import bigquery

    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    warehouse_dataset = os.environ["BQ_DATASET_WAREHOUSE"]

    client = bigquery.Client(project=project_id)

    # Load block_rewards from GCS parquet into warehouse
    table_id = f"{project_id}.{warehouse_dataset}.raw_block_rewards"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition="WRITE_TRUNCATE",
    )

    uri = f"gs://{bucket_name}/raw/block_rewards/*.parquet"
    print(f"Loading {uri} into {table_id}")
    load_job = client.load_table_from_uri(uri, table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded block_rewards: {load_job.output_rows} rows")

    # Load blocks from GCS parquet into warehouse
    table_id = f"{project_id}.{warehouse_dataset}.raw_blocks"
    uri = f"gs://{bucket_name}/raw/blocks/*.parquet"
    print(f"Loading {uri} into {table_id}")
    load_job = client.load_table_from_uri(uri, table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded blocks: {load_job.output_rows} rows")

    # Load SOL price from GCS JSON into warehouse
    import json
    from google.cloud import storage

    storage_client = storage.Client(project=os.environ["GCP_PROJECT_ID"])
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("raw/sol_price/sol_daily_price.json")
    price_data = json.loads(blob.download_as_string())

    table_id = f"{project_id}.{warehouse_dataset}.raw_sol_price"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("date", "STRING"),
            bigquery.SchemaField("sol_price_usd", "FLOAT64"),
        ],
    )

    # Convert to newline-delimited JSON
    ndjson = "\n".join(json.dumps(row) for row in price_data)
    load_job = client.load_table_from_json(price_data, table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded sol_price: {load_job.output_rows} rows")


# DAG definition
default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="solana_validator_pipeline",
    default_args=default_args,
    description="Extract Solana validator data, load to warehouse, transform with dbt",
    schedule_interval="@weekly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["solana", "validators", "economics"],
) as dag:

    # Step 1: Extract block rewards from public dataset → staging + GCS
    task_extract_rewards = PythonOperator(
        task_id="extract_block_rewards",
        python_callable=extract_block_rewards,
    )

    # Step 2: Extract blocks from public dataset → staging + GCS
    task_extract_blocks = PythonOperator(
        task_id="extract_blocks",
        python_callable=extract_blocks,
    )

    # Step 3: Extract SOL price from CoinGecko → GCS
    task_extract_price = PythonOperator(
        task_id="extract_sol_price",
        python_callable=extract_sol_price,
    )

    # Step 4: Load from GCS into warehouse dataset
    task_load = PythonOperator(
        task_id="load_to_warehouse",
        python_callable=load_to_warehouse,
    )

    # Step 5: Run dbt transformations
    task_dbt = BashOperator(
        task_id="run_dbt",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir .",
    )

    # Define the pipeline order
    # Extracts run in parallel, then load, then transform
    [task_extract_rewards, task_extract_blocks, task_extract_price] >> task_load >> task_dbt