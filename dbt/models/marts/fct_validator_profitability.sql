WITH validator_economics AS (
    SELECT
        v.pubkey,
        v.active_days,
        v.total_earned_sol,
        v.avg_daily_reward_sol,
        1.1 AS daily_vote_cost_sol,
        v.avg_daily_reward_sol - 1.1 AS net_daily_sol_after_votes,
        (v.avg_daily_reward_sol - 1.1) * 30 AS net_monthly_sol

    FROM {{ ref('int_validator_summary') }} v
)

SELECT
    pubkey,
    active_days,
    total_earned_sol,
    avg_daily_reward_sol,
    daily_vote_cost_sol,
    net_daily_sol_after_votes,
    net_monthly_sol,

    CASE
        WHEN net_monthly_sol > 0
        THEN ROUND(1000.0 / net_monthly_sol, 2)
        ELSE NULL
    END AS breakeven_sol_price_low_cost,

    CASE
        WHEN net_monthly_sol > 0
        THEN ROUND(2000.0 / net_monthly_sol, 2)
        ELSE NULL
    END AS breakeven_sol_price_mid_cost,

    CASE
        WHEN net_monthly_sol > 0
        THEN ROUND(3000.0 / net_monthly_sol, 2)
        ELSE NULL
    END AS breakeven_sol_price_high_cost,

    CASE
        WHEN net_daily_sol_after_votes > 0 THEN 'profitable_in_sol'
        ELSE 'unprofitable_in_sol'
    END AS sol_profitability_status,

    CASE
        WHEN avg_daily_reward_sol >= 10 THEN 'whale'
        WHEN avg_daily_reward_sol >= 2 THEN 'medium'
        WHEN avg_daily_reward_sol >= 1.1 THEN 'small_profitable'
        ELSE 'underwater'
    END AS validator_tier

FROM validator_economics