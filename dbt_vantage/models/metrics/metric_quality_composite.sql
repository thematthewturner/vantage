{{ config(materialized='view') }}

-- Index #3: cross-section z-scored quality composite. Same role Graham
-- gave book value (a quality floor), but using digital-health-native
-- denominators that actually carry signal on this universe.
--
-- Components (each z-scored across the 22 publics):
--   * fcf_yield          - free cash flow / market cap
--   * gross_margin_fy    - latest annual gross margin
--   * capital_efficiency - lifetime revenue per dollar of cumulative funding
--   * cash_runway_years  - cash / annual burn (winsorized at 10)
--   * revenue_growth     - latest Q annualized vs prior FY
--
-- Equal-weighted sum of available z-scores; rank within the universe.

WITH base AS (
    SELECT
        ev.company_id,
        ev.ticker,
        ev.business_model,
        ev.fcf_yield,
        l.gross_margin_fy,
        l.capital_efficiency,
        LEAST(COALESCE(l.cash_runway_years, 10), 10) AS cash_runway_capped,
        CASE
            WHEN l.revenue_fy > 0
            THEN (l.revenue_q_annualized - l.revenue_fy) / l.revenue_fy
        END AS revenue_growth
    FROM {{ ref('metric_enterprise_value') }} ev
    JOIN {{ ref('metric_company_latest') }} l ON l.company_id = ev.company_id
), z AS (
    SELECT
        company_id,
        ticker,
        business_model,
        fcf_yield,
        gross_margin_fy,
        capital_efficiency,
        cash_runway_capped,
        revenue_growth,
        (fcf_yield        - AVG(fcf_yield)        OVER ()) / NULLIF(STDDEV(fcf_yield)        OVER (), 0) AS z_fcf_yield,
        (gross_margin_fy  - AVG(gross_margin_fy)  OVER ()) / NULLIF(STDDEV(gross_margin_fy)  OVER (), 0) AS z_gross_margin,
        (capital_efficiency - AVG(capital_efficiency) OVER ()) / NULLIF(STDDEV(capital_efficiency) OVER (), 0) AS z_capital_eff,
        (cash_runway_capped - AVG(cash_runway_capped) OVER ()) / NULLIF(STDDEV(cash_runway_capped) OVER (), 0) AS z_runway,
        (revenue_growth   - AVG(revenue_growth)   OVER ()) / NULLIF(STDDEV(revenue_growth)   OVER (), 0) AS z_growth
    FROM base
)
SELECT
    company_id,
    ticker,
    business_model,
    fcf_yield,
    gross_margin_fy,
    capital_efficiency,
    cash_runway_capped,
    revenue_growth,
    z_fcf_yield,
    z_gross_margin,
    z_capital_eff,
    z_runway,
    z_growth,
    -- Sum available z-scores. NULL components silently drop; small-N
    -- companies (no Q data yet) lose a component but stay ranked.
    COALESCE(z_fcf_yield, 0)
      + COALESCE(z_gross_margin, 0)
      + COALESCE(z_capital_eff, 0)
      + COALESCE(z_runway, 0)
      + COALESCE(z_growth, 0)                                         AS quality_score,
    RANK() OVER (
        ORDER BY (
              COALESCE(z_fcf_yield, 0)
            + COALESCE(z_gross_margin, 0)
            + COALESCE(z_capital_eff, 0)
            + COALESCE(z_runway, 0)
            + COALESCE(z_growth, 0)
        ) DESC
    ) AS quality_rank
FROM z
