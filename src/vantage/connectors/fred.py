"""FRED connector (St. Louis Fed).

One API key (free, ``FRED_API_KEY`` env var) unlocks a large set of tailored
healthcare series: medical-care CPI, healthcare employment, PCE health, JOLTS,
hospital/pharma PPI, plus macro context like the 10Y Treasury yield.

Frequency and units come from FRED's own series metadata when available, with a
fallback to whatever is declared in ``config/sources.toml``.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import httpx

from vantage.config import load_sources
from vantage.connectors.base import Connector, register
from vantage.schema import Frequency, Observation, SeriesMeta

_FRED_FREQ = {
    "Daily": Frequency.DAILY,
    "Weekly": Frequency.WEEKLY,
    "Monthly": Frequency.MONTHLY,
    "Quarterly": Frequency.QUARTERLY,
    "Annual": Frequency.ANNUAL,
}


@register
class FredConnector(Connector):
    name = "FRED"
    base_url = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def _get(self, endpoint: str, params: dict) -> dict:
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY is not set")
        params = {**params, "api_key": self.api_key, "file_type": "json"}
        resp = self.client.get(f"{self.base_url}/{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()

    def list_series(self) -> list[SeriesMeta]:
        cfg = load_sources().get("fred", {})
        out: list[SeriesMeta] = []
        for series_id, spec in cfg.items():
            out.append(
                SeriesMeta(
                    source=self.name,
                    series_id=series_id,
                    metric_name=spec.get("name", series_id),
                    frequency=Frequency(spec.get("frequency", "M")),
                    unit=spec.get("unit"),
                    subsector=spec.get("subsector"),
                )
            )
        return out

    def fetch(self, series_id: str, since: dt.date | None) -> Any:
        params: dict[str, Any] = {"series_id": series_id}
        if since is not None:
            params["observation_start"] = since.isoformat()
        return self._get("series/observations", params)

    def normalize(self, raw: Any, meta: SeriesMeta) -> list[Observation]:
        today = dt.date.today()
        out: list[Observation] = []
        for row in raw.get("observations", []):
            raw_val = row.get("value")
            # FRED encodes missing values as ".".
            value = None if raw_val in (".", "", None) else float(raw_val)
            out.append(
                Observation(
                    source=self.name,
                    series_id=meta.series_id,
                    date=dt.date.fromisoformat(row["date"]),
                    value=value,
                    # Plain observations endpoint returns the current vintage only,
                    # so as_of is the fetch date. ALFRED vintages are a Phase 2 add.
                    as_of=today,
                    meta={"as_of_is_fetch": True},
                )
            )
        return out
