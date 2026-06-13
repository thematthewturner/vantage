import datetime as dt

from vantage.schema import Observation
from vantage.storage.readers import current_series, last_obs_date, series_as_known_on
from vantage.storage.writers import upsert_observations


def _obs(date, value, as_of):
    return Observation(source="FRED", series_id="X", date=date, value=value, as_of=as_of)


def test_migrations_create_tables(con):
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert {
        "series_meta",
        "observations",
        "securities",
        "prices",
        "index_values",
        "index_weights",
    } <= tables


def test_upsert_is_idempotent(con):
    obs = [_obs(dt.date(2020, 1, 1), 100.0, dt.date(2020, 1, 15))]
    upsert_observations(con, obs)
    upsert_observations(con, obs)  # second run must not duplicate
    n = con.execute("SELECT count(*) FROM observations").fetchone()[0]
    assert n == 1


def test_point_in_time_excludes_future_vintages(con):
    # Same period revised: first print 100 (knowable Jan 15), revised to 105 (Feb 15).
    upsert_observations(
        con,
        [
            _obs(dt.date(2020, 1, 1), 100.0, dt.date(2020, 1, 15)),
            _obs(dt.date(2020, 1, 1), 105.0, dt.date(2020, 2, 15)),
        ],
    )
    # As known on Jan 20, only the first vintage existed.
    pit = series_as_known_on(con, "FRED", "X", dt.date(2020, 1, 20))
    assert pit["value"].tolist() == [100.0]
    # Current best view takes the latest vintage.
    cur = current_series(con, "FRED", "X")
    assert cur["value"].tolist() == [105.0]


def test_last_obs_date(con):
    upsert_observations(
        con,
        [
            _obs(dt.date(2020, 1, 1), 1.0, dt.date(2020, 1, 1)),
            _obs(dt.date(2020, 3, 1), 2.0, dt.date(2020, 3, 1)),
        ],
    )
    assert last_obs_date(con, "FRED", "X") == dt.date(2020, 3, 1)
    assert last_obs_date(con, "FRED", "MISSING") is None
