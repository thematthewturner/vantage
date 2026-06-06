{{ config(materialized='table') }}

-- Grain: company × as_of_date × method. Natural key all three.
-- valuation_usd is total enterprise/equity value depending on method (documented
-- in metric layer). USD millions, DECIMAL.

SELECT
    CAST(NULL AS VARCHAR)       AS company_id,
    CAST(NULL AS DATE)          AS as_of_date,
    CAST(NULL AS DECIMAL(20,4)) AS valuation_usd,
    CAST(NULL AS DECIMAL(20,6)) AS price_per_share,
    CAST(NULL AS VARCHAR)       AS method,
    CAST(NULL AS VARCHAR)       AS source_id
WHERE 1 = 0
