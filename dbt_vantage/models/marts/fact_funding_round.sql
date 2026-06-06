{{ config(materialized='table') }}

-- Grain: one row per funding round. Natural key: round_id (deterministic hash of
-- company_id + announced_date + round_type + amount_usd, built by the loader).
-- `lead_investors` is stored in the seed as a ';'-delimited string and split into
-- the VARCHAR[] array here. amount_usd / post_money_valuation are USD millions, DECIMAL.

SELECT
    round_id,
    company_id,
    announced_date,
    round_type,
    amount_usd,
    post_money_valuation,
    CASE
        WHEN lead_investors_raw IS NULL OR lead_investors_raw = ''
            THEN CAST([] AS VARCHAR[])
        ELSE string_split(lead_investors_raw, ';')
    END AS lead_investors,
    source_id
FROM {{ ref('fact_funding_round_seed') }}
