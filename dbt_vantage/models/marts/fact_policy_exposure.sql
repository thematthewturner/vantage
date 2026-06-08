{{ config(materialized='table') }}

-- Per-company policy-exposure scores on 0-5 ordinal scale.
-- Grain: company_id (latest analyst scoring). Phase 0 hand-curated from
-- segment/business-model knowledge; refreshed quarterly off live filings.

SELECT
    company_id,
    ma_rate_exposure,
    aca_aptc_exposure,
    cmmi_model_dependence,
    rationale,
    source_id
FROM {{ ref('fact_policy_exposure_seed') }}
