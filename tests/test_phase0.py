"""Phase 0 acceptance: dbt build is green, seeds load, schema matches spec,
and re-running the build is idempotent (no row drift, same column shapes)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = REPO_ROOT / "dbt_vantage"


def _dbt_bin() -> str:
    # Prefer the dbt next to the current interpreter (works in any venv layout),
    # fall back to PATH for system installs.
    candidate = Path(sys.executable).parent / "dbt"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("dbt")
    if not found:
        pytest.skip("dbt not installed in this environment")
    return found


def _run_build() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _dbt_bin(),
            "build",
            "--project-dir",
            str(DBT_DIR),
            "--profiles-dir",
            str(DBT_DIR),
            "--no-partial-parse",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def warehouse() -> duckdb.DuckDBPyConnection:
    result = _run_build()
    assert result.returncode == 0, f"dbt build failed:\n{result.stdout}\n{result.stderr}"
    con = duckdb.connect(str(REPO_ROOT / "vantage.duckdb"), read_only=True)
    yield con
    con.close()


EXPECTED_MARTS = {
    "dim_company",
    "dim_segment",
    "dim_source",
    "dim_person",
    "fact_funding_round",
    "fact_financials",
    "fact_covered_lives",
    "fact_operating_metric",
    "fact_valuation",
    "fact_event",
    "fact_projection",
    "fact_policy_exposure",
}


def test_all_mart_tables_exist(warehouse: duckdb.DuckDBPyConnection) -> None:
    actual = {
        r[0]
        for r in warehouse.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' "
            "AND (table_name LIKE 'dim_%' OR table_name LIKE 'fact_%') "
            "AND table_name NOT LIKE '%_seed'"
        ).fetchall()
    }
    assert EXPECTED_MARTS == actual


def test_seeds_loaded(warehouse: duckdb.DuckDBPyConnection) -> None:
    n_segments = warehouse.execute("SELECT COUNT(*) FROM dim_segment").fetchone()[0]
    n_companies = warehouse.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
    assert n_segments >= 15, "segment taxonomy should cover all major verticals"
    assert n_companies >= 30, "cold-start directory should have at least 30 companies"


def test_dim_company_shape_matches_spec(warehouse: duckdb.DuckDBPyConnection) -> None:
    cols = {
        r[0]
        for r in warehouse.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='dim_company'"
        ).fetchall()
    }
    spec_cols = {
        "company_id", "legal_name", "status", "ticker", "exchange", "cik",
        "segment", "sub_segment", "business_model", "is_public_benefit",
        "founded_year", "hq_state", "website", "description",
    }
    assert cols == spec_cols


def test_money_columns_are_decimal(warehouse: duckdb.DuckDBPyConnection) -> None:
    # CLAUDE.md invariant: money is DECIMAL, never FLOAT.
    rows = warehouse.execute(
        "SELECT table_name, column_name, data_type "
        "FROM information_schema.columns "
        "WHERE table_name IN ('fact_financials','fact_funding_round','fact_valuation','fact_projection') "
        "AND column_name IN ('revenue','gross_profit','opex','adj_ebitda','net_income',"
        "'free_cash_flow','cash_and_sti','amount_usd','post_money_valuation',"
        "'valuation_usd','projected_revenue')"
    ).fetchall()
    for table, col, dtype in rows:
        assert dtype.startswith("DECIMAL"), f"{table}.{col} should be DECIMAL, got {dtype}"


def test_build_is_idempotent(warehouse: duckdb.DuckDBPyConnection) -> None:
    # Re-running dbt build should not duplicate seed rows. Drop the read-only
    # connection's lock between builds so dbt can acquire the writer lock.
    before = warehouse.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
    warehouse.close()
    try:
        result = _run_build()
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        # Reopen so subsequent assertions / teardown still work.
        pass
    con = duckdb.connect(str(REPO_ROOT / "vantage.duckdb"), read_only=True)
    try:
        after = con.execute("SELECT COUNT(*) FROM dim_company").fetchone()[0]
    finally:
        con.close()
    assert before == after
