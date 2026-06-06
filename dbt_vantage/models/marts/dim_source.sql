{{ config(materialized='table') }}

-- Phase 0: pass-through of the seeded sources. Phase 1+ will UNION ALL with
-- `raw_dim_source` (written by ingest/) once that table exists. Until then
-- this model is the system of record for `dim_source`.

SELECT
    source_id,
    source_type,
    url,
    retrieved_at,
    reliability
FROM {{ ref('dim_source_seed') }}
