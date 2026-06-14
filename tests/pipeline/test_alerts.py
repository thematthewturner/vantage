"""Offline tests for the webhook alerting helper (no real network)."""

import httpx

from vantage.pipeline import alerts


def test_notify_noop_when_webhook_unset(monkeypatch):
    monkeypatch.delenv(alerts.ENV_WEBHOOK, raising=False)
    sent = {}

    def _post(*args, **kwargs):  # should never be called
        sent["called"] = True
        raise AssertionError("must not post without a webhook")

    monkeypatch.setattr(httpx, "post", _post)
    assert alerts.notify("boom") is False
    assert "called" not in sent


def test_notify_posts_both_payload_keys(monkeypatch):
    monkeypatch.setenv(alerts.ENV_WEBHOOK, "https://hooks.example/abc")
    captured = {}

    class _Resp:
        def raise_for_status(self):
            return None

    def _post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(httpx, "post", _post)
    assert alerts.notify("daily refresh failed") is True
    assert captured["url"] == "https://hooks.example/abc"
    # One payload serves both Slack (text) and Discord (content).
    assert captured["json"]["text"] == "daily refresh failed"
    assert captured["json"]["content"] == "daily refresh failed"


def test_notify_swallows_errors(monkeypatch):
    monkeypatch.setenv(alerts.ENV_WEBHOOK, "https://hooks.example/abc")

    def _post(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", _post)
    # Must not raise -- alerting can never take down the refresh loop.
    assert alerts.notify("boom") is False
