"""Connector base class and registry.

A connector's only job is to pull from one source and emit canonical
``Observation`` rows. It never writes to the database directly (the pipeline
does that), which keeps connectors pure and easy to test offline.

Adding a new source = one file: subclass ``Connector``, implement the three
abstract methods, decorate with ``@register``, and list its series in
``config/sources.toml``. Retries and raw Parquet landing come for free.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from vantage.schema import Observation, SeriesMeta

# Only transient I/O failures are worth retrying. Config errors (e.g. a missing
# API key, raised as RuntimeError) should fail fast, not back off four times.
TRANSIENT_ERRORS = (httpx.TransportError, httpx.HTTPStatusError, ConnectionError, TimeoutError)

REGISTRY: dict[str, type[Connector]] = {}


def register(cls: type[Connector]) -> type[Connector]:
    """Class decorator that adds a connector to the global registry."""
    if not getattr(cls, "name", None):
        raise ValueError(f"{cls.__name__} must set a non-empty `name`")
    if cls.name in REGISTRY:
        raise ValueError(f"duplicate connector name: {cls.name!r}")
    REGISTRY[cls.name] = cls
    return cls


class Connector(ABC):
    """Base class for all data sources."""

    name: str = ""

    @abstractmethod
    def list_series(self) -> list[SeriesMeta]:
        """Series this connector is configured to provide."""

    @abstractmethod
    def fetch(self, series_id: str, since: dt.date | None) -> Any:
        """Raw pull for one series. `since` enables incremental fetch.

        Returns the source's raw payload unchanged (no transformation), so the
        landing layer can persist exactly what came back.
        """

    @abstractmethod
    def normalize(self, raw: Any, meta: SeriesMeta) -> list[Observation]:
        """Map a raw payload to canonical Observations. Pure function."""

    # --- provided by the base class; not overridden ---

    def meta_for(self, series_id: str) -> SeriesMeta:
        for meta in self.list_series():
            if meta.series_id == series_id:
                return meta
        raise KeyError(f"{self.name}: unknown series_id {series_id!r}")

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, max=16),
        retry=retry_if_exception_type(TRANSIENT_ERRORS),
        reraise=True,
    )
    def _fetch_with_retry(self, series_id: str, since: dt.date | None) -> Any:
        return self.fetch(series_id, since)

    def run(self, series_id: str, since: dt.date | None = None) -> tuple[Any, list[Observation]]:
        """Fetch (with retry) and normalize. Returns (raw, observations).

        The pipeline persists `raw` to the Parquet landing and writes the
        observations to DuckDB; the connector stays I/O-free beyond its fetch.
        """
        meta = self.meta_for(series_id)
        raw = self._fetch_with_retry(series_id, since)
        return raw, self.normalize(raw, meta)
