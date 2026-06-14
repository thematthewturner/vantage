"""Healthcare investor-firm watchlist loading and lookup utilities."""

from __future__ import annotations

from collections.abc import Iterable

from vantage.config import load_investor_firms

TOP_HEALTHCARE_INVESTOR_COUNT = 25


def firms() -> list[dict]:
    """Return the curated top-25 healthcare investor firms sorted by rank."""
    return sorted(load_investor_firms(), key=lambda firm: firm["rank"])


def slugs() -> list[str]:
    """Stable identifiers for tailing firm news, filings, and portfolio activity."""
    return [firm["slug"] for firm in firms()]


def by_slug(slug: str) -> dict:
    """Return one investor firm by slug."""
    for firm in firms():
        if firm["slug"] == slug:
            return firm
    raise KeyError(f"Unknown healthcare investor firm slug: {slug}")


def filter_by_focus(focus_terms: Iterable[str]) -> list[dict]:
    """Find firms whose focus tags contain any supplied term.

    Matching is case-insensitive and partial so callers can search for broad
    concepts such as ``AI``, ``devices``, ``biotech``, or ``digital``.
    """
    terms = [term.lower() for term in focus_terms]
    if not terms:
        return firms()

    matches = []
    for firm in firms():
        haystack = " ".join(firm.get("focus", [])).lower()
        if any(term in haystack for term in terms):
            matches.append(firm)
    return matches
