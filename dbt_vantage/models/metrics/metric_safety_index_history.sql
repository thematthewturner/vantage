{{ config(materialized='view') }}

-- History-aware safety index. Re-runs the species-ceiling + reverse-DCF +
-- guidance-adjusted checks at every snapshot in fact_market_data.
-- Quality composite and risk balance are snapshot-invariant in v1 (their
-- inputs are constant across snapshots) so they're surfaced once but the
-- bucket can flip when the EV-dependent indexes flip.

WITH ev_hist AS (
    SELECT * FROM {{ ref('metric_enterprise_value_history') }}
), bundle AS (
    SELECT
        ev.company_id,
        ev.as_of_date,
        ev.ticker,
        ev.business_model,
        ev.market_cap,
        ev.enterprise_value,
        ev.ev_to_revenue,
        ev.ev_to_ebitda,
        ev.ev_to_fcf,
        ev.fcf_yield,
        l.revenue_fy,
        l.adj_ebitda_fy,
        l.fcf_fy,
        l.gross_margin_fy,
        l.revenue_q_annualized,
        CASE
            WHEN l.revenue_fy > 0
            THEN (l.revenue_q_annualized - l.revenue_fy) / l.revenue_fy
        END AS observed_growth,
        q.quality_score,
        rb.risk_score,
        g.guidance_reliability,
        0.10 + (0.50 - COALESCE(g.guidance_reliability, 0.50)) * 0.04 AS adjusted_discount_rate
    FROM ev_hist ev
    LEFT JOIN {{ ref('metric_company_latest') }}      l  ON l.company_id  = ev.company_id
    LEFT JOIN {{ ref('metric_quality_composite') }}   q  ON q.company_id  = ev.company_id
    LEFT JOIN {{ ref('metric_risk_balance') }}        rb ON rb.company_id = ev.company_id
    LEFT JOIN {{ ref('fact_guidance_accuracy') }}     g  ON g.company_id  = ev.company_id
), scored AS (
    SELECT
        *,
        -- Species ceiling at this snapshot
        CASE
            WHEN ev_to_ebitda IS NULL AND business_model IN ('full_risk', 'vbc_enabler') THEN 'fail_no_ebitda'
            WHEN ev_to_fcf IS NULL AND business_model = 'saas' THEN 'fail_no_fcf'
            WHEN (business_model = 'full_risk'   AND ev_to_ebitda <= 12 AND adj_ebitda_fy > 0)
              OR (business_model = 'vbc_enabler' AND ev_to_ebitda <= 14 AND adj_ebitda_fy > 0)
              OR (business_model = 'saas'        AND ev_to_fcf     <= 25)
              OR (business_model = 'data_infra'  AND ev_to_revenue <=  8 AND gross_margin_fy >= 0.65)
              OR (business_model = 'dtc_sub'     AND ev_to_revenue <=  5 AND fcf_fy > 0)
              OR (business_model = 'dx'          AND ev_to_revenue <=  6 AND gross_margin_fy >= 0.50)
                THEN 'pass'
            ELSE 'fail'
        END AS species_overall,
        -- Reverse DCF at this snapshot
        CASE business_model
            WHEN 'full_risk'    THEN 0.04
            WHEN 'vbc_enabler'  THEN 0.08
            WHEN 'saas'         THEN 0.22
            WHEN 'data_infra'   THEN 0.30
            WHEN 'dtc_sub'      THEN 0.12
            WHEN 'dx'           THEN 0.15
        END AS terminal_fcf_margin
    FROM bundle
), dcf AS (
    SELECT
        *,
        enterprise_value * (0.10 - 0.03) AS required_terminal_fcf,
        (enterprise_value * (0.10 - 0.03)) / NULLIF(terminal_fcf_margin, 0) AS required_revenue_t5
    FROM scored
), finished AS (
    SELECT
        *,
        CASE
            WHEN revenue_fy > 0 AND required_revenue_t5 > 0
            THEN POWER(required_revenue_t5 / revenue_fy, 1.0 / 5.0) - 1
        END AS implied_5yr_cagr,
        CASE
            WHEN revenue_fy > 0 AND required_revenue_t5 > 0
            THEN observed_growth - (POWER(required_revenue_t5 / revenue_fy, 1.0 / 5.0) - 1)
        END AS growth_gap
    FROM dcf
), verdicted AS (
    SELECT
        *,
        CASE
            WHEN revenue_fy IS NULL OR required_revenue_t5 IS NULL THEN 'data_unavailable'
            WHEN growth_gap >  0.05 THEN 'cushion'
            WHEN growth_gap > -0.05 THEN 'fairly_priced'
            ELSE 'priced_for_perfection'
        END AS dcf_verdict,
        CASE WHEN adjusted_discount_rate > 0.03 AND fcf_fy > 0
             THEN fcf_fy / (adjusted_discount_rate - 0.03)
        END AS guidance_adjusted_ev
    FROM finished
), final AS (
    SELECT
        *,
        CASE
            WHEN guidance_adjusted_ev IS NOT NULL AND enterprise_value > 0
            THEN (guidance_adjusted_ev - enterprise_value) / enterprise_value
        END AS guidance_adjusted_mos,
        CASE species_overall WHEN 'pass' THEN 1.0 ELSE 0.0 END AS s_species,
        CASE
            WHEN revenue_fy IS NULL OR required_revenue_t5 IS NULL THEN 0.0
            WHEN growth_gap >  0.05 THEN  1.0
            WHEN growth_gap > -0.05 THEN  0.0
            ELSE -1.0
        END                                                     AS s_dcf,
        GREATEST(LEAST(quality_score / 5.0, 1.5), -1.5)         AS s_quality,
        - COALESCE(risk_score, 0) * 2.0                         AS s_risk
    FROM verdicted
)
SELECT
    company_id,
    as_of_date,
    ticker,
    business_model,
    market_cap,
    enterprise_value,
    ev_to_revenue,
    ev_to_ebitda,
    ev_to_fcf,
    fcf_yield,
    species_overall,
    dcf_verdict,
    implied_5yr_cagr,
    observed_growth,
    growth_gap,
    quality_score,
    guidance_adjusted_mos,
    risk_score,
    CAST(s_species + s_dcf + s_quality + s_risk
         + CASE
             WHEN guidance_adjusted_mos IS NULL                       THEN 0.0
             WHEN guidance_adjusted_mos >  0.33                        THEN  1.0
             WHEN guidance_adjusted_mos >  0.0                         THEN  0.5
             WHEN guidance_adjusted_mos > -0.20                        THEN  0.0
             ELSE -1.0
           END
         AS DECIMAL(9, 4))                                         AS combined_safety_score,
    CASE
        WHEN s_species + s_dcf + s_quality + s_risk
             + CASE WHEN guidance_adjusted_mos > 0.33 THEN 1.0
                    WHEN guidance_adjusted_mos > 0.0  THEN 0.5
                    WHEN guidance_adjusted_mos > -0.20 THEN 0.0
                    WHEN guidance_adjusted_mos IS NULL THEN 0.0
                    ELSE -1.0 END
             >=  1.5 THEN 'quality_and_cushion'
        WHEN s_species + s_dcf + s_quality + s_risk
             + CASE WHEN guidance_adjusted_mos > 0.33 THEN 1.0
                    WHEN guidance_adjusted_mos > 0.0  THEN 0.5
                    WHEN guidance_adjusted_mos > -0.20 THEN 0.0
                    WHEN guidance_adjusted_mos IS NULL THEN 0.0
                    ELSE -1.0 END
             >=  0.5 THEN 'watch_list'
        WHEN s_species + s_dcf + s_quality + s_risk
             + CASE WHEN guidance_adjusted_mos > 0.33 THEN 1.0
                    WHEN guidance_adjusted_mos > 0.0  THEN 0.5
                    WHEN guidance_adjusted_mos > -0.20 THEN 0.0
                    WHEN guidance_adjusted_mos IS NULL THEN 0.0
                    ELSE -1.0 END
             >= -0.5 THEN 'neutral'
        ELSE 'avoid_or_special_view_required'
    END AS recommendation_bucket
FROM final
