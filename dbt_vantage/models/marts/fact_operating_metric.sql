{{ config(materialized='table') }}

-- Flexible EAV for anything that isn't financials or covered-lives: providers,
-- tests, MLR, Stars, retention, etc. Grain: company × fiscal_period × metric_name.
-- metric_value is DECIMAL — never floats.

SELECT
    CAST(NULL AS VARCHAR)       AS company_id,
    CAST(NULL AS VARCHAR)       AS fiscal_period,
    CAST(NULL AS VARCHAR)       AS metric_name,
    CAST(NULL AS DECIMAL(28,8)) AS metric_value,
    CAST(NULL AS VARCHAR)       AS unit,
    CAST(NULL AS VARCHAR)       AS source_id
WHERE 1 = 0
