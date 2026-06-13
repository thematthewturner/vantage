-- Vantage core schema. Long-format, bitemporal where it matters.
-- Idempotent: safe to run repeatedly (CREATE TABLE IF NOT EXISTS).

-- One row per (source, series_id): catalog of what we track.
CREATE TABLE IF NOT EXISTS series_meta (
    source       TEXT NOT NULL,
    series_id    TEXT NOT NULL,
    metric_name  TEXT,
    frequency    TEXT,            -- D / W / M / Q / A
    unit         TEXT,
    subsector    TEXT,
    notes        TEXT,
    first_obs    DATE,
    last_obs     DATE,
    last_fetched TIMESTAMP,
    PRIMARY KEY (source, series_id)
);

-- The indicator fact table. Bitemporal: `date` is the period the value
-- describes, `as_of` is the vintage (when the value was knowable). Keeping
-- both means a point-in-time query never sees a revision published after a
-- decision date -> no lookahead in backtests.
CREATE TABLE IF NOT EXISTS observations (
    source    TEXT NOT NULL,
    series_id TEXT NOT NULL,
    date      DATE NOT NULL,
    as_of     DATE NOT NULL,
    value     DOUBLE,
    PRIMARY KEY (source, series_id, date, as_of)
);

-- Index constituents. `to_date` NULL/empty = still in the universe.
-- from_date/to_date support survivorship-bias correction later.
CREATE TABLE IF NOT EXISTS securities (
    ticker    TEXT PRIMARY KEY,
    name      TEXT,
    subsector TEXT,
    from_date DATE,
    to_date   DATE,
    notes     TEXT
);

-- Daily equity prices. `close` drives price-return cap weighting;
-- `adj_close` (dividend+split adjusted) drives total return.
CREATE TABLE IF NOT EXISTS prices (
    ticker     TEXT NOT NULL,
    date       DATE NOT NULL,
    close      DOUBLE,
    adj_close  DOUBLE,
    shares_out DOUBLE,
    PRIMARY KEY (ticker, date)
);

-- Index output: one row per index per day, both return tracks, base=100.
CREATE TABLE IF NOT EXISTS index_values (
    index_id TEXT NOT NULL,
    date     DATE NOT NULL,
    level_pr DOUBLE,   -- price return
    level_tr DOUBLE,   -- total return
    PRIMARY KEY (index_id, date)
);

-- Weights snapshot at each rebalance, for auditability.
CREATE TABLE IF NOT EXISTS index_weights (
    index_id       TEXT NOT NULL,
    rebalance_date DATE NOT NULL,
    ticker         TEXT NOT NULL,
    weight         DOUBLE,
    PRIMARY KEY (index_id, rebalance_date, ticker)
);
