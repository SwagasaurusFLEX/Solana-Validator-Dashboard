-- Fact: complete validator economics combining rewards with stake data
-- Pure math, no assumptions. What does the chain tell us?

WITH rewards AS (
    SELECT
        pubkey,
        active_days,
        total_earned_sol,
        avg_daily_reward_sol,
        avg_daily_reward_sol - 1.1 AS net_daily_sol
    FROM {{ ref('int_validator_summary') }}
),

stakes AS (
    SELECT
        vote_pubkey,
        activated_stake_sol,
        commission,
        status
    FROM `zoomcamp-test-2.solana_validator_economics.raw_validator_snapshots`
    WHERE snapshot_date = (
        SELECT MAX(snapshot_date)
        FROM `zoomcamp-test-2.solana_validator_economics.raw_validator_snapshots`
    )
),

combined AS (
    SELECT
        s.vote_pubkey,
        s.activated_stake_sol,
        s.commission,
        s.status,
        COALESCE(r.active_days, 0) AS active_days,
        COALESCE(r.total_earned_sol, 0) AS total_earned_sol,
        COALESCE(r.avg_daily_reward_sol, 0) AS avg_daily_reward_sol,
        COALESCE(r.net_daily_sol, -1.1) AS net_daily_sol,
        COALESCE(r.net_daily_sol, -1.1) * 30 AS net_monthly_sol,
        COALESCE(r.net_daily_sol, -1.1) * 365 AS net_annual_sol,

        -- Annual return on staked SOL
        CASE
            WHEN s.activated_stake_sol > 0
            THEN ROUND((COALESCE(r.net_daily_sol, -1.1) * 365) / s.activated_stake_sol * 100, 4)
            ELSE NULL
        END AS annual_return_pct,

        -- Net daily in USD
        COALESCE(r.net_daily_sol, -1.1) * (
            SELECT sol_price_usd
            FROM {{ ref('stg_sol_price') }}
            ORDER BY price_date DESC
            LIMIT 1
        ) AS net_daily_usd,

        -- Simple status: making or losing SOL
        CASE
            WHEN COALESCE(r.net_daily_sol, -1.1) > 0 THEN 'profitable'
            ELSE 'unprofitable'
        END AS profitability_status

    FROM stakes s
    LEFT JOIN rewards r
        ON s.vote_pubkey = r.pubkey
)

SELECT * FROM combined
ORDER BY activated_stake_sol DESC
