{{ config(materialized='table') }}

-- Grain: company × fiscal_period × life_type. Natural key all three.
-- `life_type` is the denominator-discipline column — every metric that joins
-- against this fact must join on a matching life_type, never collapse across.

SELECT
    company_id,
    fiscal_period,
    life_type,
    lives_count,
    source_id
FROM {{ ref('fact_covered_lives_seed') }}
