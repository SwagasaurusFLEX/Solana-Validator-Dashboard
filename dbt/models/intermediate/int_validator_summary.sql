SELECT
    pubkey,
    COUNT(DISTINCT reward_date) AS active_days,
    SUM(total_reward_sol) AS total_earned_sol,
    AVG(total_reward_sol) AS avg_daily_reward_sol,
    MIN(total_reward_sol) AS min_daily_reward_sol,
    MAX(total_reward_sol) AS max_daily_reward_sol,
    MIN(reward_date) AS first_seen,
    MAX(reward_date) AS last_seen

FROM {{ ref('int_validator_daily_rewards') }}

GROUP BY pubkey