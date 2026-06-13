"""Immutable Parquet landing for raw connector pulls.

Every fetch is persisted verbatim before anything touches the database, giving
a cheap audit trail and full reprocessability: the entire DuckDB store can be
rebuilt from ``data/raw/`` at any time.
"""

from __future__ import annotations

import datetime as dt
import json
import re

import pandas as pd

from vantage.config import Settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _slug(value: str) -> str:
    return _SAFE.sub("_", value)


def land(source: str, series_id: str, raw: object, settings: Settings | None = None) -> str:
    """Write a raw payload to data/raw/<source>/<series>/<fetched_at>.parquet.

    Arbitrary JSON-serialisable payloads are wrapped in a one-row frame holding
    the serialised blob plus capture metadata; this keeps the landing uniform
    regardless of source shape. Returns the written path.
    """
    settings = settings or Settings.load()
    fetched_at = dt.datetime.now(dt.UTC)
    out_dir = settings.raw_dir / _slug(source) / _slug(series_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{fetched_at:%Y%m%dT%H%M%SZ}.parquet"

    frame = pd.DataFrame(
        [
            {
                "source": source,
                "series_id": series_id,
                "fetched_at": fetched_at,
                "payload": json.dumps(raw, default=str),
            }
        ]
    )
    frame.to_parquet(out_path, index=False)
    return str(out_path)
