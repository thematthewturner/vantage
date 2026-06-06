{{ config(materialized='table') }}

-- Grain: company × scenario × fiscal_year. Natural key all three + generated_at.
-- `assumptions` is a queryable JSON object so the scenario can be re-derived.
-- Written by engine/scenarios.py (Phase 4).

SELECT
    CAST(NULL AS VARCHAR)       AS company_id,
    CAST(NULL AS VARCHAR)       AS scenario,           -- 'base'|'bull'|'bear'
    CAST(NULL AS INTEGER)       AS fiscal_year,
    CAST(NULL AS DECIMAL(20,4)) AS projected_revenue,
    CAST(NULL AS DECIMAL(9,6))  AS cagr,
    CAST(NULL AS JSON)          AS assumptions,
    CAST(NULL AS TIMESTAMP)     AS generated_at,
    CAST(NULL AS VARCHAR)       AS method
WHERE 1 = 0
