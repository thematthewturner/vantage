{{ config(materialized='table') }}

-- Grain: one row per funding round. Natural key: (company_id, announced_date, round_type, amount_usd).
-- Populated by ingest/news.py (RSS classification) and ingest/sec.py (8-K, S-1).
-- amount_usd / post_money_valuation are USD millions, DECIMAL.

SELECT
    CAST(NULL AS VARCHAR)       AS round_id,
    CAST(NULL AS VARCHAR)       AS company_id,
    CAST(NULL AS DATE)          AS announced_date,
    CAST(NULL AS VARCHAR)       AS round_type,
    CAST(NULL AS DECIMAL(20,4)) AS amount_usd,
    CAST(NULL AS DECIMAL(20,4)) AS post_money_valuation,
    CAST(NULL AS VARCHAR[])     AS lead_investors,
    CAST(NULL AS VARCHAR)       AS source_id
WHERE 1 = 0
