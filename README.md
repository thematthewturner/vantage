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
- **Builds full-history benchmark baselines** — healthcare-sector ETFs
  (`BASE_XLV`, `BASE_IYH`, `BASE_VHT`) and broad-market proxies (`BASE_SPY`,
  `BASE_QQQ`), normalized to 100 from first available ETF history — plus a
  **VHC-vs-benchmark relative-strength** view, so you can tell sector beta from
  market beta (is healthcare beating *the market*, not just other health funds).
- **Builds a custom index** (`VHC`) of ~28 healthcare names — market-cap
  weighted, quarterly rebalanced, base = 100, with both price-return and
  total-return tracks — plus per-sub-sector sub-indices (pharma, payers,
  providers, devices, biotech, tools, distributors).
- **Indexes top healthcare investor firms** in `config/investor_firms.toml`: a
  curated top-25 watchlist with focus areas, stages, geography, source links,
  and tailing signals for tracking where specialist healthcare capital moves next.
- **Compares** indicators against the index with mixed-frequency as-of
  alignment and an honest lead-lag correlation tool.
- **Monitors** all of the above in a dark, multi-chart **web terminal** that
  refreshes daily.

## Quick start

```bash
make setup                      # uv venv + all dependencies
export FRED_API_KEY=...         # free key: https://fredaccount.stlouisfed.org/apikey
make refresh                    # ingest sources, build all indices
make dash                       # open the web terminal at http://localhost:8501
make lab                        # ...or explore in the notebooks
```

Then run `notebooks/01_explore_indicators.py` → `02_build_index.py` →
`03_index_vs_indicators.py` (percent-format; open as notebooks in JupyterLab or
VS Code, or run as scripts).

```bash
make test    # offline test suite (live API tests skipped by default)
make lint    # ruff
```

## Web terminal

`make dash` launches a Streamlit dashboard (a thin driver over the package,
like the notebooks) with a Bloomberg-terminal feel:

- **Index** — the VHC composite (price + total return) with a range selector,
  every sub-sector index rebased and as small multiples, a color-coded
  performance table, and latest constituent weights.
- **Indicators** — a card per healthcare indicator (latest, YoY, trailing
  z-score, sparkline) grouped by sub-sector, plus a detail view.
- **Lead-Lag** — index-vs-indicator overlays, cross-correlation by lag, an
  all-indicator correlation heatmap, and the **honesty report** front and centre.
- **Data health** — series freshness, staleness flags, and price coverage.

Set `VANTAGE_DASHBOARD_PASSWORD` to gate it behind a single password.

## Deploy (daily, on a droplet)

`deploy/` ships a Docker setup that runs the terminal plus a scheduler that
refreshes the data every day, sharing one persistent volume:

```bash
cp deploy/.env.example deploy/.env   # set FRED_API_KEY (and a password)
make deploy                          # docker compose up -d --build
```

Full DigitalOcean walkthrough (firewall, HTTPS, day-2 ops) in
[`deploy/README.md`](deploy/README.md).

## How it's built

```
config/        settings, the list of series to pull, the index universe
migrations/    DuckDB schema (idempotent .sql)
src/vantage/
  connectors/  one file per source; subclass Connector, emit canonical Observations
  storage/     DuckDB + immutable Parquet raw landing; point-in-time readers
  index/       cap-weighted construction, sub-sector sub-indices
               healthcare investor-firm watchlist helpers
  transforms/  YoY/z-score signals, as-of alignment, lead-lag correlation
  pipeline/    ingest + refresh orchestration + daily scheduler
  app/         the Streamlit web terminal (read-only driver over the package)
notebooks/     thin drivers (percent format)
deploy/        Dockerfile + compose for the droplet (web + scheduler)
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
- **Phase 4:** the Streamlit terminal and daily scheduler ship now (`app/`,
  `deploy/`); still to come — alerts and richer cross-filtering.
