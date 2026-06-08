{{ config(materialized='table') }}

-- Per-company Bayesian prior on guidance accuracy. Phase 0 bootstrap = 0.50
-- uniform; Phase 1.5 backtest replaces with empirical posteriors from
-- historical guidance-vs-actuals harvested out of 8-K/10-Q filings.

SELECT
    company_id,
    as_of_date,
    guidance_reliability,
    n_observations,
    prior_strength,
    source_id
FROM {{ ref('fact_guidance_accuracy_seed') }}
