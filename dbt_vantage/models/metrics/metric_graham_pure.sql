{{ config(materialized='view') }}

-- Honest application of Graham's 1973 defensive-investor screen.
-- Most criteria are uncomputable for our universe (no book value, no
-- 10-year earnings history, no dividend record). Surface what we CAN
-- compute and mark the rest data_unavailable. That null pattern IS the
-- diagnostic: classical Graham does not price asset-light, growth-stage
-- digital health.

WITH base AS (
    SELECT
        ev.company_id,
        ev.ticker,
        ev.market_cap,
        ev.close_price,
        l.net_income_fy,
        l.revenue_fy,
        CASE WHEN ev.shares_diluted > 0 AND l.net_income_fy IS NOT NULL
             THEN l.net_income_fy / ev.shares_diluted
        END AS eps_fy,
        ev.shares_diluted
    FROM {{ ref('metric_enterprise_value') }} ev
    JOIN {{ ref('metric_company_latest') }} l ON l.company_id = ev.company_id
)
SELECT
    company_id,
    ticker,
    -- Criterion 1: adequate size. Graham's $100M sales in 1973 ≈ $2B today.
    CASE WHEN revenue_fy >= 2000 THEN 'pass'
         WHEN revenue_fy IS NULL  THEN 'data_unavailable'
         ELSE 'fail'
    END AS c1_size,
    -- Criterion 2: strong balance sheet. We have cash + debt only; not a
    -- current-ratio replacement. Marked structurally unavailable.
    'data_unavailable' AS c2_balance_sheet,
    -- Criterion 3: 10-year positive earnings. No multi-year history yet.
    'data_unavailable' AS c3_earnings_stability,
    -- Criterion 4: uninterrupted dividends for 20yrs. Zero companies in
    -- the corpus pay one — Graham would fail every name on this alone.
    'fail' AS c4_dividend_record,
    -- Criterion 5: 33% growth in 3-yr-avg EPS over the decade. No history.
    'data_unavailable' AS c5_earnings_growth,
    -- Criterion 6: P/E ≤ 15 on 3-yr avg earnings. We compute on TTM EPS as
    -- a single-period proxy; loose, but the directional answer holds.
    CASE WHEN eps_fy IS NULL OR eps_fy <= 0 THEN 'fail_no_earnings'
         WHEN close_price / eps_fy <= 15     THEN 'pass'
         ELSE 'fail'
    END AS c6_pe,
    -- Criterion 7: P/B ≤ 1.5. No book value yet.
    'data_unavailable' AS c7_pb,
    -- Graham Number = sqrt(22.5 × EPS × BVPS). Without BVPS, uncomputable.
    CAST(NULL AS DECIMAL(20, 4)) AS graham_number,
    -- A blunt "pure Graham survives?" flag. With our null pattern it lands
    -- on 'fail' for every name.
    CASE WHEN eps_fy IS NULL OR eps_fy <= 0 OR revenue_fy IS NULL OR revenue_fy < 2000
         THEN 'fail'
         WHEN close_price / eps_fy <= 15 AND revenue_fy >= 2000 THEN 'incomplete_data'
         ELSE 'fail'
    END AS graham_overall,
    eps_fy,
    CASE WHEN eps_fy > 0 THEN close_price / eps_fy END AS pe_ratio
FROM base
