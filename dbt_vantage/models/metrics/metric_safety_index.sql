{{ config(materialized='view') }}

-- The final layered output: one row per public, every index's verdict
-- side-by-side, plus a combined directional score and category.
--
-- The combined score is a TRANSPARENT WEIGHTED SUM, not a black box —
-- every component is visible so you can reweight or override per name.
-- It is not a buy/sell signal; it ranks the corpus by a Graham-spirited
-- margin-of-safety framework, then surfaces where each index agrees or
-- disagrees with the others. Disagreement is the interesting signal.

WITH bundle AS (
    SELECT
        ev.company_id,
        ev.ticker,
        c.legal_name,
        c.segment,
        c.business_model,
        ev.market_cap,
        ev.enterprise_value,
        ev.ev_to_revenue,
        ev.ev_to_ebitda,
        ev.ev_to_fcf,
        ev.fcf_yield,
        -- Pure Graham column (honesty)
        g.graham_overall,
        g.c1_size,
        g.c4_dividend_record,
        g.c6_pe,
        g.pe_ratio,
        -- Index #1: species ceiling
        s.ceiling_rule,
        s.primary_multiple,
        s.species_overall,
        -- Index #2: reverse DCF
        rd.terminal_fcf_margin,
        rd.implied_5yr_cagr,
        rd.observed_growth,
        rd.growth_gap,
        rd.dcf_verdict,
        -- Index #3: quality composite
        q.quality_score,
        q.quality_rank,
        -- Index #4: guidance-adjusted MoS
        ga.guidance_reliability,
        ga.guidance_adjusted_margin_of_safety,
        ga.guidance_adjusted_verdict,
        -- Index #5: risk balance
        rb.risk_score,
        rb.demanded_margin_of_safety
    FROM {{ ref('metric_enterprise_value') }} ev
    JOIN {{ ref('dim_company') }}                 c  ON c.company_id  = ev.company_id
    LEFT JOIN {{ ref('metric_graham_pure') }}             g  ON g.company_id  = ev.company_id
    LEFT JOIN {{ ref('metric_species_ceiling') }}         s  ON s.company_id  = ev.company_id
    LEFT JOIN {{ ref('metric_reverse_dcf') }}             rd ON rd.company_id = ev.company_id
    LEFT JOIN {{ ref('metric_quality_composite') }}       q  ON q.company_id  = ev.company_id
    LEFT JOIN {{ ref('metric_guidance_adjusted_value') }} ga ON ga.company_id = ev.company_id
    LEFT JOIN {{ ref('metric_risk_balance') }}            rb ON rb.company_id = ev.company_id
), scored AS (
    SELECT
        *,
        -- Translate each index into a numeric contribution.
        CASE species_overall          WHEN 'pass' THEN 1.0 ELSE 0.0 END AS s_species,
        CASE dcf_verdict
            WHEN 'cushion'               THEN  1.0
            WHEN 'fairly_priced'         THEN  0.0
            WHEN 'priced_for_perfection' THEN -1.0
            ELSE 0.0
        END                                                              AS s_dcf,
        CASE guidance_adjusted_verdict
            WHEN 'wide_cushion'    THEN  1.0
            WHEN 'modest_cushion'  THEN  0.5
            WHEN 'fairly_priced'   THEN  0.0
            WHEN 'overvalued'      THEN -1.0
            ELSE 0.0
        END                                                              AS s_guidance,
        -- Cap quality_score contribution; otherwise outliers dominate.
        GREATEST(LEAST(quality_score / 5.0, 1.5), -1.5)                  AS s_quality,
        -- Risk penalty: max possible risk is 1.0 → up to -2.0 penalty.
        - COALESCE(risk_score, 0) * 2.0                                  AS s_risk
    FROM bundle
)
SELECT
    company_id,
    ticker,
    legal_name,
    segment,
    business_model,
    market_cap,
    enterprise_value,
    ev_to_revenue,
    ev_to_ebitda,
    ev_to_fcf,
    fcf_yield,
    -- Index columns
    graham_overall,
    species_overall,
    primary_multiple,
    dcf_verdict,
    implied_5yr_cagr,
    growth_gap,
    quality_rank,
    quality_score,
    guidance_reliability,
    guidance_adjusted_verdict,
    guidance_adjusted_margin_of_safety,
    risk_score,
    demanded_margin_of_safety,
    -- Combined directional score and category
    CAST(s_species + s_dcf + s_guidance + s_quality + s_risk AS DECIMAL(9, 4)) AS combined_safety_score,
    CASE
        WHEN s_species + s_dcf + s_guidance + s_quality + s_risk >=  1.5 THEN 'quality_and_cushion'
        WHEN s_species + s_dcf + s_guidance + s_quality + s_risk >=  0.5 THEN 'watch_list'
        WHEN s_species + s_dcf + s_guidance + s_quality + s_risk >= -0.5 THEN 'neutral'
        ELSE 'avoid_or_special_view_required'
    END AS recommendation_bucket,
    RANK() OVER (ORDER BY s_species + s_dcf + s_guidance + s_quality + s_risk DESC) AS safety_rank
FROM scored
