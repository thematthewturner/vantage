"""Ingestion writers. Each writer is idempotent (upsert on natural key),
validates through Pydantic before insert, and writes a `dim_source` row
before any `fact_*` row. Phase 1+ populates this module."""
