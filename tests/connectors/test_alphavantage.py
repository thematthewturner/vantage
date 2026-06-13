import datetime as dt

from vantage.connectors.alphavantage import AlphaVantageConnector
from vantage.schema import Frequency, SeriesMeta


def test_normalize_parses_intraday_rsi_points():
    meta = SeriesMeta(
        source="ALPHAVANTAGE",
        series_id="LLY_RSI_5MIN",
        metric_name="LLY 5min RSI(14)",
        frequency=Frequency.INTRADAY,
    )
    raw = {
        "Technical Analysis: RSI": {
            "2026-06-12 09:35": {"RSI": "63.4123"},
            "2026-06-12 09:30": {"RSI": "58.1000"},
        }
    }

    obs = AlphaVantageConnector(api_key="dummy").normalize(raw, meta)

    assert [o.meta["timestamp"] for o in obs] == ["2026-06-12 09:30", "2026-06-12 09:35"]
    assert [o.date for o in obs] == [dt.date(2026, 6, 12), dt.date(2026, 6, 12)]
    assert obs[0].value == 58.1
    assert obs[1].value == 63.4123
    assert all(o.source == "ALPHAVANTAGE" and o.series_id == "LLY_RSI_5MIN" for o in obs)
    assert all(o.meta.get("as_of_is_fetch") for o in obs)


def test_registry_contains_alphavantage():
    from vantage.connectors import REGISTRY

    assert "ALPHAVANTAGE" in REGISTRY
