{{ config(materialized='view') }}

-- Index #5: denominator-discipline + policy-exposure composite.
-- A "balance sheet of risk" that modifies the demanded margin of safety
-- on top of the valuation index. Higher score = wider cushion required.
--
-- Inputs:
--   * Policy exposure: sum of three ordinal axes (0-5 each).
--   * Denominator volatility: bucket by denominator_class × default_life_type.
--     At-risk capitated lives are the noisiest; provider/contract denomination
--     is the cleanest. SaaS/data revenue has minimal denominator drift.
--
-- Output is a 0-1 normalized risk_score plus a categorical wide/normal/tight
-- recommendation on how much margin of safety to demand.

WITH base AS (
    SELECT
        l.company_id,
        l.ticker,
        l.business_model,
        l.denominator_class,
        l.default_life_type,
        COALESCE(p.ma_rate_exposure, 0)      AS ma_rate_exposure,
        COALESCE(p.aca_aptc_exposure, 0)     AS aca_aptc_exposure,
        COALESCE(p.cmmi_model_dependence, 0) AS cmmi_dependence
    FROM {{ ref('metric_company_latest') }} l
    LEFT JOIN {{ ref('fact_policy_exposure') }} p ON p.company_id = l.company_id
    WHERE l.ticker IS NOT NULL
), denom AS (
    SELECT
        *,
        ma_rate_exposure + aca_aptc_exposure + cmmi_dependence AS policy_exposure_total,
        -- Denominator volatility on a 0-5 scale. At-risk capitation > attributed
        -- shared-savings > eligible > subscriber > provider/contract billing.
        CASE
            WHEN denominator_class = 'covered_life' AND default_life_type = 'at_risk'    THEN 5
            WHEN denominator_class = 'covered_life' AND default_life_type = 'enrolled'   THEN 4
            WHEN denominator_class = 'covered_life' AND default_life_type = 'attributed' THEN 4
            WHEN denominator_class = 'covered_life' AND default_life_type = 'eligible'   THEN 2
            WHEN denominator_class = 'covered_life' AND default_life_type = 'subscriber' THEN 2
            WHEN denominator_class = 'provider'                                          THEN 1
            WHEN denominator_class = 'test'                                              THEN 2
            WHEN denominator_class = 'contract'                                          THEN 1
            ELSE 2
        END AS denominator_volatility
    FROM base
)
SELECT
    company_id,
    ticker,
    business_model,
    denominator_class,
    default_life_type,
    ma_rate_exposure,
    aca_aptc_exposure,
    cmmi_dependence,
    policy_exposure_total,
    denominator_volatility,
    -- Normalize to 0-1. Max possible = 15 (policy) + 5 (denom) = 20.
    CAST((policy_exposure_total + denominator_volatility) / 20.0 AS DECIMAL(9, 6)) AS risk_score,
    CASE
        WHEN (policy_exposure_total + denominator_volatility) >= 12 THEN 'wide'
        WHEN (policy_exposure_total + denominator_volatility) >=  6 THEN 'normal'
        ELSE 'tight'
    END AS demanded_margin_of_safety
FROM denom
