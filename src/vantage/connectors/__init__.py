"""Connectors package.

Importing it registers all built-in indicator connectors (FRED, ...). Equity
prices are handled by ``prices_yf`` as a standalone fetcher, not a registered
``Connector``, because they have a different shape.
"""

from vantage.connectors import fred  # noqa: F401  (side-effect: registers FRED)
from vantage.connectors.base import REGISTRY, Connector, register

__all__ = ["REGISTRY", "Connector", "register"]
