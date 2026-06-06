{{ config(materialized='table') }}

-- Timeline events: IPO, M&A, partnership, layoff, regulatory action.
-- Natural key: event_id (hash of company_id + event_date + event_type + headline).

SELECT
    CAST(NULL AS VARCHAR) AS event_id,
    CAST(NULL AS VARCHAR) AS company_id,
    CAST(NULL AS DATE)    AS event_date,
    CAST(NULL AS VARCHAR) AS event_type,
    CAST(NULL AS VARCHAR) AS headline,
    CAST(NULL AS VARCHAR) AS source_id
WHERE 1 = 0
