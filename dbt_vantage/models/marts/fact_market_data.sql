{{ config(materialized='table') }}

-- Per-company point-in-time market snapshot (publics only).
-- Grain: (company_id, as_of_date). Phase 0.5 sourced from estimates;
-- Phase 1+ overlays XBRL companyfacts with reliability='primary'.

SELECT
    company_id,
    as_of_date,
    shares_diluted,
    close_price,
    CAST(shares_diluted * close_price AS DECIMAL(20, 4)) AS market_cap,
    total_debt,
    source_id
FROM {{ ref('fact_market_data_seed') }}
