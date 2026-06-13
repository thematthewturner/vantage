"""Tests for the daily scheduler's wall-clock math."""

from __future__ import annotations

import datetime as dt

from vantage.pipeline import scheduler


def test_seconds_until_later_today():
    now = dt.datetime(2026, 6, 13, 1, 0, tzinfo=dt.UTC)
    assert scheduler.seconds_until(6, now=now) == 5 * 3600


def test_seconds_until_rolls_to_tomorrow():
    now = dt.datetime(2026, 6, 13, 8, 0, tzinfo=dt.UTC)
    # 06:00 already passed today -> next is 22h away.
    assert scheduler.seconds_until(6, now=now) == 22 * 3600


def test_seconds_until_exact_hour_rolls_forward():
    now = dt.datetime(2026, 6, 13, 6, 0, tzinfo=dt.UTC)
    # Exactly at the target -> schedule the next day, not zero.
    assert scheduler.seconds_until(6, now=now) == 24 * 3600


def test_refresh_hour_env(monkeypatch):
    monkeypatch.setenv("REFRESH_HOUR_UTC", "9")
    assert scheduler._refresh_hour() == 9
    monkeypatch.setenv("REFRESH_HOUR_UTC", "garbage")
    assert scheduler._refresh_hour() == 6
    monkeypatch.setenv("REFRESH_HOUR_UTC", "99")
    assert scheduler._refresh_hour() == 23
