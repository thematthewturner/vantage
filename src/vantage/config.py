"""Configuration loading from the TOML files in config/.

Keeps a single source of truth for paths and the list of series/securities, and
resolves them relative to the repo root so notebooks and the CLI behave the same.
"""

from __future__ import annotations

import datetime as dt
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def _load_toml(path: Path) -> dict:
    with path.open("rb") as fh:
        return tomllib.load(fh)


@dataclass(frozen=True)
class Settings:
    db_path: Path
    raw_dir: Path
    index_base_value: float
    index_base_date: dt.date
    index_baseline_start_date: dt.date
    rebalance: str

    @classmethod
    def load(cls) -> Settings:
        data = _load_toml(CONFIG_DIR / "settings.toml")
        storage = data["storage"]
        index = data["index"]
        return cls(
            db_path=REPO_ROOT / storage["db_path"],
            raw_dir=REPO_ROOT / storage["raw_dir"],
            index_base_value=float(index["base_value"]),
            index_base_date=dt.date.fromisoformat(index["base_date"]),
            index_baseline_start_date=dt.date.fromisoformat(
                index.get("baseline_start_date", index["base_date"])
            ),
            rebalance=index["rebalance"],
        )


def load_sources() -> dict:
    """Per-connector series config keyed by connector name."""
    return _load_toml(CONFIG_DIR / "sources.toml")


def load_universe() -> list[dict]:
    """List of security dicts: ticker, name, subsector, from, to."""
    return _load_toml(CONFIG_DIR / "universe.toml").get("security", [])


def load_investor_firms() -> list[dict]:
    """Curated top-25 healthcare investor-firm watchlist records."""
    return _load_toml(CONFIG_DIR / "investor_firms.toml").get("firm", [])
