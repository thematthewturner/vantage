{{ config(materialized='view') }}

-- Index #4: guidance-reliability-adjusted valuation.
--
-- Each company's Bayesian prior on guidance accuracy translates into a
-- discount-rate adjustment. Serial beat-and-raisers earn a lower discount;
-- serial under-deliverers earn a higher one. The adjusted discount feeds
-- a fair-value EV ceiling under the same reverse-DCF skeleton.
--
-- Phase 0 prior = 0.50 uniform across the corpus (placeholder).
-- Phase 1.5 backtest replaces with empirical posteriors from the historical
-- guidance-vs-actuals harvest. Until that lands, this index produces only
-- the SKELETON of the comparison — every name gets the same adjustment.
-- The differential signal appears the moment the prior diverges.

WITH base AS (
    SELECT
        ev.company_id,
        ev.ticker,
        ev.business_model,
        ev.enterprise_value,
        ev.market_cap,
        l.revenue_fy,
        l.fcf_fy,
        l.adj_ebitda_fy,
        g.guidance_reliability,
        g.n_observations,
        g.prior_strength,
        -- ±200bps swing band: reliability=1.0 shaves 200bps off the discount;
        -- reliability=0.0 adds 200bps. Centered at 0.50 = no adjustment.
        0.10 + (0.50 - g.guidance_reliability) * 0.04 AS adjusted_discount_rate
    FROM {{ ref('metric_enterprise_value') }} ev
    JOIN {{ ref('metric_company_latest') }}   l ON l.company_id = ev.company_id
    LEFT JOIN {{ ref('fact_guidance_accuracy') }} g ON g.company_id = ev.company_id
), fair AS (
    SELECT
        company_id,
        ticker,
        business_model,
        enterprise_value,
        market_cap,
        revenue_fy,
        guidance_reliability,
        n_observations,
        prior_strength,
        adjusted_discount_rate,
        -- Hold long-run g = 3%, use latest FCF as cash-flow base.
        CASE
            WHEN adjusted_discount_rate > 0.03 AND fcf_fy > 0
            THEN fcf_fy / (adjusted_discount_rate - 0.03)
        END AS guidance_adjusted_ev,
        fcf_fy
    FROM base
)
SELECT
    company_id,
    ticker,
    business_model,
    enterprise_value,
    market_cap,
    guidance_reliability,
    n_observations,
    prior_strength,
    adjusted_discount_rate,
    fcf_fy,
    guidance_adjusted_ev,
    -- Margin of safety: how much room between the Gordon-style fair-value
    -- EV (at the adjusted discount) and today's EV. Positive = name trades
    -- below its guidance-adjusted intrinsic value.
    CASE
        WHEN guidance_adjusted_ev IS NOT NULL AND enterprise_value > 0
        THEN (guidance_adjusted_ev - enterprise_value) / enterprise_value
    END AS guidance_adjusted_margin_of_safety,
    CASE
        WHEN guidance_adjusted_ev IS NULL                   THEN 'no_positive_fcf'
        WHEN (guidance_adjusted_ev - enterprise_value)
              / enterprise_value > 0.33                     THEN 'wide_cushion'
        WHEN (guidance_adjusted_ev - enterprise_value)
              / enterprise_value > 0                        THEN 'modest_cushion'
        WHEN (guidance_adjusted_ev - enterprise_value)
              / enterprise_value > -0.20                    THEN 'fairly_priced'
        ELSE 'overvalued'
    END AS guidance_adjusted_verdict
FROM fair
