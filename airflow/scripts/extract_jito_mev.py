"""
Pull Jito MEV reward data per validator for recent epochs.
"""

import os
import json
import requests
from google.cloud import bigquery, storage


def extract_jito_mev():
    """Pull MEV rewards from Jito API for the last 5 epochs and save to BigQuery."""

    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    warehouse_dataset = os.environ["BQ_DATASET_WAREHOUSE"]

    # Get current epoch from Solana RPC
    epoch_response = requests.post(
        "https://api.mainnet-beta.solana.com",
        json={"jsonrpc": "2.0", "id": 1, "method": "getEpochInfo"},
    )
    current_epoch = epoch_response.json()["result"]["epoch"]
    print(f"Current epoch: {current_epoch}")

    all_rows = []

    # Pull last 5 epochs
    for epoch in range(current_epoch - 4, current_epoch + 1):
        print(f"Pulling Jito data for epoch {epoch}...")

        try:
            r = requests.post(
                "https://kobe.mainnet.jito.network/api/v1/jitosol_validators",
                json={"epoch": epoch},
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()

            # Also get network-level MEV stats
            mev_r = requests.post(
                "https://kobe.mainnet.jito.network/api/v1/mev_rewards",
                json={"epoch": epoch},
                headers={"Content-Type": "application/json"},
            )
            mev_data = mev_r.json()
            total_network_mev = mev_data.get("total_network_mev_lamports", 0)

            for v in data["validators"]:
                all_rows.append({
                    "epoch": epoch,
                    "vote_account": v["vote_account"],
                    "identity_account": v.get("identity_account", ""),
                    "mev_rewards_lamports": v["mev_rewards"],
                    "mev_rewards_sol": round(v["mev_rewards"] / 1e9, 6),
                    "mev_commission_bps": v["mev_commission_bps"],
                    "priority_fee_rewards_lamports": v.get("priority_fee_rewards") or 0,
                    "priority_fee_rewards_sol": round((v.get("priority_fee_rewards") or 0) / 1e9, 6),
                    "running_jito": v["running_jito"],
                    "running_bam": v.get("running_bam", False),
                    "active_stake_sol": round(v["active_stake"] / 1e9, 2),
                    "total_network_mev_lamports": total_network_mev,
                    "total_network_mev_sol": round(total_network_mev / 1e9, 4),
                })

            print(f"  Epoch {epoch}: {len(data['validators'])} validators, {round(total_network_mev / 1e9, 2)} SOL total MEV")

        except Exception as e:
            print(f"  Error on epoch {epoch}: {e}")
            continue

    print(f"\nTotal rows: {len(all_rows)}")

    # Save to GCS
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob("raw/jito_mev/latest.json")
    blob.upload_from_string(
        "\n".join(json.dumps(row) for row in all_rows),
        content_type="application/json",
    )
    print("Saved to GCS")

    # Load to BigQuery
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{warehouse_dataset}.raw_jito_mev"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition="WRITE_TRUNCATE",
        schema=[
            bigquery.SchemaField("epoch", "INTEGER"),
            bigquery.SchemaField("vote_account", "STRING"),
            bigquery.SchemaField("identity_account", "STRING"),
            bigquery.SchemaField("mev_rewards_lamports", "INTEGER"),
            bigquery.SchemaField("mev_rewards_sol", "FLOAT64"),
            bigquery.SchemaField("mev_commission_bps", "INTEGER"),
            bigquery.SchemaField("priority_fee_rewards_lamports", "INTEGER"),
            bigquery.SchemaField("priority_fee_rewards_sol", "FLOAT64"),
            bigquery.SchemaField("running_jito", "BOOLEAN"),
            bigquery.SchemaField("running_bam", "BOOLEAN"),
            bigquery.SchemaField("active_stake_sol", "FLOAT64"),
            bigquery.SchemaField("total_network_mev_lamports", "INTEGER"),
            bigquery.SchemaField("total_network_mev_sol", "FLOAT64"),
        ],
    )

    load_job = client.load_table_from_json(all_rows, table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded {load_job.output_rows} rows to BigQuery")


if __name__ == "__main__":
    extract_jito_mev()
