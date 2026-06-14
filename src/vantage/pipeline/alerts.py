"""Optional failure alerting via an incoming webhook (Slack or Discord).

Set ``VANTAGE_ALERT_WEBHOOK`` to a Slack or Discord incoming-webhook URL and the
scheduler posts a short message when a refresh fails. With no webhook set,
alerting is a no-op. Alerting never raises: a broken webhook must not take down
the refresh loop.

One payload works for both providers -- Slack reads ``text``, Discord reads
``content`` and each ignores the other's key.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("vantage.alerts")

ENV_WEBHOOK = "VANTAGE_ALERT_WEBHOOK"


def notify(message: str, *, timeout: float = 10.0) -> bool:
    """Post ``message`` to the configured webhook. Returns True if delivered.

    Returns False (a no-op) when ``VANTAGE_ALERT_WEBHOOK`` is unset or the post
    fails -- the caller is the unattended scheduler, so this must never raise.
    """
    url = os.environ.get(ENV_WEBHOOK, "").strip()
    if not url:
        return False
    payload = {"text": message, "content": message}
    try:
        resp = httpx.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return True
    except Exception as exc:  # alerting must never crash the refresh loop
        log.warning("alert webhook failed: %s", exc)
        return False
