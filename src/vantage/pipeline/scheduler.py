"""A tiny, dependency-free daily scheduler for the refresh.

Designed to run as its own long-lived process (a container in ``deploy/``).
It refreshes once on startup if the store is empty, then sleeps until the next
``REFRESH_HOUR_UTC`` every day and refreshes again. No cron, no extra deps --
restart-safe because the next run time is recomputed from the wall clock on
every loop.

Env:
* ``REFRESH_HOUR_UTC``   hour (0-23) to run the daily refresh. Default 6.
* ``REFRESH_ON_START``   "1"/"true" to always refresh on boot. Default: only
  when the store has no index data yet.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import time

from vantage.config import Settings
from vantage.pipeline import alerts, refresh

log = logging.getLogger("vantage.scheduler")


def _refresh_hour() -> int:
    try:
        return max(0, min(23, int(os.environ.get("REFRESH_HOUR_UTC", "6"))))
    except ValueError:
        return 6


def seconds_until(hour: int, now: dt.datetime | None = None) -> float:
    """Seconds from `now` until the next occurrence of `hour`:00 UTC."""
    now = now or dt.datetime.now(dt.UTC)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return (target - now).total_seconds()


def _store_has_data() -> bool:
    """True if an index has already been built (so we needn't refresh on boot)."""
    settings = Settings.load()
    if not settings.db_path.exists():
        return False
    import duckdb

    try:
        con = duckdb.connect(str(settings.db_path), read_only=True)
    except duckdb.Error:
        return False
    try:
        row = con.execute("SELECT count(*) FROM index_values").fetchone()
        return bool(row and row[0])
    except duckdb.Error:
        return False
    finally:
        con.close()


def _should_refresh_on_start() -> bool:
    flag = os.environ.get("REFRESH_ON_START", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    return not _store_has_data()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    hour = _refresh_hour()
    log.info("scheduler started; daily refresh at %02d:00 UTC", hour)

    if _should_refresh_on_start():
        log.info("running initial refresh (store empty or REFRESH_ON_START set)")
        try:
            code = refresh.main([])
            if code:
                alerts.notify(
                    f"vantage: initial refresh exited {code} (one or more sources failed). "
                    "Check scheduler logs."
                )
        except Exception:  # never let a bad run kill the loop
            log.exception("initial refresh failed")
            alerts.notify("vantage: initial refresh crashed. Check scheduler logs.")

    while True:
        wait = seconds_until(hour)
        log.info("sleeping %.0f min until next refresh", wait / 60)
        time.sleep(wait)
        log.info("starting daily refresh")
        try:
            code = refresh.main([])
            log.info("refresh finished with exit code %d", code)
            if code:
                alerts.notify(
                    f"vantage: daily refresh exited {code} (one or more sources failed). "
                    "Check scheduler logs."
                )
        except Exception:
            log.exception("daily refresh failed; will retry tomorrow")
            alerts.notify(
                "vantage: daily refresh crashed; will retry tomorrow. Check scheduler logs."
            )
        # Guard against a fast refresh re-triggering within the same hour.
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
