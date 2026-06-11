{{ config(materialized='table') }}

-- Per-(company, fiscal_period, metric) historical guidance vs realized.
-- Phase 0 = header-only. Phase 1.5 backtest populates via the content
-- harvest pipeline reading 8-K MD&A guidance and matching to the next
-- reported actual. Every row carries TWO source_ids — one for the
-- guidance issuance, one for the realization — since both are auditable
-- artifacts.

SELECT
    company_id,
    fiscal_period,
    metric,
    CAST(guided_value AS DECIMAL(20, 4))    AS guided_value,
    CAST(realized_value AS DECIMAL(20, 4))  AS realized_value,
    CAST(guidance_issued_date AS DATE)      AS guidance_issued_date,
    CAST(realization_date AS DATE)          AS realization_date,
    source_id_guidance,
    source_id_actual
FROM {{ ref('fact_historical_guidance_seed') }}
