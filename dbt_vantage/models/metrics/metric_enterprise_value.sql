{{ config(materialized='view') }}

-- Enterprise value for the 22 publics. EV = market_cap + debt - cash.
-- Phase 0 uses estimated market data (reliability='estimate'); Phase 1
-- ingest replaces with XBRL primaries.

SELECT
    m.company_id,
    c.ticker,
    c.segment,
    c.business_model,
    m.as_of_date,
    m.shares_diluted,
    m.close_price,
    m.market_cap,
    m.total_debt,
    l.cash_latest,
    CAST(m.market_cap + m.total_debt - COALESCE(l.cash_latest, 0) AS DECIMAL(20, 4)) AS enterprise_value,
    -- Common valuation ratios used throughout the safety-index family.
    CASE WHEN l.revenue_fy > 0
         THEN (m.market_cap + m.total_debt - COALESCE(l.cash_latest, 0)) / l.revenue_fy
    END AS ev_to_revenue,
    CASE WHEN l.adj_ebitda_fy > 0
         THEN (m.market_cap + m.total_debt - COALESCE(l.cash_latest, 0)) / l.adj_ebitda_fy
    END AS ev_to_ebitda,
    CASE WHEN l.fcf_fy > 0
         THEN (m.market_cap + m.total_debt - COALESCE(l.cash_latest, 0)) / l.fcf_fy
    END AS ev_to_fcf,
    CASE WHEN m.market_cap > 0
         THEN l.fcf_fy / m.market_cap
    END AS fcf_yield,
    m.source_id
FROM {{ ref('fact_market_data') }} m
JOIN {{ ref('dim_company') }} c ON c.company_id = m.company_id
LEFT JOIN {{ ref('metric_company_latest') }} l ON l.company_id = m.company_id
