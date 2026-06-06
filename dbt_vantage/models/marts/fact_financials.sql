{{ config(materialized='table') }}

-- Grain: company × fiscal_period × is_guidance. Natural key: (company_id, fiscal_period, is_guidance).
-- Phase 0+: curated/analyst figures land in `fact_financials_seed` (every row carries a
-- source_id). Phase 1 will UNION ALL with XBRL-derived `raw_fact_financials`.
-- All currency in USD millions, DECIMAL. Guidance rows never blended into actuals downstream.

SELECT
    company_id,
    fiscal_period,
    period_end,
    is_guidance,
    revenue,
    gross_profit,
    gross_margin,
    opex,
    adj_ebitda,
    net_income,
    free_cash_flow,
    cash_and_sti,
    source_id
FROM {{ ref('fact_financials_seed') }}
