SELECT
    block_slot,
    block_hash,
    block_timestamp,
    pubkey,
    reward_type,
    lamports,
    lamports / 1e9 AS reward_sol,
    post_balance / 1e9 AS post_balance_sol,
    commission,
    DATE(block_timestamp) AS reward_date

FROM {{ source('raw', 'raw_block_rewards') }}

WHERE pubkey IS NOT NULL