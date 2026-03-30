-- Staging model: daily SOL/USD price from CoinGecko

SELECT
    PARSE_DATE('%Y-%m-%d', date) AS price_date,
    sol_price_usd

FROM {{ source('raw', 'raw_sol_price') }}