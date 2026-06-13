"""Refresh entrypoint: ingest all sources, then rebuild every index.

Run as ``python -m vantage.pipeline.refresh``. Exits non-zero if any source
errored, so cron surfaces failures, while still completing the rest of the run.
"""

from __future__ import annotations

import logging
import sys

from vantage.config import Settings
from vantage.index.subsectors import build_all_indices
from vantage.pipeline.ingest import ingest_indicators, ingest_prices
from vantage.storage.db import connect

log = logging.getLogger("vantage.refresh")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    argv = sys.argv[1:] if argv is None else argv
    skip_prices = "--no-prices" in argv

    settings = Settings.load()
    con = connect(settings)

    ind = ingest_indicators(con, settings)
    log.info("indicators: %d series updated, %d errors",
             len(ind["counts"]), len(ind["errors"]))

    price_errors: dict = {}
    if not skip_prices:
        pr = ingest_prices(con, settings)
        price_errors = pr["errors"]
        log.info("prices: %d rows upserted, %d errors", pr["rows"], len(price_errors))

    built = build_all_indices(con, settings)
    log.info("indices built: %s", ", ".join(built) if built else "(none -- no price data)")

    con.close()
    n_errors = len(ind["errors"]) + len(price_errors)
    return 1 if n_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
