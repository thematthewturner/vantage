"""Mixed-frequency alignment via as-of joins.

To compare a daily stock index against a monthly/quarterly indicator, each
index date takes the most recent indicator value whose period has already
ended. Values are forward-filled but never interpolated past the last known
print, and never pulled from a future period -- preserving point-in-time honesty.
"""

from __future__ import annotations

import pandas as pd


def asof_align(
    index: pd.Series,
    indicator: pd.Series,
    *,
    index_name: str = "index",
    indicator_name: str = "indicator",
) -> pd.DataFrame:
    """As-of join `indicator` onto `index`'s (daily) dates.

    Both inputs are date-indexed Series. Returns a date-indexed frame with the
    index column and the as-of indicator column aligned on the index's dates.
    """
    left = pd.DataFrame(
        {
            "date": pd.to_datetime(index.index),
            index_name: index.to_numpy(),
        }
    ).sort_values("date")
    right = pd.DataFrame(
        {
            "date": pd.to_datetime(indicator.index),
            indicator_name: indicator.to_numpy(),
        }
    ).sort_values("date")

    merged = pd.merge_asof(left, right, on="date", direction="backward")
    return merged.set_index("date")
