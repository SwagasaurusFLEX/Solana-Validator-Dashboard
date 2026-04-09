"""
Pull a live snapshot of all Solana validators from the RPC API.
Gets activated stake, commission, vote credits, and status for every validator.
"""

import os
import json
import requests
from datetime import datetime
from google.cloud import bigquery, storage


def extract_validator_snapshot():
    """Call Solana RPC getVoteAccounts and save to GCS + BigQuery."""

    project_id = os.environ["GCP_PROJECT_ID"]
    bucket_name = os.environ["GCS_BUCKET_NAME"]

    print("Pulling validator snapshot from Solana RPC...")

    response = requests.post(
        "https://api.mainnet-beta.solana.com",
        json={"jsonrpc": "2.0", "id": 1, "method": "getVoteAccounts"},
    )
    response.raise_for_status()
    data = response.json()["result"]

    snapshot_date = datetime.utcnow().strftime("%Y-%m-%d")
    snapshot_ts = datetime.utcnow().isoformat()

    rows = []

    for validator in data["current"]:
        rows.append({
            "snapshot_date": snapshot_date,
            "snapshot_timestamp": snapshot_ts,
            "vote_pubkey": validator["votePubkey"],
            "node_pubkey": validator["nodePubkey"],
            "activated_stake_lamports": validator["activatedStake"],
            "activated_stake_sol": round(validator["activatedStake"] / 1e9, 2),
            "commission": validator["commission"],
            "last_vote": validator["lastVote"],
            "root_slot": validator["rootSlot"],
            "epoch_vote_account": validator["epochVoteAccount"],
            "status": "current",
            "epoch_credits": json.dumps(validator["epochCredits"]),
        })

    for validator in data["delinquent"]:
        rows.append({
            "snapshot_date": snapshot_date,
            "snapshot_timestamp": snapshot_ts,
            "vote_pubkey": validator["votePubkey"],
            "node_pubkey": validator["nodePubkey"],
            "activated_stake_lamports": validator["activatedStake"],
            "activated_stake_sol": round(validator["activatedStake"] / 1e9, 2),
            "commission": validator["commission"],
            "last_vote": validator["lastVote"],
            "root_slot": validator["rootSlot"],
            "epoch_vote_account": validator["epochVoteAccount"],
            "status": "delinquent",
            "epoch_credits": json.dumps(validator["epochCredits"]),
        })

    print(f"Got {len(rows)} validators ({len(data['current'])} active, {len(data['delinquent'])} delinquent)")

    # Save to GCS
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"raw/validator_snapshots/{snapshot_date}.json")
    blob.upload_from_string(
        "\n".join(json.dumps(row) for row in rows),
        content_type="application/json",
    )
    print(f"Saved snapshot to GCS: raw/validator_snapshots/{snapshot_date}.json")

    # Load to BigQuery
    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{os.environ['BQ_DATASET_WAREHOUSE']}.raw_validator_snapshots"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition="WRITE_APPEND",
        schema=[
            bigquery.SchemaField("snapshot_date", "STRING"),
            bigquery.SchemaField("snapshot_timestamp", "STRING"),
            bigquery.SchemaField("vote_pubkey", "STRING"),
            bigquery.SchemaField("node_pubkey", "STRING"),
            bigquery.SchemaField("activated_stake_lamports", "INTEGER"),
            bigquery.SchemaField("activated_stake_sol", "FLOAT64"),
            bigquery.SchemaField("commission", "INTEGER"),
            bigquery.SchemaField("last_vote", "INTEGER"),
            bigquery.SchemaField("root_slot", "INTEGER"),
            bigquery.SchemaField("epoch_vote_account", "BOOLEAN"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("epoch_credits", "STRING"),
        ],
    )

    load_job = client.load_table_from_json(rows, table_id, job_config=job_config)
    load_job.result()
    print(f"Loaded {load_job.output_rows} rows to BigQuery")


if __name__ == "__main__":
    extract_validator_snapshot()