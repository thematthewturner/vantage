{{ config(materialized='table') }}

-- Per-company Bayesian prior on guidance accuracy.
--
-- Phase 0 = 0.50 uniform bootstrap (from fact_guidance_accuracy_seed).
-- Phase 1.5 = empirical Beta posterior updated from fact_historical_guidance:
--   prior  Beta(α=1, β=1)   → mean 0.50
--   each beat → α += 1
--   each miss → β += 1
--   posterior mean = α / (α + β)
--
-- "Beat" definition: realized >= guided midpoint (or single point). When
-- both seeds have a row for the same company, the empirical posterior
-- (n_observations > 0) wins; otherwise the bootstrap row carries.

WITH evidence AS (
    SELECT
        company_id,
        SUM(CASE WHEN realized_value >= guided_value THEN 1 ELSE 0 END) AS beats,
        SUM(CASE WHEN realized_value <  guided_value THEN 1 ELSE 0 END) AS misses,
        COUNT(*)                                                        AS n_obs,
        MAX(realization_date)                                           AS last_realized
    FROM {{ ref('fact_historical_guidance') }}
    WHERE guided_value IS NOT NULL AND realized_value IS NOT NULL
    GROUP BY company_id
), empirical AS (
    SELECT
        company_id,
        last_realized                                                 AS as_of_date,
        CAST((beats + 1.0) / (beats + misses + 2.0) AS DECIMAL(9, 6)) AS guidance_reliability,
        n_obs                                                         AS n_observations,
        'empirical'                                                   AS prior_strength,
        'src_historical_guidance_v0'                                  AS source_id
    FROM evidence
)
SELECT
    s.company_id,
    COALESCE(e.as_of_date,           s.as_of_date)           AS as_of_date,
    COALESCE(e.guidance_reliability, s.guidance_reliability) AS guidance_reliability,
    COALESCE(e.n_observations,       s.n_observations)       AS n_observations,
    COALESCE(e.prior_strength,       s.prior_strength)       AS prior_strength,
    COALESCE(e.source_id,            s.source_id)            AS source_id
FROM {{ ref('fact_guidance_accuracy_seed') }} s
LEFT JOIN empirical e ON e.company_id = s.company_id
