WITH daily_validators AS (
    SELECT
        d.reward_date,
        d.pubkey,
        d.total_reward_sol AS daily_reward_sol,
        CASE WHEN d.total_reward_sol >= 1.1 THEN 1 ELSE 0 END AS covers_vote_cost,
        p.sol_price_usd

    FROM {{ ref('int_validator_daily_rewards') }} d
    LEFT JOIN {{ ref('stg_sol_price') }} p
        ON d.reward_date = p.price_date
),

daily_risk AS (
    SELECT
        reward_date,
        sol_price_usd,
        COUNT(DISTINCT pubkey) AS total_validators,
        SUM(covers_vote_cost) AS validators_covering_votes,
        COUNT(DISTINCT pubkey) - SUM(covers_vote_cost) AS validators_underwater_votes,

        ROUND(
            (COUNT(DISTINCT pubkey) - SUM(covers_vote_cost))
            * 100.0 / COUNT(DISTINCT pubkey),
            1
        ) AS pct_underwater_votes,

        SUM(
            CASE
                WHEN sol_price_usd IS NOT NULL
                    AND (daily_reward_sol - 1.1) * 30 * sol_price_usd >= 2000
                THEN 1 ELSE 0
            END
        ) AS validators_fully_profitable,

        ROUND(
            SUM(
                CASE
                    WHEN sol_price_usd IS NOT NULL
                        AND (daily_reward_sol - 1.1) * 30 * sol_price_usd >= 2000
                    THEN 1 ELSE 0
                END
            ) * 100.0 / COUNT(DISTINCT pubkey),
            1
        ) AS pct_fully_profitable

    FROM daily_validators
    GROUP BY reward_date, sol_price_usd
)

SELECT
    reward_date,
    sol_price_usd,
    total_validators,
    validators_covering_votes,
    validators_underwater_votes,
    pct_underwater_votes,
    validators_fully_profitable,
    pct_fully_profitable,

    CASE
        WHEN pct_fully_profitable >= 80 THEN 'low_risk'
        WHEN pct_fully_profitable >= 50 THEN 'moderate_risk'
        WHEN pct_fully_profitable >= 30 THEN 'high_risk'
        ELSE 'critical_risk'
    END AS network_risk_level

FROM daily_risk

ORDER BY reward_date