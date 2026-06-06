{{ config(materialized='table') }}

-- Grain: company × fiscal_period × is_guidance. Natural key: (company_id, fiscal_period, is_guidance).
-- Populated by ingest/sec.py from XBRL `companyfacts`. All currency in USD millions, DECIMAL.
-- Guidance rows are *never* blended into actuals downstream — see metric_growth_yoy.

SELECT
    CAST(NULL AS VARCHAR)       AS company_id,
    CAST(NULL AS VARCHAR)       AS fiscal_period,    -- e.g. '2025FY', '2026Q1'
    CAST(NULL AS DATE)          AS period_end,
    CAST(NULL AS BOOLEAN)       AS is_guidance,
    CAST(NULL AS DECIMAL(20,4)) AS revenue,
    CAST(NULL AS DECIMAL(20,4)) AS gross_profit,
    CAST(NULL AS DECIMAL(9,6))  AS gross_margin,
    CAST(NULL AS DECIMAL(20,4)) AS opex,
    CAST(NULL AS DECIMAL(20,4)) AS adj_ebitda,
    CAST(NULL AS DECIMAL(20,4)) AS net_income,
    CAST(NULL AS DECIMAL(20,4)) AS free_cash_flow,
    CAST(NULL AS DECIMAL(20,4)) AS cash_and_sti,
    CAST(NULL AS VARCHAR)       AS source_id
WHERE 1 = 0
