# vantage

Healthcare-industry **trackers** (think CPI, but tailored to healthcare) and a
custom **index of healthcare stocks** you can watch over time — built to explore,
honestly, whether industry signals lead or lag how health stocks perform.

This is the Phase 1 MVP: a clean, importable Python package driven from
notebooks. The package is the product; notebooks are thin drivers.

## What it does

- **Ingests** tailored healthcare indicators from public APIs into a time-series
  store. Phase 1 ships a **FRED** connector (medical-care CPI, healthcare
  employment, JOLTS health openings, PCE health services, hospital/pharma PPI,
  10Y Treasury) and an **equity-price** connector (yfinance).
- **Builds a custom index** (`VHC`) of ~28 healthcare names — market-cap
  weighted, quarterly rebalanced, base = 100, with both price-return and
  total-return tracks — plus per-sub-sector sub-indices (pharma, payers,
  providers, devices, biotech, tools, distributors).
- **Compares** indicators against the index with mixed-frequency as-of
  alignment and an honest lead-lag correlation tool.

## Quick start

```bash
make setup                      # uv venv + all dependencies
export FRED_API_KEY=...         # free key: https://fredaccount.stlouisfed.org/apikey
make refresh                    # ingest sources, build all indices
make lab                        # open the notebooks
```

Then run `notebooks/01_explore_indicators.py` → `02_build_index.py` →
`03_index_vs_indicators.py` (percent-format; open as notebooks in JupyterLab or
VS Code, or run as scripts).

```bash
make test    # offline test suite (live API tests skipped by default)
make lint    # ruff
```

## How it's built

```
config/        settings, the list of series to pull, the index universe
migrations/    DuckDB schema (idempotent .sql)
src/vantage/
  connectors/  one file per source; subclass Connector, emit canonical Observations
  storage/     DuckDB + immutable Parquet raw landing; point-in-time readers
  index/       cap-weighted construction, sub-sector sub-indices
  transforms/  YoY/z-score signals, as-of alignment, lead-lag correlation
  pipeline/    ingest + refresh orchestration
notebooks/     thin drivers (percent format)
tests/         offline unit + golden-value + end-to-end tests
```

Data is stored long-format and **bitemporal**: each observation carries an
`as_of` vintage, so a point-in-time query never sees a revision published after
a decision date. Raw pulls land as immutable Parquet first, so the whole DuckDB
store is always rebuildable from `data/raw/`.

**Adding a data source** is one file: subclass `Connector`, implement
`list_series` / `fetch` / `normalize`, decorate with `@register`, and list its
series in `config/sources.toml`. Retries and raw landing come for free.

## Honest caveats (read these)

- **Not investment advice.** Most healthcare industry indicators are *coincident
  or lagging*, not predictive. Lead-lag findings are hypotheses, not signals —
  the `honesty_report` exists to keep you skeptical (small effective samples and
  many indicator × lag combinations manufacture spurious correlations).
- **Survivorship bias.** The MVP universe uses *current* tickers, which overstates
  historical returns. The schema supports delisted/acquired names
  (`from_date`/`to_date`); correcting the history is a later phase.
- **yfinance** has no SLA and a murky ToS, and its share-count/adjustment data can
  be wrong (it feeds cap weights). It's isolated behind one file so it can be
  swapped for a licensed feed.

## Roadmap

- **Phase 2:** sub-sector depth; CMS Medicare/MA enrollment, BLS, openFDA,
  ClinicalTrials.gov, drug-shortage connectors; FRED/ALFRED true vintages.
- **Phase 3:** survivorship-bias correction, corporate-action handling, insurer
  medical-loss-ratio guidance from SEC EDGAR.
- **Phase 4:** a Streamlit dashboard over the package; cloud scheduling; alerts.
