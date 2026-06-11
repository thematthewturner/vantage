{{ config(materialized='view') }}

-- Multi-snapshot enterprise value. One row per (company_id, as_of_date)
-- in fact_market_data. Backs the safety-index backtest.
--
-- Caveat: fundamentals (revenue, EBITDA, FCF) come from metric_company_latest,
-- which is single-snapshot. So historical EV moves with price, but the
-- underlying ratios use the same denominator across snapshots. This is
-- acceptable for "did the market reprice X enough to flip the verdict?"
-- It is NOT a true point-in-time backtest until prior-quarter financials
-- get loaded — wired up the moment Phase 1 ingest lands historical 10-Qs.

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
