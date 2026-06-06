# VANTAGE

Digital Health Intelligence Engine. System of record for digital health company economics — public and private. See **[SPEC.md](SPEC.md)** for the build prompt and **[CLAUDE.md](CLAUDE.md)** for conventions.

## Quickstart

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e .

# Phase 0: scaffold the warehouse
./.venv/bin/python cli.py init
./.venv/bin/python cli.py build
```

Or directly:

```bash
./.venv/bin/dbt build --project-dir dbt_vantage --profiles-dir dbt_vantage
```

The DuckDB warehouse lands at `./vantage.duckdb` (gitignored). Always run dbt from the repo root.

## Phase status

- [x] **Phase 0** — Scaffold + schema + seeds. `dbt build` green (7 seeds, 12 models, 48 tests).
- [x] **Phase 0.5** — Curated public financials (22 cos × FY2025 + Q1 2026), 14 private funding rounds, 12 valuation marks, all cited. `scripts/load_curated_*.py` are the loaders.
- [ ] Phase 1 — SEC ingestion (`edgartools` + XBRL → `fact_financials`).
- [ ] Phase 2 — Metric layer (denominator-aware comparisons).
- [ ] Phase 3 — Funding/news + Claude enrichment.
- [ ] Phase 4 — Scenario, valuation, policy engines.
- [ ] Phase 5 — Prospectus generator.
- [ ] Phase 6 — Evidence.dev dashboard.
- [ ] Phase 7 — Orchestrated refresh + alerts.

## Drop your data here

- `dbt_vantage/seeds/dim_company_seed.csv` — extend the 35-company cold-start directory.
- `dbt_vantage/seeds/fact_covered_lives_seed.csv` — drop your curated rev/covered-life dataset (header-only by default).
- `dbt_vantage/seeds/dim_source_seed.csv` — add any new sources referenced by the rows you add above.

See `dbt_vantage/seeds/README.md` for the rules.
