{{ config(materialized='view') }}

-- Index #2: reverse-DCF implied-growth gap.
--
-- For each public, solve a Gordon-style perpetuity for the implied
-- steady-state cash flow that today's EV requires. Then back out the
-- implicit 5-year revenue CAGR needed to reach that cash flow given a
-- species-appropriate terminal FCF margin. Compare to the observed
-- run-rate growth.
--
--   EV = FCF_terminal / (r - g)
--   FCF_terminal = revenue_t5 * terminal_margin
--   revenue_t5 = revenue_fy * (1 + implied_cagr) ** 5
--
-- Hold r = 0.10 and a long-run nominal g = 0.03; solve for implied_cagr.
-- The output is opinionated — it depends on terminal_margin choice —
-- so it's surfaced alongside, never as the sole gate.

WITH params AS (
    SELECT
        ev.company_id,
        ev.ticker,
        ev.business_model,
        ev.enterprise_value,
        l.revenue_fy,
        l.revenue_q_annualized,
        CASE ev.business_model
            WHEN 'full_risk'    THEN 0.04
            WHEN 'vbc_enabler'  THEN 0.08
            WHEN 'saas'         THEN 0.22
            WHEN 'data_infra'   THEN 0.30
            WHEN 'dtc_sub'      THEN 0.12
            WHEN 'dx'           THEN 0.15
        END AS terminal_fcf_margin,
        0.10 AS discount_rate,
        0.03 AS long_run_g
    FROM {{ ref('metric_enterprise_value') }} ev
    JOIN {{ ref('metric_company_latest') }} l ON l.company_id = ev.company_id
), solved AS (
    SELECT
        company_id,
        ticker,
        business_model,
        enterprise_value,
        revenue_fy,
        terminal_fcf_margin,
        -- Required terminal FCF from EV = FCF / (r - g_long).
        enterprise_value * (discount_rate - long_run_g) AS required_terminal_fcf,
        -- Required revenue at t=5 to deliver that FCF at the species margin.
        (enterprise_value * (discount_rate - long_run_g)) / NULLIF(terminal_fcf_margin, 0) AS required_revenue_t5,
        -- Observed run-rate (latest Q × 4) vs latest annual.
        CASE
            WHEN revenue_fy > 0
            THEN (revenue_q_annualized - revenue_fy) / revenue_fy
        END AS observed_growth,
        revenue_q_annualized
    FROM params
)
SELECT
    company_id,
    ticker,
    business_model,
    enterprise_value,
    revenue_fy,
    terminal_fcf_margin,
    required_terminal_fcf,
    required_revenue_t5,
    -- Implied 5-year CAGR: required_t5 = revenue_fy * (1 + g) ** 5.
    CASE
        WHEN revenue_fy > 0 AND required_revenue_t5 > 0
        THEN POWER(required_revenue_t5 / revenue_fy, 1.0 / 5.0) - 1
    END AS implied_5yr_cagr,
    observed_growth,
    CASE
        WHEN revenue_fy > 0 AND required_revenue_t5 > 0
        THEN observed_growth - (POWER(required_revenue_t5 / revenue_fy, 1.0 / 5.0) - 1)
    END AS growth_gap,
    -- Verdict: gap > 0  = market hasn't priced observed growth (cushion).
    --         gap < 0  = market is ahead of fundamentals (no cushion).
    CASE
        WHEN revenue_fy IS NULL OR required_revenue_t5 IS NULL THEN 'data_unavailable'
        WHEN observed_growth - (POWER(required_revenue_t5 / revenue_fy, 1.0 / 5.0) - 1) >  0.05 THEN 'cushion'
        WHEN observed_growth - (POWER(required_revenue_t5 / revenue_fy, 1.0 / 5.0) - 1) > -0.05 THEN 'fairly_priced'
        ELSE 'priced_for_perfection'
    END AS dcf_verdict
FROM solved
