# CLAUDE.md — VANTAGE Conventions

**Always read `SPEC.md` first.** That file is the source of truth. This file enforces how to work in the repo.

## Working rules

- **One phase at a time.** The build is acceptance-gated (see SPEC §8). Do not start phase N+1 until phase N's acceptance criteria pass.
- **Stop at phase boundaries** and surface what changed + what's next. The operator gates the next phase.

## Hard invariants (these block merges)

1. **Provenance or it didn't happen.** No row in any `fact_*` table without a corresponding `dim_source` row. Estimates must be tagged `reliability='estimate'` and never silently promoted to `'primary'`.
2. **Denominator discipline.** Any cross-company metric must assert matching `denominator_class` (see `dim_segment`). Comparing revenue/eligible-life to revenue/at-risk-member is a bug. Engines must raise, not silently fudge.
3. **Idempotent ingestion.** Every writer upserts on a natural key. Re-running the same ingest is a no-op. Tests should re-run the same fixture twice and assert row counts are stable.
4. **Money = `DECIMAL`, USD millions.** Never `FLOAT` for currency. Unit is documented in column comments and dbt `meta`.
5. **Guidance ≠ actuals.** `fact_financials.is_guidance` is always set. Metric models that mix actuals and guidance must say so explicitly in their name (e.g., `metric_growth_yoy_guidance_aware`).
6. **LLM for judgment, SQL for truth.** Claude extracts, classifies, and drafts prose. It does not invent a number that isn't in a source. Every numeric claim in a prospectus renders an inline source ref tied to a `dim_source.source_id`.

## Code conventions

- Python 3.11+. Pydantic v2 for any ingestion boundary. `pydantic-settings` for config.
- Use `uv` for env + dependency management. `uv sync` is the canonical install.
- Run dbt with `uv run dbt build --project-dir dbt_vantage --profiles-dir dbt_vantage` (profiles live in the project).
- Typed everywhere. `mypy --strict` is the target on `ingest/`, `engine/`, and `prospectus/`.
- Tests in `tests/`. Use `pytest`. Ingestion writers get an idempotency test as a baseline.
- No file-level docstrings or planning docs unless asked. Comments only when the *why* is non-obvious.

## Schema rules

- The dbt project (`dbt_vantage/`) owns the marts. Raw ingestion lands in DuckDB tables prefixed `raw_*` (declared as dbt `source`s).
- `dim_*` and `fact_*` are materialized as `table` in the `main` schema (mart layer).
- Metrics layer is `metric_*`, materialized as `view` unless performance demands otherwise.
- Every new model gets a `schema.yml` entry with `description`, column docs, and at least one test (`not_null` on the grain, `relationships` to dims, `accepted_values` on enum columns).

## Doing risky things

- Never drop tables or `vantage.duckdb` without confirmation. The file is the system of record between runs.
- Migrations: prefer additive (new columns, new models). For breaking changes, document in `CHANGELOG.md` and bump a schema version.
- Never commit `.env` or `vantage.duckdb`. Both are gitignored — keep them that way.
