{{ config(materialized='table') }}

-- Phase 0: pass-through of the seeded directory. Phase 1+ overlays SEC-derived
-- fields (CIK, exact legal name) via a UNION/COALESCE against `raw_dim_company`.

SELECT
    company_id,
    legal_name,
    status,
    ticker,
    exchange,
    cik,
    segment,
    sub_segment,
    business_model,
    is_public_benefit,
    founded_year,
    hq_state,
    website,
    description
FROM {{ ref('dim_company_seed') }}
