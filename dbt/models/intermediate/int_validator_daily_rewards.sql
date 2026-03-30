SELECT
    pubkey,
    reward_date,
    COUNT(*) AS reward_events,
    SUM(reward_sol) AS total_reward_sol,
    AVG(reward_sol) AS avg_reward_sol

FROM {{ ref('stg_block_rewards') }}

GROUP BY pubkey, reward_date