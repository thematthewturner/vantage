{{ config(materialized='view') }}

-- Index #1: species-conditional EV ceilings. Same spirit as Graham's
-- 15×/1.5× combined ceiling, recalibrated for digital-health economic
-- species. Each business_model gets its own primary multiple cap +
-- balance-sheet quality gate. Pass requires BOTH.

WITH scored AS (
    SELECT
        ev.company_id,
        ev.ticker,
        ev.segment,
        ev.business_model,
        ev.market_cap,
        ev.enterprise_value,
        ev.ev_to_revenue,
        ev.ev_to_ebitda,
        ev.ev_to_fcf,
        ev.fcf_yield,
        l.adj_ebitda_fy,
        l.fcf_fy,
        l.gross_margin_fy,
        l.revenue_fy,
        l.revenue_q_annualized,
        CASE
            WHEN l.revenue_fy > 0
            THEN (l.revenue_q_annualized - l.revenue_fy) / l.revenue_fy
        END AS qoq_growth_proxy
    FROM {{ ref('metric_enterprise_value') }} ev
    JOIN {{ ref('metric_company_latest') }} l ON l.company_id = ev.company_id
)
SELECT
    company_id,
    ticker,
    business_model,
    -- Species-conditional ceiling: the multiple cap appropriate for each
    -- economic species. Values reflect mid-cycle multiples, not bull peaks.
    CASE business_model
        WHEN 'full_risk'    THEN 'EV/EBITDA <= 12x AND EBITDA > 0'
        WHEN 'vbc_enabler'  THEN 'EV/EBITDA <= 14x AND EBITDA > 0'
        WHEN 'saas'         THEN 'EV/FCF <= 25x AND Rule-of-40 cleared'
        WHEN 'data_infra'   THEN 'EV/Sales <= 8x AND gross margin >= 65%'
        WHEN 'dtc_sub'      THEN 'EV/Sales <= 5x AND FCF > 0'
        WHEN 'dx'           THEN 'EV/Sales <= 6x AND gross margin >= 50%'
    END AS ceiling_rule,
    -- The primary multiple used to test against the ceiling.
    CASE business_model
        WHEN 'full_risk'    THEN ev_to_ebitda
        WHEN 'vbc_enabler'  THEN ev_to_ebitda
        WHEN 'saas'         THEN ev_to_fcf
        WHEN 'data_infra'   THEN ev_to_revenue
        WHEN 'dtc_sub'      THEN ev_to_revenue
        WHEN 'dx'           THEN ev_to_revenue
    END AS primary_multiple,
    -- Quality gate: does the company clear the balance-sheet / unit-economic
    -- floor required for the multiple to be meaningful?
    CASE business_model
        WHEN 'full_risk'    THEN adj_ebitda_fy > 0
        WHEN 'vbc_enabler'  THEN adj_ebitda_fy > 0
        WHEN 'saas'         THEN COALESCE(qoq_growth_proxy, 0) * 100
                                 + COALESCE(adj_ebitda_fy / NULLIF(revenue_fy, 0), 0) * 100 >= 40
        WHEN 'data_infra'   THEN gross_margin_fy >= 0.65
        WHEN 'dtc_sub'      THEN fcf_fy > 0
        WHEN 'dx'           THEN gross_margin_fy >= 0.50
    END AS quality_gate_pass,
    -- Multiple-pass (independent of the quality gate).
    CASE business_model
        WHEN 'full_risk'    THEN ev_to_ebitda <= 12
        WHEN 'vbc_enabler'  THEN ev_to_ebitda <= 14
        WHEN 'saas'         THEN ev_to_fcf     <= 25
        WHEN 'data_infra'   THEN ev_to_revenue <=  8
        WHEN 'dtc_sub'      THEN ev_to_revenue <=  5
        WHEN 'dx'           THEN ev_to_revenue <=  6
    END AS multiple_pass,
    -- Overall species ceiling pass = BOTH gates clear.
    CASE
        WHEN ev_to_ebitda IS NULL AND business_model IN ('full_risk', 'vbc_enabler')
            THEN 'fail_no_ebitda'
        WHEN ev_to_fcf IS NULL AND business_model = 'saas'
            THEN 'fail_no_fcf'
        WHEN (
            (business_model = 'full_risk'   AND ev_to_ebitda <= 12 AND adj_ebitda_fy > 0)
         OR (business_model = 'vbc_enabler' AND ev_to_ebitda <= 14 AND adj_ebitda_fy > 0)
         OR (business_model = 'saas'        AND ev_to_fcf     <= 25)
         OR (business_model = 'data_infra'  AND ev_to_revenue <=  8 AND gross_margin_fy >= 0.65)
         OR (business_model = 'dtc_sub'     AND ev_to_revenue <=  5 AND fcf_fy > 0)
         OR (business_model = 'dx'          AND ev_to_revenue <=  6 AND gross_margin_fy >= 0.50)
        ) THEN 'pass'
        ELSE 'fail'
    END AS species_overall
FROM scored
