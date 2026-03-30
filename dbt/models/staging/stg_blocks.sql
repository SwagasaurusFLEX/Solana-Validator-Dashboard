SELECT
    slot,
    block_hash,
    block_timestamp,
    height,
    previous_block_hash,
    transaction_count,
    leader_reward,
    leader,
    DATE(block_timestamp) AS block_date

FROM {{ source('raw', 'raw_blocks') }}