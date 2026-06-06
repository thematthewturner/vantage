{{ config(materialized='table') }}

-- People (founders, execs, board) — populated by ingest/sec.py (DEF 14A / S-1
-- officers and directors) and curated additions in Phase 3+. Empty in Phase 0.

SELECT
    CAST(NULL AS VARCHAR) AS person_id,
    CAST(NULL AS VARCHAR) AS full_name,
    CAST(NULL AS VARCHAR) AS role,
    CAST(NULL AS VARCHAR) AS company_id,
    CAST(NULL AS BOOLEAN) AS is_board
WHERE 1 = 0
