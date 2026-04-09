"""
Pull historical Jito MEV data across epochs to show trends over time.
"""

import os
import json
import requests
from google.cloud import bigquery, storage


def extract_jito_historical():
    """Pull MEV stats for sampled epochs from 2023 to present."""

    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    warehouse_dataset = os.environ["BQ_DATASET_WAREHOUSE"]

    # Get current epoch
    epoch_response = requests.post(
        "https://api.mainnet-beta.solana.com",
        json={"jsonrpc": "2.0", "id": 1, "method": "getEpochInfo"},
    )
    current_epoch = epoch_response.json()["result"]["epoch"]

    # Sample every 10 epochs from 400 to current
    epochs = list(range(400, current_epoch + 1, 10))
    # Make sure current epoch is included
    if current_epoch not in epochs:
        epochs.append(current_epoch)

    all_rows = []

    for epoch in epochs:
        try:
            # Network-level MEV
            mev_r = requests.post(
                "https://kobe.mainnet.jito.network/api/v1/mev_rewards",
                json={"epoch": epoch},
                headers={"Content-Type": "application/json"},
            )
            mev_data = mev_r.json()
            total_mev_lamports = mev_data.get("total_network_mev_lamports", 0)
            total_mev_sol = round(total_mev_lamports / 1e9, 4)

            # Validator count and concentration
            val_r = requests.post(
                "https://kobe.mainnet.jito.network/api/v1/jitosol_validators",
                json={"epoch": epoch},
                headers={"Content-Type": "application/json"},
            )
            val_data = val_r.json()
            validators = val_data.get("validators", [])
            num_validators = len(validators)

            # Calculate MEV concentration for this epoch
            if validators:
                mev_amounts = sorted(
                    [v["mev_rewards"] / 1e9 for v in validators],
                    reverse=True,
                )
                total = sum(mev_amounts)
                top_10_mev = sum(mev_amounts[:10]) if len(mev_amounts) >= 10 else total
                top_50_mev = sum(mev_amounts[:50]) if len(mev_amounts) >= 50 else total
                top_10_pct = round(top_10_mev / total * 100, 1) if total > 0 else 0
                top_50_pct = round(top_50_mev / total * 100, 1) if total > 0 else 0
            else:
                top_10_pct = 0
                top_50_pct = 0

            all_rows.append({
                "epoch": epoch,
                "total_mev_sol": total_mev_sol,
                "jito_validator_count": num_validators,
                "mev_top_10_pct": top_10_pct,
                "mev_top_50_pct": top_50_pct,
            })

            print(f"Epoch {epoch}: {total_mev_sol} SOL MEV, {num_validators} validators, top 10 = {top_10_pct}%")

        except Exception as e:
            print(f"Epoch {epoch}: Error - {e}")
            continue

    print(f"\nTotal epochs collected: {len(all_rows)}")

    # Save to GCS
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("raw/jito_historical/mev_trends.json")
    blob.upload_from_string(
        "\n".join(json.dumps(row) for row in all_rows),
        content_type="application/json",
    )
    print("Saved to GCS")

    # Load to BigQuery
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{warehouse_dataset}.raw_jito_historical"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("epoch", "INTEGER"),
            bigquery.SchemaField("total_mev_sol", "FLOAT64"),
            bigquery.SchemaField("jito_validator_count", "INTEGER"),
            bigquery.SchemaField("mev_top_10_pct", "FLOAT64"),
            bigquery.SchemaField("mev_top_50_pct", "FLOAT64"),
        ],
    )

    load_job = client.load_table_from_json(all_rows, table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded {load_job.output_rows} rows to BigQuery")


if __name__ == "__main__":
    extract_jito_historical()
