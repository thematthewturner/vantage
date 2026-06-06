{{ config(materialized='table') }}

-- Grain: company × as_of_date × method. Natural key all three.
-- Phase 0+: curated marks (public market cap, secondary, primary round) land in
-- `fact_valuation_seed`, each with a source_id. USD millions, DECIMAL.

SELECT
    company_id,
    as_of_date,
    valuation_usd,
    price_per_share,
    method,
    source_id
FROM {{ ref('fact_valuation_seed') }}
