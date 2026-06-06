# Seeds

Cold-start CSVs loaded by `dbt seed`. The column shapes in each file are enforced by `dbt_project.yml > seeds > +column_types`.

## Files

- `dim_segment.csv` — segment taxonomy. Fully populated, owns the `denominator_class` and `default_life_type` per segment. Edit here when a new segment is added; never compute it downstream.
- `dim_source_seed.csv` — bootstrap `dim_source` rows. The `src_directory_curated_v1` row is the source that the cold-start company directory is attributed to. New sources (SEC filings, news posts, CMS PUFs) get written by `ingest/*` to `raw_dim_source`, not here.
- `dim_company_seed.csv` — cold-start company directory. Verifiable public-info fields only (legal name, ticker, exchange, segment, founded year, HQ state, website). `cik` is intentionally blank for now — Phase 1 SEC ingestion populates it via name lookup.
- `fact_covered_lives_seed.csv` — header-only. **Drop the curated revenue-per-covered-life dataset here**, matching the column shape. Every row needs a `source_id` that exists in `dim_source_seed.csv` (or a fresh row added there).

## Extending the directory

Add rows to `dim_company_seed.csv`. The seed source `src_directory_curated_v1` covers manual curated entries; if a directory entry comes from a specific URL (a press release, a state filing, a Crunchbase page), add a new `dim_source_seed.csv` row and reference it.

## Rule

No `fact_*` row without a `source_id` that resolves to a `dim_source` row. dbt tests in `models/marts/schema.yml` enforce this.
