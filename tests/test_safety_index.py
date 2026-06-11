"""Phase 1 safety-index acceptance: all 22 publics get scored, the pure
Graham column produces only 'fail' (the diagnostic), and the species ceiling
classifications respect the enum."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "vantage.duckdb"


@pytest.fixture(scope="module")
def warehouse() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    yield con
    con.close()


def test_all_publics_scored(warehouse: duckdb.DuckDBPyConnection) -> None:
    n_publics = warehouse.execute(
        "SELECT COUNT(*) FROM dim_company WHERE status = 'public'"
    ).fetchone()[0]
    n_scored = warehouse.execute("SELECT COUNT(*) FROM metric_safety_index").fetchone()[0]
    assert n_scored == n_publics, f"expected {n_publics} publics scored, got {n_scored}"


def test_pure_graham_fails_universally(warehouse: duckdb.DuckDBPyConnection) -> None:
    # The point of including pure Graham is to demonstrate it doesn't price
    # this corpus. Every public should land on 'fail' under the classical
    # 7-criterion screen.
    rows = warehouse.execute(
        "SELECT graham_overall, COUNT(*) FROM metric_safety_index GROUP BY graham_overall"
    ).fetchall()
    by_verdict = dict(rows)
    assert by_verdict.get("fail", 0) == sum(by_verdict.values()), (
        f"expected every name to fail Graham; got {by_verdict}"
    )


def test_recommendation_buckets_partition_corpus(warehouse: duckdb.DuckDBPyConnection) -> None:
    rows = warehouse.execute(
        "SELECT recommendation_bucket, COUNT(*) FROM metric_safety_index GROUP BY recommendation_bucket"
    ).fetchall()
    by_bucket = {b: n for b, n in rows}
    valid = {"quality_and_cushion", "watch_list", "neutral", "avoid_or_special_view_required"}
    assert set(by_bucket).issubset(valid), f"unexpected bucket: {set(by_bucket) - valid}"
    assert sum(by_bucket.values()) > 0, "no companies got bucketed"


def test_combined_score_is_signed(warehouse: duckdb.DuckDBPyConnection) -> None:
    # A useful index has both positive and negative scores in the corpus —
    # if everything were one-sided the ranking carries no information.
    rows = warehouse.execute(
        "SELECT MIN(combined_safety_score), MAX(combined_safety_score) FROM metric_safety_index"
    ).fetchone()
    lo, hi = float(rows[0]), float(rows[1])
    assert lo < 0 and hi > 0, f"score should straddle zero, got [{lo}, {hi}]"


def test_every_market_data_row_has_a_source(warehouse: duckdb.DuckDBPyConnection) -> None:
    # The provenance invariant carries to the new facts.
    nulls = warehouse.execute(
        "SELECT COUNT(*) FROM fact_market_data WHERE source_id IS NULL"
    ).fetchone()[0]
    assert nulls == 0


def test_market_data_sources_are_marked_estimate(warehouse: duckdb.DuckDBPyConnection) -> None:
    # Phase 0 market data is hand-curated; CLAUDE.md invariant #1 forbids
    # silently labeling it 'primary'. Phase 1 ingest replaces with XBRL.
    row = warehouse.execute(
        "SELECT reliability FROM dim_source WHERE source_id = 'src_market_v0'"
    ).fetchone()
    assert row is not None and row[0] == "estimate"


def test_history_has_multiple_snapshots(warehouse: duckdb.DuckDBPyConnection) -> None:
    n_dates = warehouse.execute(
        "SELECT COUNT(DISTINCT as_of_date) FROM metric_safety_index_history"
    ).fetchone()[0]
    assert n_dates >= 2, f"backtest needs >= 2 snapshots, got {n_dates}"


def test_transitions_emit_at_least_one_rerate(warehouse: duckdb.DuckDBPyConnection) -> None:
    # A useful backtest produces SOME bucket movement. If every transition
    # is 'unchanged' the framework is too coarse.
    rerated = warehouse.execute(
        "SELECT COUNT(*) FROM metric_safety_index_transitions WHERE transition IN ('rerated_up', 'rerated_down')"
    ).fetchone()[0]
    assert rerated > 0, "expected at least one bucket transition in the backtest window"


def test_private_index_covers_active_privates(warehouse: duckdb.DuckDBPyConnection) -> None:
    n_priv = warehouse.execute(
        "SELECT COUNT(*) FROM dim_company WHERE status = 'private'"
    ).fetchone()[0]
    n_indexed = warehouse.execute(
        "SELECT COUNT(*) FROM metric_private_safety_index"
    ).fetchone()[0]
    assert n_indexed == n_priv, f"expected {n_priv} active privates indexed, got {n_indexed}"


def test_private_index_ranks_devoted_in_top_band(warehouse: duckdb.DuckDBPyConnection) -> None:
    # Devoted Health's Series E ($12.6B post on $300M) is the most capital-
    # efficient fresh mark in the private corpus. If it drops out of the top
    # cohort that's a real signal worth investigating, not a flaky test.
    row = warehouse.execute(
        "SELECT private_verdict FROM metric_private_safety_index WHERE company_id = 'devoted_health'"
    ).fetchone()
    assert row is not None and row[0] == "capital_efficient_fresh_mark"


def test_guidance_prior_falls_back_to_bootstrap(warehouse: duckdb.DuckDBPyConnection) -> None:
    # With no historical guidance loaded yet, every prior should still be
    # the 0.50 bootstrap. The empirical pipeline activates only when
    # fact_historical_guidance has rows.
    rows = warehouse.execute(
        "SELECT guidance_reliability, prior_strength FROM fact_guidance_accuracy"
    ).fetchall()
    assert all(float(r[0]) == 0.50 and r[1] == "bootstrap" for r in rows), (
        "expected all priors at 0.50/bootstrap until historical guidance loads"
    )
