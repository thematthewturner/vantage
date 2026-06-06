{{ config(materialized='table') }}

SELECT
    segment,
    denominator_class,
    default_life_type,
    typical_rev_per_unit_low,
    typical_rev_per_unit_high,
    notes
FROM {{ ref('dim_segment_seed') }}
