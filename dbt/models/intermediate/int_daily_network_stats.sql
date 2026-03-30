SELECT
    reward_date,
    COUNT(DISTINCT pubkey) AS active_validators,
    SUM(total_reward_sol) AS total_network_rewards_sol,
    AVG(total_reward_sol) AS avg_validator_reward_sol,
    APPROX_QUANTILES(total_reward_sol, 100)[OFFSET(50)] AS median_validator_reward_sol,
    APPROX_QUANTILES(total_reward_sol, 100)[OFFSET(25)] AS p25_validator_reward_sol,
    APPROX_QUANTILES(total_reward_sol, 100)[OFFSET(75)] AS p75_validator_reward_sol

FROM {{ ref('int_validator_daily_rewards') }}

GROUP BY reward_date