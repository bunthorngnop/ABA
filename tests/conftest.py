"""Shared test safety: no test may reach the live USD/CNY (CFETS) service.

ExchangeRateMonitor.refresh_once() also fetches the official USD/CNY rate. Tests that exercise the
monitor patch fetch_rate for the bank pages; this keeps the CNY fetch offline too, unless a test
replaces it with its own fake.
"""

from urllib.error import URLError

import pytest


@pytest.fixture(autouse=True)
def _offline_cny_parity(monkeypatch):
    def offline(*_args, **_kwargs):
        raise URLError("live USD/CNY fetch is disabled in tests")

    monkeypatch.setattr("app.exchange_rates.fetch_cny_parity", offline)
