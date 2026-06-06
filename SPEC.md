# VANTAGE — Master Build Prompt for Claude Code
### Digital Health Intelligence Engine ("Rock Health on steroids")

> **How to use this file:** Drop it in an empty repo as `SPEC.md`, open Claude Code in that directory, and start with: *"Read SPEC.md. Build Phase 0, then stop and show me the schema before continuing."* Build phase-by-phase; don't let the agent one-shot the whole thing. Rename `VANTAGE` to whatever you want.

---

## 0 · Mission & North Star

Build a single-operator intelligence system that is the **system of record for digital health company economics** — public and private. It ingests primary sources (SEC filings, CMS data, funding news), normalizes every company onto a **denominator-aware metric layer**, runs **scenario-banded valuation models**, and auto-generates **investment-grade prospectuses**.

**Success criteria (the agent should optimize for these):**

1. Every figure traces to a source URL + retrieval date (provenance is non-negotiable — this is what makes it citable IP).
2. Cross-company metrics are *only* compared within a normalized denominator class (never compare revenue/eligible-life to revenue/at-risk-member).
3. A new company can go from "ticker or name" → fully populated profile + prospectus in one command.
4. Refresh is incremental and idempotent — re-running ingestion never duplicates or corrupts rows.

**What makes this beat Rock Health / CB Insights (build these as first-class features, not afterthoughts):**

- Denominator-aware `revenue_per_covered_life` (eligible vs enrolled vs attributed vs at-risk).
- Gross-vs-net economics for VBC enablers (platform contribution per life, not gross pass-through).
- Policy-exposure scoring (MA rate/v28, ACA APTC cliff, CMMI model dependence) per company.
- Per-company base/bull/bear revenue projections with explicit, queryable assumption objects.
- Auto-generated investment memos.

---

## 1 · Tech Stack (opinionated — do not substitute without flagging)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | — |
| Analytical store | **DuckDB** (embedded, single file `vantage.duckdb`) | Zero infra, fast OLAP, Claude Code can build+query directly; sync to Snowflake later |
| Transform / metrics | **dbt-duckdb** | Version-controlled metric definitions = a portable Trusted Metrics Layer |
| Validation | **Pydantic v2** | Schema enforcement at ingestion boundary |
| SEC ingestion | **`edgartools`** (preferred) + SEC `companyfacts` XBRL API | Structured financials from 10-K/10-Q/S-1 without scraping |
| Web/news ingestion | `httpx` + `selectolax`; RSS via `feedparser` | Funding-round capture |
| LLM enrichment | **Anthropic SDK** (`claude-opus-4-x` for memos, a Haiku-class model for classification) | Entity extraction, news tagging, prospectus drafting |
| Semantic search | **LanceDB** (local, embedded) | "Ask the filing corpus" over chunked filings/news |
| Dashboard | **Evidence.dev** (SQL + markdown) primary; Streamlit if interactivity needed | Pairs natively with DuckDB/dbt; report-grade output |
| Orchestration | **Prefect** (local) or cron + GitHub Actions | Scheduled incremental refresh |
| Config / secrets | `pydantic-settings` + `.env` (gitignored) | — |

Use `uv` for env + dependency management. Pin everything in `pyproject.toml`.

---

## 2 · Data Model (the core — get this right first)

Dimensional model in DuckDB. Conformed dimensions, fact tables grain-explicit. Generate as dbt sources/models; physical DDL below is the target shape.

```sql
-- DIMENSIONS ----------------------------------------------------------------
dim_company (
  company_id        VARCHAR PRIMARY KEY,   -- slug, e.g. 'aledade'
  legal_name        VARCHAR,
  status            VARCHAR,               -- 'public' | 'private' | 'acquired'
  ticker            VARCHAR,               -- nullable
  exchange          VARCHAR,
  cik               VARCHAR,               -- SEC CIK for public/S-1 filers
  segment           VARCHAR,               -- FK to dim_segment
  sub_segment       VARCHAR,
  business_model    VARCHAR,               -- 'full_risk' | 'vbc_enabler' | 'dtc_sub' | 'saas' | 'dx' | 'data_infra' | ...
  is_public_benefit BOOLEAN,
  founded_year      INT,
  hq_state          VARCHAR,
  website           VARCHAR,
  description        VARCHAR
)

dim_segment (
  segment           VARCHAR PRIMARY KEY,
  denominator_class VARCHAR,    -- 'covered_life' | 'provider' | 'test' | 'contract' | 'transaction'
  default_life_type VARCHAR,    -- for covered_life segments: 'at_risk'|'attributed'|'enrolled'|'eligible'
  typical_rev_per_unit_low  DECIMAL,
  typical_rev_per_unit_high DECIMAL,
  notes             VARCHAR
)

dim_source (
  source_id    VARCHAR PRIMARY KEY,
  source_type  VARCHAR,   -- '10-K'|'10-Q'|'S-1'|'press'|'cms_puf'|'secondary_mkt'|'analyst'|'manual'
  url          VARCHAR,
  retrieved_at TIMESTAMP,
  reliability  VARCHAR     -- 'primary'|'secondary'|'estimate'
)

dim_person (person_id PK, full_name, role, company_id FK, is_board BOOLEAN)

-- FACTS ----------------------------------------------------------------------
fact_funding_round (
  round_id PK, company_id FK, announced_date DATE,
  round_type VARCHAR,           -- 'seed'|'series_a'.. 'debt'|'growth'
  amount_usd DECIMAL, post_money_valuation DECIMAL,
  lead_investors VARCHAR[], source_id FK
)

fact_financials (                -- grain: company × fiscal period × line item set
  company_id FK, fiscal_period VARCHAR,   -- '2025FY','2026Q1'
  period_end DATE, is_guidance BOOLEAN,
  revenue DECIMAL, gross_profit DECIMAL, gross_margin DECIMAL,
  opex DECIMAL, adj_ebitda DECIMAL, net_income DECIMAL,
  free_cash_flow DECIMAL, cash_and_sti DECIMAL,
  source_id FK
)

fact_covered_lives (             -- grain: company × period × life_type
  company_id FK, fiscal_period VARCHAR,
  life_type VARCHAR,             -- 'at_risk'|'attributed'|'enrolled'|'eligible'|'subscriber'
  lives_count BIGINT, source_id FK
)

fact_operating_metric (          -- flexible EAV for anything else (providers, tests, MLR, Stars...)
  company_id FK, fiscal_period VARCHAR,
  metric_name VARCHAR, metric_value DECIMAL, unit VARCHAR, source_id FK
)

fact_valuation (                 -- grain: company × date × method
  company_id FK, as_of_date DATE,
  valuation_usd DECIMAL, price_per_share DECIMAL,
  method VARCHAR,               -- 'primary_round'|'secondary_npm'|'public_mktcap'|'409a'
  source_id FK
)

fact_event (                     -- timeline: IPO, M&A, partnership, layoff, regulatory
  event_id PK, company_id FK, event_date DATE,
  event_type VARCHAR, headline VARCHAR, source_id FK
)

fact_projection (                -- grain: company × scenario × year
  company_id FK, scenario VARCHAR,  -- 'base'|'bull'|'bear'
  fiscal_year INT, projected_revenue DECIMAL,
  cagr DECIMAL, assumptions JSON,   -- queryable assumption object
  generated_at TIMESTAMP, method VARCHAR
)

fact_policy_exposure (           -- the differentiator
  company_id FK,
  ma_rate_exposure INT,        -- 0-5 score
  aca_aptc_exposure INT,
  cmmi_model_dependence INT,
  rationale VARCHAR, source_id FK
)
```

**Seed immediately** with the ~120-company directory and the revenue-per-covered-life dataset already produced (CSV import). That's the cold-start corpus.

---

## 3 · Normalized Metric Layer (dbt models)

Define every metric once, in dbt, with tests. These are the "steroids." Key models:

- **`metric_rev_per_covered_life`** — joins `fact_financials` × `fact_covered_lives` *on matching life_type only*; emits one row per life_type with an explicit `life_type` column. Never collapse across types. dbt test: fail if a comparison view mixes `denominator_class`.
- **`metric_net_economics_per_life`** — for `business_model = 'vbc_enabler'`: platform contribution (not gross revenue) ÷ attributed lives. Flag gross-vs-net delta.
- **`metric_growth_yoy`** — period-over-period revenue, guidance-aware (separate actual vs guided).
- **`metric_rule_of_40`** — revenue growth % + adj-EBITDA margin %.
- **`metric_capital_efficiency`** — cumulative revenue ÷ total equity raised (revenue per $ funded).
- **`metric_implied_ev_revenue`** — latest valuation ÷ latest revenue; segment-percentile rank.
- **`metric_burn_multiple`** — net burn ÷ net new ARR, where derivable.

Each model: documented in `schema.yml`, with `not_null` / `accepted_values` / relationship tests. A failing test blocks the build.

---

## 4 · Ingestion (specific sources — wire these)

1. **SEC EDGAR** via `edgartools`: pull latest 10-K, 10-Q, S-1 for any CIK. Extract revenue/margins/cash from XBRL `companyfacts`; parse S-1 "covered lives"/"members"/"attributed lives" language with a Claude extraction pass into `fact_covered_lives`.
2. **CMS public data**: MSSP ACO PUF (shared savings, beneficiaries per ACO), MA enrollment files — validate/triangulate private VBC and MA covered-life counts independently of company PR.
3. **Funding news**: RSS/scrape Fierce Healthcare, Axios Pro Health Tech, MedCity News, Endpoints, TechCrunch. Claude-classify each item → `fact_funding_round` / `fact_event` with dedup on (company, date, amount).
4. **Secondary marks**: capture Nasdaq Private Market / Forge / EquityZen estimates into `fact_valuation` (method='secondary_npm', reliability='estimate').
5. **Manual/analyst**: a `seeds/` folder for hand-curated figures (Rock Health reports, your own analysis) — always tagged reliability and source.

Ingestion contract: every writer is **idempotent** (upsert on natural key), validates through Pydantic before insert, and writes a `dim_source` row first. No source row → no fact row.

---

## 5 · Analytical Engine

- **Scenario engine** (`engine/scenarios.py`): given a company's history + segment priors, generate base/bull/bear revenue paths to a target year. Assumptions are explicit objects (e.g. `{"membership_cagr": 0.18, "rev_per_life": 14800, "aptc_restored": false}`) persisted to `fact_projection.assumptions`. Re-runnable and overridable.
- **Comp engine** (`engine/comps.py`): build a peer set by `business_model` + `denominator_class`; return denominator-aware percentile ranks. Refuse to rank across incompatible denominator classes (raise, don't silently fudge).
- **Valuation** (`engine/valuation.py`): comp-multiple (segment median EV/Rev applied to projected revenue) + a DCF-lite for names with positive projectable FCF. Output a valuation range, not a point.
- **Policy sensitivity** (`engine/policy.py`): score MA / ACA-APTC / CMMI exposure; surface which companies the bear macro case hits hardest.

---

## 6 · Prospectus Generator (the "invest the works" deliverable)

`vantage prospectus <company_id>` → a structured investment memo (Markdown + optional PDF via the system's renderer):

1. **Thesis** (3 sentences, Claude-drafted from the data, not the web).
2. **Business model & denominator class** — what "a covered life" means for *this* company.
3. **Financial snapshot** — table from `fact_financials`, fully cited.
4. **Normalized metrics** — rev/covered-life (correct denominator), Rule of 40, capital efficiency, EV/Rev percentile vs peer set.
5. **Scenario table** — base/bull/bear revenue + valuation range, assumptions listed.
6. **Policy exposure** — MA/ACA/CMMI scores + rationale.
7. **Risks** — top 5, model-derived.
8. **Verdict** — a structured stance (e.g. conviction 1-5) with the single metric that would change it.

Every numeric claim renders with an inline source ref. The memo must be defensible to a buy-side analyst.

---

## 7 · Outputs

- **Evidence.dev report site**: market overview, segment leaderboards (denominator-aware), funding-velocity dashboard, policy-exposure heatmap, single-company deep-dive pages.
- **Quarterly "State of Digital Health" auto-report** — the artifact that becomes your public thought-leadership drop.
- **Watchlist alerts**: new S-1 filed, funding round, valuation mark change, metric breach → notification (reuse your existing Jarvis/Telegram channel if desired).

---

## 8 · Build Phases (acceptance-gated — stop after each)

- **Phase 0 — Scaffold:** repo, `uv` env, DuckDB init, dbt project, full schema from §2, seed the directory + rev/life CSVs. *Accept: `dbt build` green, seeds loaded, schema matches spec.*
- **Phase 1 — SEC ingestion:** `edgartools` pull + XBRL → `fact_financials` for all public names. *Accept: 15+ public cos populated with cited financials.*
- **Phase 2 — Metric layer:** all §3 dbt models + tests. *Accept: rev_per_covered_life returns correct, denominator-separated rows; mixing test fails as designed.*
- **Phase 3 — Funding/news + Claude enrichment:** RSS ingest, classification, dedup. *Accept: backfill 2025-26 rounds, zero dupes on re-run.*
- **Phase 4 — Scenario + valuation + policy engines.** *Accept: base/bull/bear + valuation range + policy scores for top 20.*
- **Phase 5 — Prospectus generator.** *Accept: `vantage prospectus aledade` produces a fully-cited memo.*
- **Phase 6 — Evidence.dev dashboard.** *Accept: market overview + deep-dive pages render.*
- **Phase 7 — Orchestrated refresh + alerts.** *Accept: idempotent scheduled run; alert fires on a simulated new filing.*

---

## 9 · Repo Structure

```
vantage/
├── SPEC.md                 # this file
├── CLAUDE.md               # conventions below + "always read SPEC.md first"
├── pyproject.toml
├── .env.example
├── vantage.duckdb          # gitignored
├── ingest/                 # sec.py, news.py, cms.py, secondary.py  (Pydantic-validated writers)
├── dbt_vantage/            # models/{staging,marts,metrics}/, seeds/, schema.yml tests
├── engine/                 # scenarios.py, comps.py, valuation.py, policy.py
├── prospectus/             # generator.py, templates/
├── reports/                # Evidence.dev project
├── orchestration/          # prefect_flows.py
├── cli.py                  # `vantage ingest|build|prospectus|report`
└── tests/
```

## 10 · Conventions (put in CLAUDE.md)

- **Provenance or it didn't happen**: no fact row without a `dim_source` row. Estimates tagged `reliability='estimate'`, never laundered into 'primary'.
- **Denominator discipline**: any cross-company metric must assert matching `denominator_class`; otherwise raise.
- **Idempotent ingestion**: upsert on natural keys; re-runs are safe.
- **Money** = DECIMAL, USD millions, documented. No floats for currency.
- **Guidance ≠ actuals**: never blend; `is_guidance` flag always set.
- **Runnable, not illustrative**: real code, typed, tested. No pseudocode.
- **Claude for judgment, SQL for truth**: LLM extracts/drafts; the DB + dbt is the source of record. Never let the model invent a number that isn't in a source.

---

## Forks for the operator to decide (flag, don't block)

1. **Local vs cloud:** DuckDB local is the default and correct for v1. If this becomes shared IP / a product, the dbt layer ports to Snowflake/Databricks unchanged — design marts to be warehouse-agnostic now.
2. **Personal tool vs published moat:** if the quarterly report is going public, add a `publish/` path with redaction rules (don't leak paid-source data) and a citation-export step.
3. **Paid data:** Crunchbase/PitchBook APIs would deepen private-round coverage but cost $. v1 runs entirely on free primary sources (SEC, CMS) + news; add paid connectors as optional adapters behind the same `ingest/` interface.
