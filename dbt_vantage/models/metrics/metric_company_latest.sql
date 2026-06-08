{{ config(materialized='view') }}

-- Latest available financials per company, narrowed to the figures the
-- safety-index family needs. One row per company. Joins dim_company so
-- non-public names are filtered downstream by ticker IS NOT NULL.

WITH latest_fy AS (
    SELECT
        company_id,
        period_end                AS fy_period_end,
        revenue                   AS revenue_fy,
        gross_margin              AS gross_margin_fy,
        adj_ebitda                AS adj_ebitda_fy,
        net_income                AS net_income_fy,
        free_cash_flow            AS fcf_fy,
        cash_and_sti              AS cash_fy,
        ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY period_end DESC) AS rn
    FROM {{ ref('fact_financials') }}
    WHERE fiscal_period LIKE '%FY' AND NOT is_guidance
), latest_q AS (
    SELECT
        company_id,
        period_end                AS q_period_end,
        revenue                   AS revenue_q,
        adj_ebitda                AS adj_ebitda_q,
        net_income                AS net_income_q,
        cash_and_sti              AS cash_q,
        ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY period_end DESC) AS rn
    FROM {{ ref('fact_financials') }}
    WHERE fiscal_period LIKE '%Q%' AND NOT is_guidance
), funding_total AS (
    SELECT company_id, SUM(amount_usd) AS lifetime_funding
    FROM {{ ref('fact_funding_round') }}
    GROUP BY company_id
)

SELECT
    c.company_id,
    c.legal_name,
    c.status,
    c.ticker,
    c.segment,
    c.business_model,
    s.denominator_class,
    s.default_life_type,
    -- Annual base
    fy.fy_period_end,
    fy.revenue_fy,
    fy.gross_margin_fy,
    fy.adj_ebitda_fy,
    fy.net_income_fy,
    fy.fcf_fy,
    -- Latest quarter
    q.q_period_end,
    q.revenue_q,
    q.adj_ebitda_q,
    q.net_income_q,
    -- Cash: prefer most recent disclosure
    COALESCE(q.cash_q, fy.cash_fy) AS cash_latest,
    -- TTM revenue proxy: latest Q annualized
    CASE WHEN q.revenue_q IS NOT NULL THEN q.revenue_q * 4 END  AS revenue_q_annualized,
    -- Capital efficiency for privates (and a sanity check for publics):
    -- revenue per dollar of cumulative equity raised.
    ft.lifetime_funding,
    CASE
        WHEN ft.lifetime_funding > 0 AND fy.revenue_fy IS NOT NULL
        THEN fy.revenue_fy / ft.lifetime_funding
    END AS capital_efficiency,
    -- Burn proxy: negative TTM FCF, or fall back to negative adj EBITDA.
    CASE
        WHEN COALESCE(fy.fcf_fy, fy.adj_ebitda_fy) < 0
        THEN -COALESCE(fy.fcf_fy, fy.adj_ebitda_fy)
    END AS annual_burn,
    -- Margin of safety primitive: years of cash at current burn.
    CASE
        WHEN COALESCE(fy.fcf_fy, fy.adj_ebitda_fy) < 0
         AND COALESCE(q.cash_q, fy.cash_fy) IS NOT NULL
        THEN COALESCE(q.cash_q, fy.cash_fy) / -COALESCE(fy.fcf_fy, fy.adj_ebitda_fy)
    END AS cash_runway_years
FROM {{ ref('dim_company') }} c
LEFT JOIN {{ ref('dim_segment') }} s ON s.segment = c.segment
LEFT JOIN latest_fy fy ON fy.company_id = c.company_id AND fy.rn = 1
LEFT JOIN latest_q  q  ON q.company_id  = c.company_id AND q.rn  = 1
LEFT JOIN funding_total ft ON ft.company_id = c.company_id
