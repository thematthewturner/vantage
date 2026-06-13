"""Universe loading and sub-sector grouping."""

from __future__ import annotations

from vantage.config import load_universe

SUBSECTORS = ["pharma", "payers", "providers", "devices", "biotech", "tools", "distributors"]


def members(subsector: str | None = None) -> list[dict]:
    """Universe members, optionally filtered to one sub-sector."""
    secs = load_universe()
    if subsector is None:
        return secs
    return [s for s in secs if s.get("subsector") == subsector]


def tickers(subsector: str | None = None) -> list[str]:
    return [s["ticker"] for s in members(subsector)]


def index_id_for(subsector: str | None) -> str:
    """Canonical index id: VHC for the whole universe, VHC_<SUBSECTOR> otherwise."""
    return "VHC" if subsector is None else f"VHC_{subsector.upper()}"
