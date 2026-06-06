{{ config(materialized='table') }}

-- Per-company policy-exposure scores. Grain: company_id (latest scoring;
-- history kept via incremental snapshot in Phase 4+). Scores are 0-5 ordinal.
-- Written by engine/policy.py.

SELECT
    CAST(NULL AS VARCHAR) AS company_id,
    CAST(NULL AS INTEGER) AS ma_rate_exposure,        -- 0-5
    CAST(NULL AS INTEGER) AS aca_aptc_exposure,       -- 0-5
    CAST(NULL AS INTEGER) AS cmmi_model_dependence,   -- 0-5
    CAST(NULL AS VARCHAR) AS rationale,
    CAST(NULL AS VARCHAR) AS source_id
WHERE 1 = 0
