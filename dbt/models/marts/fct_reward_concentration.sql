WITH daily_ranked AS (
    SELECT
        reward_date,
        pubkey,
        total_reward_sol,
        SUM(total_reward_sol) OVER (PARTITION BY reward_date) AS daily_total_rewards,
        ROW_NUMBER() OVER (PARTITION BY reward_date ORDER BY total_reward_sol DESC) AS reward_rank

    FROM {{ ref('int_validator_daily_rewards') }}
),

concentration AS (
    SELECT
        reward_date,
        COUNT(DISTINCT pubkey) AS total_validators,
        MAX(daily_total_rewards) AS total_rewards_sol,

        SUM(CASE WHEN reward_rank <= 10 THEN total_reward_sol ELSE 0 END)
            / MAX(daily_total_rewards) * 100 AS pct_top_10,

        SUM(CASE WHEN reward_rank <= 50 THEN total_reward_sol ELSE 0 END)
            / MAX(daily_total_rewards) * 100 AS pct_top_50,

        SUM(CASE WHEN reward_rank <= 100 THEN total_reward_sol ELSE 0 END)
            / MAX(daily_total_rewards) * 100 AS pct_top_100,

        MIN(CASE
            WHEN cumulative_pct >= 33 THEN reward_rank
            ELSE NULL
        END) AS nakamoto_coefficient

    FROM (
        SELECT
            *,
            SUM(total_reward_sol) OVER (
                PARTITION BY reward_date
                ORDER BY total_reward_sol DESC
                ROWS UNBOUNDED PRECEDING
            ) / daily_total_rewards * 100 AS cumulative_pct
        FROM daily_ranked
    )
    GROUP BY reward_date
)

SELECT
    reward_date,
    total_validators,
    ROUND(total_rewards_sol, 2) AS total_rewards_sol,
    ROUND(pct_top_10, 1) AS pct_rewards_top_10,
    ROUND(pct_top_50, 1) AS pct_rewards_top_50,
    ROUND(pct_top_100, 1) AS pct_rewards_top_100,
    nakamoto_coefficient,

    CASE
        WHEN nakamoto_coefficient >= 30 THEN 'healthy'
        WHEN nakamoto_coefficient >= 20 THEN 'moderate'
        WHEN nakamoto_coefficient >= 10 THEN 'concerning'
        ELSE 'critical'
    END AS decentralization_status

FROM concentration

ORDER BY reward_date