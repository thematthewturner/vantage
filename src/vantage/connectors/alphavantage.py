"""Alpha Vantage near-time intraday technical-signal connector.

Alpha Vantage is a practical low-cost feed for Phase 1 experiments: it offers a
free API key for most datasets (currently 25 requests/day) and paid tiers when a
larger symbol universe or fresher licensed US market data is needed. This
connector intentionally ingests technical indicators, not raw exchange quotes,
so Vantage can trial near-time intraday signals without changing the storage
model yet.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import httpx

from vantage.config import load_sources
from vantage.connectors.base import Connector, register
from vantage.schema import Frequency, Observation, SeriesMeta


@register
class AlphaVantageConnector(Connector):
    """Pull intraday technical indicators from Alpha Vantage."""

    name = "ALPHAVANTAGE"
    base_url = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.environ.get("ALPHAVANTAGE_API_KEY")
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("ALPHAVANTAGE_API_KEY is not set")
        resp = self.client.get(self.base_url, params={**params, "apikey": self.api_key})
        resp.raise_for_status()
        payload = resp.json()
        if "Error Message" in payload:
            raise RuntimeError(f"Alpha Vantage error: {payload['Error Message']}")
        if "Note" in payload or "Information" in payload:
            raise RuntimeError(payload.get("Note") or payload.get("Information"))
        return payload

    def list_series(self) -> list[SeriesMeta]:
        cfg = load_sources().get("alphavantage", {})
        out: list[SeriesMeta] = []
        for series_id, spec in cfg.items():
            symbol = spec.get("symbol", series_id.split("_")[0]).upper()
            indicator = spec.get("indicator", "RSI").upper()
            interval = spec.get("interval", "5min")
            time_period = int(spec.get("time_period", 14))
            out.append(
                SeriesMeta(
                    source=self.name,
                    series_id=series_id,
                    metric_name=spec.get("name", f"{symbol} {interval} {indicator}({time_period})"),
                    frequency=Frequency(spec.get("frequency", "I")),
                    unit=spec.get("unit", indicator),
                    subsector=spec.get("subsector", "intraday"),
                    notes=spec.get(
                        "notes",
                        "Near-time intraday signal from Alpha Vantage technical indicators.",
                    ),
                )
            )
        return out

    def fetch(self, series_id: str, since: dt.date | None) -> Any:
        meta = self.meta_for(series_id)
        cfg = load_sources().get("alphavantage", {})[series_id]
        indicator = cfg.get("indicator", "RSI").upper()
        if indicator != "RSI":
            raise ValueError(
                f"unsupported Alpha Vantage indicator {indicator!r}; currently supports RSI"
            )
        params = {
            "function": "RSI",
            "symbol": cfg.get("symbol", series_id.split("_")[0]).upper(),
            "interval": cfg.get("interval", "5min"),
            "time_period": int(cfg.get("time_period", 14)),
            "series_type": cfg.get("series_type", "close"),
            "datatype": "json",
        }
        if "month" in cfg:
            # Keep raw payload small for repeated refreshes on free/cheap tiers.
            params["month"] = cfg["month"]
        payload = self._get(params)
        payload["_vantage_meta"] = meta.model_dump(mode="json")
        payload["_since"] = since.isoformat() if since else None
        return payload

    def normalize(self, raw: Any, meta: SeriesMeta) -> list[Observation]:
        today = dt.date.today()
        technical = raw.get("Technical Analysis: RSI", {})
        out: list[Observation] = []
        for timestamp, values in sorted(technical.items()):
            value = values.get("RSI")
            observed_at = dt.datetime.fromisoformat(timestamp)
            out.append(
                Observation(
                    source=self.name,
                    series_id=meta.series_id,
                    date=observed_at.date(),
                    value=None if value in (None, "") else float(value),
                    as_of=today,
                    meta={"timestamp": timestamp, "as_of_is_fetch": True},
                )
            )
        return out
