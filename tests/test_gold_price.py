import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError

import pytest

import app.exchange_rates as exchange_rates
from app.config import load_settings
from app.database import PaymentStore
from app.exchange_rates import (
    CAMBODIA_TIMEZONE,
    ExchangeRate,
    ExchangeRateMonitor,
    gold_local_units,
    gold_refresh_due,
    load_rate_rows,
    parse_gold_response,
)

SAMPLE = {
    "timestamp": 1794034800,
    "metal": "XAU",
    "currency": "USD",
    "price": 2418.6,
    "change": 13.5,
    "bid": 2418.3,
    "ask": 2418.9,
}


def test_gold_response_is_parsed_as_usd_per_ounce_with_cambodia_time():
    rate = parse_gold_response(json.dumps(SAMPLE).encode())
    assert rate.source == "GOLD"
    assert rate.official_rate == Decimal("2418.60")
    assert (rate.buy_rate, rate.sell_rate) == (None, None)
    assert rate.effective_at == datetime.fromtimestamp(SAMPLE["timestamp"], CAMBODIA_TIMEZONE).strftime("%d %b %Y %H:%M")


@pytest.mark.parametrize("payload", [
    {"metal": "XAG", "currency": "USD", "price": 30},
    {"metal": "XAU", "currency": "EUR", "price": 2000},
    {"metal": "XAU", "currency": "USD"},
    {"metal": "XAU", "currency": "USD", "price": -1},
    {"metal": "XAU", "currency": "USD", "price": "not-a-number"},
    ["not", "an", "object"],
])
def test_invalid_gold_responses_are_rejected(payload):
    with pytest.raises(ValueError):
        parse_gold_response(json.dumps(payload).encode())


def test_gold_local_units_convert_exactly_from_troy_ounce():
    assert gold_local_units(Decimal("2418.60")) == (Decimal("2915.99"), Decimal("291.60"))
    assert gold_local_units(Decimal("31.1034768")) == (Decimal("37.50"), Decimal("3.75"))


def test_gold_refreshes_at_most_every_twelve_hours():
    now = datetime(2026, 11, 7, 12, 0, tzinfo=CAMBODIA_TIMEZONE)
    cached = ExchangeRate("GOLD", "XAU/USD spot", Decimal("2400"), None, None, "", now - timedelta(hours=11, minutes=59))
    assert gold_refresh_due(None, now)
    assert not gold_refresh_due(cached, now)
    assert gold_refresh_due(
        ExchangeRate("GOLD", "XAU/USD spot", Decimal("2400"), None, None, "", now - timedelta(hours=12)), now,
    )
    assert gold_refresh_due(ExchangeRate("GOLD", "XAU/USD spot", None, None, None, "", None), now)


def _no_bank_fetches(monkeypatch):
    def unavailable(source, timeout=5):
        raise URLError("offline in tests")

    monkeypatch.setattr(exchange_rates, "fetch_rate", unavailable)


def test_monitor_uses_free_quota_sparingly_and_never_logs_the_key(tmp_path, monkeypatch, caplog):
    _no_bank_fetches(monkeypatch)
    calls = []
    key = "private-gold-key-123"
    clock = {"now": datetime(2026, 11, 7, 9, 0, tzinfo=CAMBODIA_TIMEZONE)}

    def fake_fetch(api_key, timeout=5):
        calls.append(api_key)
        if len(calls) == 2:
            raise HTTPError("https://www.goldapi.io/api/price/XAU/USD", 429, "Too Many Requests", None, None)
        price = Decimal("2418.60") if len(calls) == 1 else Decimal("2425.00")
        return ExchangeRate("GOLD", "XAU/USD spot", price, None, None, "07 Nov 2026 09:00", clock["now"])

    monkeypatch.setattr(exchange_rates, "fetch_gold_price", fake_fetch)
    store = PaymentStore(tmp_path / "rates.sqlite3")
    published = []
    monitor = ExchangeRateMonitor(store, published.append, gold_api_key=key, clock=lambda: clock["now"])
    caplog.set_level(logging.INFO)

    monitor.refresh_once()
    assert len(calls) == 1
    assert published[-1]["GOLD"].official_rate == Decimal("2418.60")
    monitor.refresh_once()
    clock["now"] += timedelta(hours=11)
    monitor.refresh_once()
    assert len(calls) == 1

    clock["now"] += timedelta(hours=1)
    monitor.refresh_once()
    assert len(calls) == 2
    assert load_rate_rows(store)["GOLD"].official_rate == Decimal("2418.60")
    clock["now"] += timedelta(minutes=30)
    monitor.refresh_once()
    assert len(calls) == 2

    clock["now"] += timedelta(minutes=31)
    monitor.refresh_once()
    assert len(calls) == 3
    gold = load_rate_rows(store)["GOLD"]
    assert gold.official_rate == Decimal("2425.00")
    assert gold.previous_official_rate == Decimal("2418.60")
    assert gold.trend("official") == "up"
    assert key not in caplog.text
    assert "HTTP 429" in caplog.text
    store.close()


def test_monitor_without_key_never_requests_gold(tmp_path, monkeypatch):
    _no_bank_fetches(monkeypatch)
    calls = []
    monkeypatch.setattr(exchange_rates, "fetch_gold_price", lambda *args, **kwargs: calls.append(args))
    store = PaymentStore(tmp_path / "rates.sqlite3")
    ExchangeRateMonitor(store, lambda rates: None).refresh_once()
    assert calls == []
    assert "GOLD" not in load_rate_rows(store)
    store.close()


def test_gold_key_is_sent_only_as_a_header(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return json.dumps(SAMPLE).encode()

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        return Response()

    monkeypatch.setattr(exchange_rates, "urlopen", fake_urlopen)
    rate = exchange_rates.fetch_gold_price("secret-key")
    assert rate.official_rate == Decimal("2418.60")
    assert "secret-key" not in captured["url"]
    assert captured["headers"].get("X-access-token") == "secret-key"


def test_nbc_daily_history_keeps_one_public_value_per_day(tmp_path):
    store = PaymentStore(tmp_path / "rates.sqlite3")
    start = datetime(2026, 11, 1, 9, 0, tzinfo=CAMBODIA_TIMEZONE)
    for day, value in enumerate(("4079", "4081", "4080", "4082", "4084", "4083", "4085", "4086")):
        store.save_exchange_rate(ExchangeRate(
            "NBC", "Official reference rate", Decimal(value), None, None, "", start + timedelta(days=day),
        ))
    store.save_exchange_rate(ExchangeRate(
        "NBC", "Official reference rate", Decimal("4087"), None, None, "", start + timedelta(days=7, hours=2),
    ))
    store.save_exchange_rate(ExchangeRate(
        "ACLEDA", "Notes", None, Decimal("4081"), Decimal("4095"), "", start,
    ))
    assert store.load_nbc_history(7) == [Decimal(value) for value in ("4081", "4080", "4082", "4084", "4083", "4085", "4087")]
    store.close()


def test_gold_api_key_is_loaded_from_private_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GOLD_API_KEY= example-key \n", encoding="utf-8")
    monkeypatch.delenv("GOLD_API_KEY", raising=False)
    assert load_settings(str(env)).gold_api_key == "example-key"
    monkeypatch.delenv("GOLD_API_KEY", raising=False)


def test_nbc_weekend_without_new_rate_keeps_last_published_rate_current(tmp_path, monkeypatch):
    store = PaymentStore(tmp_path / "rates.sqlite3")
    friday = datetime(2026, 11, 6, 9, 0, tzinfo=CAMBODIA_TIMEZONE)
    store.save_exchange_rate(ExchangeRate(
        "NBC", "Official reference rate", Decimal("4085"), None, None, "6 November 2026", friday,
    ))
    store.mark_exchange_rate_error("NBC", "Official reference rate", "earlier failure")

    def weekend_fetch(source, timeout=5):
        if source.key == "NBC":
            raise ValueError(exchange_rates.NBC_NOT_PUBLISHED_MESSAGE)
        raise URLError("offline in tests")

    monkeypatch.setattr(exchange_rates, "fetch_rate", weekend_fetch)
    ExchangeRateMonitor(store, lambda rates: None).refresh_once()
    nbc = load_rate_rows(store)["NBC"]
    assert nbc.last_error is None
    assert nbc.official_rate == Decimal("4085")
    assert not nbc.is_stale(friday + timedelta(days=3))
    assert nbc.is_stale(friday + timedelta(days=4, minutes=1))
    store.close()


def test_other_nbc_parse_errors_and_bank_rates_still_mark_errors(tmp_path, monkeypatch):
    store = PaymentStore(tmp_path / "rates.sqlite3")

    def broken(source, timeout=5):
        raise ValueError("unexpected page")

    monkeypatch.setattr(exchange_rates, "fetch_rate", broken)
    ExchangeRateMonitor(store, lambda rates: None).refresh_once()
    rows = load_rate_rows(store)
    assert rows["NBC"].last_error == "unexpected page"
    assert rows["ACLEDA"].last_error == "unexpected page"
    fetched = datetime(2026, 11, 6, 9, 0, tzinfo=CAMBODIA_TIMEZONE)
    acleda = ExchangeRate("ACLEDA", "Notes", None, Decimal("4081"), Decimal("4095"), "", fetched)
    assert acleda.is_stale(fetched + timedelta(hours=25))
    store.close()
