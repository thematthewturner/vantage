{{ config(materialized='view') }}

-- Parallel safety index for the private corpus. Different denominators
-- than the public version: no market cap, no quarterly financials, so the
-- ranking pivots on capital efficiency (valuation per dollar raised),
-- valuation freshness (months since last primary round), and the
-- primary-vs-secondary signal (a secondary mark below the primary round
-- is the closest equivalent to "trading below intrinsic" in venture).
--
-- One row per active private. Excludes acquired and public companies.

WITH funding AS (
    SELECT
        company_id,
        SUM(amount_usd)                                         AS cumulative_funding,
        SUM(CASE WHEN round_type != 'debt' THEN amount_usd END) AS cumulative_equity,
        SUM(CASE WHEN round_type  = 'debt' THEN amount_usd END) AS cumulative_debt,
        MAX(announced_date)                                     AS last_round_date,
        COUNT(*)                                                AS n_rounds
    FROM {{ ref('fact_funding_round') }}
    GROUP BY company_id
), latest_primary AS (
    SELECT
        company_id,
        as_of_date     AS primary_mark_date,
        valuation_usd  AS primary_mark,
        ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY as_of_date DESC) AS rn
    FROM {{ ref('fact_valuation') }}
    WHERE method = 'primary_round'
), latest_secondary AS (
    SELECT
        company_id,
        as_of_date     AS secondary_mark_date,
        valuation_usd  AS secondary_mark,
        ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY as_of_date DESC) AS rn
    FROM {{ ref('fact_valuation') }}
    WHERE method IN ('secondary_npm', '409a')
), base AS (
    SELECT
        c.company_id,
        c.legal_name,
        c.segment,
        c.business_model,
        c.status,
        f.cumulative_funding,
        f.cumulative_equity,
        f.cumulative_debt,
        f.last_round_date,
        f.n_rounds,
        lp.primary_mark,
        lp.primary_mark_date,
        ls.secondary_mark,
        ls.secondary_mark_date,
        DATE_DIFF('month', f.last_round_date, DATE '{{ var("scoring_date", "2026-06-06") }}') AS months_since_last_round
    FROM {{ ref('dim_company') }} c
    LEFT JOIN funding         f  ON f.company_id  = c.company_id
    LEFT JOIN latest_primary  lp ON lp.company_id = c.company_id AND lp.rn = 1
    LEFT JOIN latest_secondary ls ON ls.company_id = c.company_id AND ls.rn = 1
    WHERE c.status = 'private'
)
SELECT
    company_id,
    legal_name,
    segment,
    business_model,
    cumulative_funding,
    cumulative_equity,
    cumulative_debt,
    n_rounds,
    last_round_date,
    months_since_last_round,
    primary_mark,
    primary_mark_date,
    secondary_mark,
    secondary_mark_date,
    -- Valuation per dollar of equity raised. >5x = highly capital-efficient
    -- (typical for SaaS scale-ups); <2x = capital-heavy (typical for
    -- risk-bearing operators that have to fund statutory capital).
    CASE
        WHEN cumulative_equity > 0 AND primary_mark IS NOT NULL
        THEN primary_mark / cumulative_equity
    END AS valuation_per_dollar_raised,
    -- Secondary-to-primary discount. Negative = secondary trading below
    -- primary (signal of staleness or stress). Positive = secondary
    -- markup from primary (healthy demand).
    CASE
        WHEN primary_mark > 0 AND secondary_mark IS NOT NULL
        THEN (secondary_mark - primary_mark) / primary_mark
    END AS secondary_to_primary_delta,
    -- Verdict: combination of capital efficiency, freshness, and the
    -- secondary signal. Two-axis scoring keeps it transparent.
    CASE
        WHEN primary_mark IS NULL                                   THEN 'data_unavailable'
        WHEN cumulative_equity > 0
             AND primary_mark / cumulative_equity >= 5
             AND months_since_last_round <= 18
             AND COALESCE(secondary_to_primary_delta, 0) >= -0.10   THEN 'capital_efficient_fresh_mark'
        WHEN cumulative_equity > 0
             AND primary_mark / cumulative_equity >= 5
             AND months_since_last_round >  18                      THEN 'capital_efficient_stale_mark'
        WHEN cumulative_equity > 0
             AND primary_mark / cumulative_equity <  5
             AND COALESCE(secondary_to_primary_delta, 0) < -0.10    THEN 'capital_heavy_secondary_discount'
        WHEN cumulative_equity > 0
             AND primary_mark / cumulative_equity <  5               THEN 'capital_heavy'
        ELSE 'mixed'
    END AS private_verdict,
    RANK() OVER (
        ORDER BY
            CASE
                WHEN cumulative_equity > 0 AND primary_mark IS NOT NULL
                THEN primary_mark / cumulative_equity
            END DESC NULLS LAST,
            months_since_last_round ASC
    ) AS private_rank
FROM base
