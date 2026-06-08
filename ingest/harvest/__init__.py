"""Content harvest pipeline.

Phase A: deterministic URL discovery (Haiku agents → TSV per company).
Phase B: fetch (this module, httpx) → raw_content/<company>/<type>/<sha>.{html,txt} + manifest.
Phase C: classification (Haiku agents → JSONL).
Phase D: dbt source + stg_documents + dim_document.
"""
