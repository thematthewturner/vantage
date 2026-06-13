import datetime as dt

import pytest

from vantage.config import Settings
from vantage.storage.db import connect


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        db_path=tmp_path / "test.duckdb",
        raw_dir=tmp_path / "raw",
        index_base_value=100.0,
        index_base_date=dt.date(2020, 1, 1),
        index_baseline_start_date=dt.date(1998, 12, 22),
        rebalance="Q",
    )


@pytest.fixture
def con(settings):
    connection = connect(settings)
    yield connection
    connection.close()
