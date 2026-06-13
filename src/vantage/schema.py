"""Canonical data models shared across connectors, storage, and transforms.

Everything an upstream source produces is funnelled into these models, so the
rest of the system never has to know source-specific quirks.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field


class Frequency(StrEnum):
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"
    QUARTERLY = "Q"
    ANNUAL = "A"


class SeriesMeta(BaseModel):
    """Describes one time series a connector offers."""

    source: str
    series_id: str
    metric_name: str
    frequency: Frequency
    unit: str | None = None
    subsector: str | None = None
    notes: str | None = None


class Observation(BaseModel):
    """One value of one series. Long format, bitemporal.

    `date` is the period the value describes; `as_of` is the vintage (when the
    value became knowable). Connectors that can't supply a true vintage set
    `as_of` to the fetch date and flag it in `meta["as_of_is_fetch"] = True`.
    """

    source: str
    series_id: str
    date: dt.date
    value: float | None
    as_of: dt.date
    meta: dict = Field(default_factory=dict)
