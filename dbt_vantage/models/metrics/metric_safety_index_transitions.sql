{{ config(materialized='view') }}

-- Bucket transitions across snapshots. For each company, every consecutive
-- pair of snapshots emits a row showing what changed. Use this to:
--   * spot names that crossed the buy threshold during the window
--   * audit whether the framework would have moved early on names that
--     subsequently moved (the backtest signal)
--   * see how many of the corpus's verdicts are stable vs noisy

WITH ordered AS (
    SELECT
        company_id,
        ticker,
        as_of_date,
        recommendation_bucket,
        combined_safety_score,
        ev_to_revenue,
        market_cap,
        ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY as_of_date) AS rn
    FROM {{ ref('metric_safety_index_history') }}
), paired AS (
    SELECT
        a.company_id,
        a.ticker,
        a.as_of_date                   AS from_date,
        b.as_of_date                   AS to_date,
        a.recommendation_bucket        AS from_bucket,
        b.recommendation_bucket        AS to_bucket,
        a.combined_safety_score        AS from_score,
        b.combined_safety_score        AS to_score,
        a.market_cap                   AS from_market_cap,
        b.market_cap                   AS to_market_cap,
        CASE WHEN a.market_cap > 0
             THEN (b.market_cap - a.market_cap) / a.market_cap
        END                            AS price_change_pct,
        b.combined_safety_score - a.combined_safety_score AS score_delta
    FROM ordered a
    JOIN ordered b
      ON a.company_id = b.company_id
     AND b.rn = a.rn + 1
)
SELECT
    *,
    CASE
        WHEN from_bucket = to_bucket                                  THEN 'unchanged'
        WHEN from_bucket = 'avoid_or_special_view_required'
         AND to_bucket   IN ('neutral', 'watch_list', 'quality_and_cushion') THEN 'rerated_up'
        WHEN from_bucket = 'neutral'
         AND to_bucket   IN ('watch_list', 'quality_and_cushion')           THEN 'rerated_up'
        WHEN from_bucket = 'watch_list'
         AND to_bucket   = 'quality_and_cushion'                              THEN 'rerated_up'
        WHEN from_bucket = 'quality_and_cushion'
         AND to_bucket   IN ('watch_list', 'neutral', 'avoid_or_special_view_required') THEN 'rerated_down'
        WHEN from_bucket = 'watch_list'
         AND to_bucket   IN ('neutral', 'avoid_or_special_view_required')   THEN 'rerated_down'
        WHEN from_bucket = 'neutral'
         AND to_bucket   = 'avoid_or_special_view_required'                  THEN 'rerated_down'
        ELSE 'mixed'
    END AS transition
FROM paired
