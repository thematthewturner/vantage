import datetime as dt

from vantage.connectors.fred import FredConnector
from vantage.schema import Frequency, SeriesMeta


def test_normalize_parses_values_and_missing():
    meta = SeriesMeta(source="FRED", series_id="CPIMEDSL",
                      metric_name="CPI: Medical Care", frequency=Frequency.MONTHLY)
    raw = {"observations": [
        {"date": "2020-01-01", "value": "100.5"},
        {"date": "2020-02-01", "value": "."},      # FRED missing-value sentinel
        {"date": "2020-03-01", "value": "101.2"},
    ]}

    obs = FredConnector(api_key="dummy").normalize(raw, meta)

    assert [o.date for o in obs] == [dt.date(2020, 1, 1), dt.date(2020, 2, 1), dt.date(2020, 3, 1)]
    assert obs[0].value == 100.5
    assert obs[1].value is None          # "." -> None
    assert obs[2].value == 101.2
    assert all(o.source == "FRED" and o.series_id == "CPIMEDSL" for o in obs)
    assert all(o.meta.get("as_of_is_fetch") for o in obs)


def test_registry_contains_fred():
    from vantage.connectors import REGISTRY
    assert "FRED" in REGISTRY
