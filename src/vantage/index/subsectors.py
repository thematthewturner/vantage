"""Build the whole-universe index and every sub-sector sub-index.

Same construction code path for each; only the membership filter differs.
"""

from __future__ import annotations

import duckdb

from vantage.config import Settings
from vantage.index.construction import build_index
from vantage.index.universe import SUBSECTORS, index_id_for, members
from vantage.storage.readers import prices_wide  # noqa: F401  (re-exported convenience)
from vantage.storage.writers import write_index


def _prices_long(con: duckdb.DuckDBPyConnection):
    return con.execute(
        "SELECT ticker, date, close, adj_close, shares_out FROM prices ORDER BY date"
    ).df()


def build_all_indices(
    con: duckdb.DuckDBPyConnection, settings: Settings | None = None
) -> list[str]:
    """Build VHC plus VHC_<SUBSECTOR> for each sub-sector with members. Returns ids built."""
    settings = settings or Settings.load()
    prices = _prices_long(con)
    built: list[str] = []

    for subsector in [None, *SUBSECTORS]:
        mem = members(subsector)
        if not mem:
            continue
        index_id = index_id_for(subsector)
        levels, weights = build_index(
            index_id, mem, prices,
            base_value=settings.index_base_value,
            base_date=settings.index_base_date,
            rebalance=settings.rebalance,
        )
        if levels.empty:
            continue
        write_index(con, index_id, levels, weights)
        built.append(index_id)
    return built
