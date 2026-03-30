"""
Extract Solana Block Rewards and Blocks data from the BigQuery public dataset,
save as Parquet files to GCS (data lake).
"""

import os
from datetime import datetime, timedelta
from google.cloud import bigquery, storage


def extract_block_rewards():
    """Pull block rewards data for the last N days and upload to GCS as Parquet."""

    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    source_dataset = os.environ["SOLANA_PUBLIC_DATASET"]
    extract_days = int(os.environ.get("EXTRACT_DAYS", 90))

    client = bigquery.Client(project=project_id)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=extract_days)

    print(f"Extracting Block Rewards from {start_date.date()} to {end_date.date()}")

    query = f"""
        SELECT
            block_slot,
            block_hash,
            block_timestamp,
            commission,
            lamports,
            post_balance,
            pubkey,
            reward_type
        FROM `{source_dataset}.Block Rewards`
        WHERE block_timestamp >= TIMESTAMP('{start_date.strftime('%Y-%m-%d')}')
          AND block_timestamp < TIMESTAMP('{end_date.strftime('%Y-%m-%d')}')
    """

    job_config = bigquery.QueryJobConfig(
        destination=f"{project_id}.{os.environ['BQ_DATASET_STAGING']}.raw_block_rewards",
        write_disposition="WRITE_TRUNCATE",
    )

    print("Running query...")
    query_job = client.query(query, job_config=job_config)
    query_job.result()
    print(f"Query complete. {query_job.total_bytes_processed / 1e9:.2f} GB processed")

    table_ref = f"{project_id}.{os.environ['BQ_DATASET_STAGING']}.raw_block_rewards"
    gcs_uri = f"gs://{bucket_name}/raw/block_rewards/*.parquet"

    extract_job = client.extract_table(
        table_ref,
        gcs_uri,
        job_config=bigquery.ExtractJobConfig(
            destination_format=bigquery.DestinationFormat.PARQUET
        ),
    )
    extract_job.result()
    print(f"Exported block_rewards to {gcs_uri}")


def extract_blocks():
    """Pull blocks data for the last N days and upload to GCS as Parquet."""

    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    source_dataset = os.environ["SOLANA_PUBLIC_DATASET"]
    extract_days = int(os.environ.get("EXTRACT_DAYS", 90))

    client = bigquery.Client(project=project_id)

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=extract_days)

    print(f"Extracting Blocks from {start_date.date()} to {end_date.date()}")

    query = f"""
        SELECT
            slot,
            block_hash,
            block_timestamp,
            height,
            previous_block_hash,
            transaction_count,
            leader_reward,
            leader
        FROM `{source_dataset}.Blocks`
        WHERE block_timestamp >= TIMESTAMP('{start_date.strftime('%Y-%m-%d')}')
          AND block_timestamp < TIMESTAMP('{end_date.strftime('%Y-%m-%d')}')
    """

    job_config = bigquery.QueryJobConfig(
        destination=f"{project_id}.{os.environ['BQ_DATASET_STAGING']}.raw_blocks",
        write_disposition="WRITE_TRUNCATE",
    )

    print("Running query...")
    query_job = client.query(query, job_config=job_config)
    query_job.result()
    print(f"Query complete. {query_job.total_bytes_processed / 1e9:.2f} GB processed")

    table_ref = f"{project_id}.{os.environ['BQ_DATASET_STAGING']}.raw_blocks"
    gcs_uri = f"gs://{bucket_name}/raw/blocks/*.parquet"

    extract_job = client.extract_table(
        table_ref,
        gcs_uri,
        job_config=bigquery.ExtractJobConfig(
            destination_format=bigquery.DestinationFormat.PARQUET
        ),
    )
    extract_job.result()
    print(f"Exported blocks to {gcs_uri}")


def extract_sol_price():
    """Pull daily SOL/USD price from CoinGecko free API and upload to GCS."""

    import requests
    import json

    bucket_name = os.environ["GCS_BUCKET_NAME"]
    extract_days = int(os.environ.get("EXTRACT_DAYS", 90))

    print(f"Fetching {extract_days} days of SOL price data from CoinGecko")

    url = "https://api.coingecko.com/api/v3/coins/solana/market_chart"
    params = {"vs_currency": "usd", "days": extract_days, "interval": "daily"}

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    prices = []
    for timestamp_ms, price in data["prices"]:
        dt = datetime.utcfromtimestamp(timestamp_ms / 1000)
        prices.append({"date": dt.strftime("%Y-%m-%d"), "sol_price_usd": round(price, 2)})

    storage_client = storage.Client(project=os.environ["GCP_PROJECT_ID"])
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("raw/sol_price/sol_daily_price.json")
    blob.upload_from_string(json.dumps(prices), content_type="application/json")

    print(f"Uploaded {len(prices)} days of SOL price data to GCS")


if __name__ == "__main__":
    extract_block_rewards()
    extract_blocks()
    extract_sol_price()
