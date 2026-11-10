from datetime import datetime
from decimal import Decimal
from urllib.error import URLError

import app.exchange_rates as exchange_rates
from app.database import PaymentStore
from app.exchange_rates import (
    CAMBODIA_TIMEZONE,
    ExchangeRate,
    ExchangeRateMonitor,
    format_rate_display_values,
    format_rate_row,
    format_rate_status,
    parse_acleda_page,
    parse_nbc_page,
    parse_wing_page,
    rate_from_record,
)


def test_nbc_page_parses_one_official_reference_rate():
    rate = parse_nbc_page(
        "<main>4 November 2026 | Official rate: 4,085 Riel / US Dollar</main>",
        datetime(2026, 11, 4, 16, 0, tzinfo=CAMBODIA_TIMEZONE),
    )

    assert rate.source == "NBC"
    assert rate.category == "Official reference rate"
    assert rate.official_rate == Decimal("4085")
    assert rate.buy_rate is None
    assert rate.sell_rate is None
    assert rate.effective_at == "4 November 2026"


def test_acleda_page_parses_notes_buy_sell_and_effective_time():
    rate = parse_acleda_page(
        """
        <main>
          The Exchange Rate as of November 4, 2026 4:15 PM
          <nav>NOTES AC SUPER APP TELEGRAPHIC TRANSFER OVERSEAS TAX</nav>
          <table>
            <tr><th>Currency</th><th>Buy</th><th>Sell</th></tr>
            <tr><td>USD / KHR</td><td>4,081 KHR</td><td>4,095 KHR</td></tr>
          </table>
        </main>
        """,
        datetime(2026, 11, 4, 16, 20, tzinfo=CAMBODIA_TIMEZONE),
    )

    assert rate.category == "Notes"
    assert rate.official_rate is None
    assert rate.buy_rate == Decimal("4081")
    assert rate.sell_rate == Decimal("4095")
    assert rate.effective_at == "November 4, 2026 4:15 PM"


def test_wing_page_parses_telegraphic_transfer_outbound_buy_sell():
    rate = parse_wing_page(
        """
        <main>
          Telegraphic Transfer Outbound Rate
          <table>
            <tr><th>Currency Pair</th><th>Bank Buy Bid: 1 USD</th><th>Bank Sell Ask: 1 USD</th></tr>
            <tr><td>Cambodian Riel USD/KHR</td><td>USD/KHR</td><td>4083</td><td>4093</td></tr>
          </table>
          As of 04 Nov 2026
        </main>
        """,
        datetime(2026, 11, 4, 16, 25, tzinfo=CAMBODIA_TIMEZONE),
    )

    assert rate.category == "Telegraphic Transfer Outbound"
    assert rate.buy_rate == Decimal("4083")
    assert rate.sell_rate == Decimal("4093")
    assert rate.effective_at == "04 Nov 2026"


def test_cached_rates_are_retained_but_marked_stale_after_source_error(tmp_path):
    store = PaymentStore(tmp_path / "rates.sqlite3")
    now = datetime(2026, 11, 4, 16, 15, tzinfo=CAMBODIA_TIMEZONE)
    store.save_exchange_rate(ExchangeRate(
        "ACLEDA", "Notes", None, Decimal("4081"), Decimal("4095"),
        "November 4, 2026 4:15 PM", now,
    ))
    store.mark_exchange_rate_error("ACLEDA", "Notes", "HTTP 503")
    rate = rate_from_record(store.load_exchange_rates()[0])

    row = format_rate_row("ACLEDA", rate, now)
    assert "B 4,081 / S 4,095 KHR/USD" in row
    assert "STALE" in row
    assert "source issue" in format_rate_status({"ACLEDA": rate}, now)

    store.close()


def test_rates_without_cached_values_are_explicitly_unavailable():
    rate = ExchangeRate("NBC", "Official reference rate", None, None, None, "", None, "HTTP 403")

    assert format_rate_row("NBC", rate, datetime(2026, 11, 4, tzinfo=CAMBODIA_TIMEZONE)) == (
        "NBC OFFICIAL\nUNAVAILABLE"
    )


def test_rate_card_format_preserves_source_categories_and_compact_effective_times():
    fetched = datetime(2026, 11, 4, 16, 20, tzinfo=CAMBODIA_TIMEZONE)
    nbc = ExchangeRate(
        "NBC",
        "Official reference rate",
        Decimal("4085"),
        None,
        None,
        "4 November 2026",
        fetched,
    )
    acleda = ExchangeRate(
        "ACLEDA",
        "Notes",
        None,
        Decimal("4081"),
        Decimal("4095"),
        "November 4, 2026 4:15 PM",
        fetched,
    )

    assert format_rate_display_values("NBC", nbc, fetched) == ("4,085", "", "", "4 Nov")
    assert format_rate_display_values("ACLEDA", acleda, fetched) == (
        "",
        "4,081",
        "4,095",
        "4 Nov 16:15",
    )


def test_rate_card_marks_old_or_unavailable_values_explicitly():
    now = datetime(2026, 11, 6, 16, 0, tzinfo=CAMBODIA_TIMEZONE)
    stale = ExchangeRate(
        "WING",
        "Telegraphic Transfer Outbound",
        None,
        Decimal("4083"),
        Decimal("4093"),
        "04 Nov 2026",
        datetime(2026, 11, 4, 16, 0, tzinfo=CAMBODIA_TIMEZONE),
    )

    assert format_rate_display_values("WING", stale, now) == (
        "",
        "4,083",
        "4,093",
        "4 Nov · STALE",
    )
    assert format_rate_display_values("NBC", None, now) == ("UNAVAILABLE", "", "", "")


def test_rate_status_age_refreshes_without_refetching():
    fetched = datetime(2026, 11, 4, 16, 0, tzinfo=CAMBODIA_TIMEZONE)
    rate = ExchangeRate("NBC", "Official reference rate", Decimal("4085"), None, None, "4 November 2026", fetched)

    assert "checked less than 1m ago" in format_rate_status({"NBC": rate}, fetched)
    assert "checked 2m ago" in format_rate_status(
        {"NBC": rate}, datetime(2026, 11, 4, 16, 2, tzinfo=CAMBODIA_TIMEZONE)
    )


def test_schedule_claim_is_durable_and_rate_error_preserves_cache(tmp_path):
    database = tmp_path / "state.sqlite3"
    store = PaymentStore(database)
    rate = ExchangeRate(
        "NBC", "Official reference rate", Decimal("4085"), None, None,
        "4 November 2026", datetime(2026, 11, 4, 16, 0, tzinfo=CAMBODIA_TIMEZONE),
    )
    store.save_exchange_rate(rate)
    assert store.claim_scheduled_announcement("2026-11-04", "16:10")
    assert not store.claim_scheduled_announcement("2026-11-04", "16:10")
    store.close()

    reopened = PaymentStore(database)
    assert not reopened.claim_scheduled_announcement("2026-11-04", "16:10")
    assert reopened.claim_scheduled_announcement("2026-11-05", "16:05")
    reopened.mark_exchange_rate_error("NBC", "Official reference rate", "HTTP 403")
    cached = rate_from_record(reopened.load_exchange_rates()[0])
    assert cached.official_rate == Decimal("4085")
    assert cached.last_error == "HTTP 403"
    reopened.close()


def test_refresh_failure_publishes_cached_value_as_stale(tmp_path, monkeypatch):
    store = PaymentStore(tmp_path / "rates.sqlite3")
    now = datetime(2026, 11, 4, 16, 0, tzinfo=CAMBODIA_TIMEZONE)
    store.save_exchange_rate(ExchangeRate(
        "NBC", "Official reference rate", Decimal("4085"), None, None, "4 November 2026", now,
    ))

    def fetch(source):
        if source.key == "NBC":
            raise URLError("temporary network failure")
        return ExchangeRate(source.key, source.category, Decimal("4081"), None, None, "4 November 2026", now)

    monkeypatch.setattr(exchange_rates, "fetch_rate", fetch)
    published = []
    monitor = ExchangeRateMonitor(store, published.append)
    result = monitor.refresh_once()

    assert result["NBC"].official_rate == Decimal("4085")
    assert result["NBC"].last_error
    assert "STALE" in format_rate_row("NBC", result["NBC"], now)
    assert published == [result]
    store.close()


def test_cache_keeps_previous_different_values_for_trend_arrows(tmp_path):
    database = tmp_path / "rates.sqlite3"
    store = PaymentStore(database)
    fetched = datetime(2026, 11, 7, 9, 0)

    def save(official=None, buy=None, sell=None, source="ACLEDA"):
        store.save_exchange_rate(ExchangeRate(
            source, "Notes", official, buy, sell, "November 7, 2026 9:00 AM", fetched,
        ))

    save(buy=Decimal("4081"), sell=Decimal("4095"))
    first = exchange_rates.load_rate_rows(store)["ACLEDA"]
    assert (first.previous_buy_rate, first.previous_sell_rate) == (None, None)
    assert first.trend("buy") is None

    save(buy=Decimal("4083"), sell=Decimal("4095"))
    second = exchange_rates.load_rate_rows(store)["ACLEDA"]
    assert second.previous_buy_rate == Decimal("4081")
    assert second.previous_sell_rate is None
    assert (second.trend("buy"), second.trend("sell")) == ("up", None)

    save(buy=Decimal("4083"), sell=Decimal("4094"))
    store.mark_exchange_rate_error("ACLEDA", "Notes", "timeout")
    store.close()
    reopened = PaymentStore(database)
    third = exchange_rates.load_rate_rows(reopened)["ACLEDA"]
    assert third.previous_buy_rate == Decimal("4081")
    assert third.previous_sell_rate == Decimal("4095")
    assert (third.trend("buy"), third.trend("sell")) == ("up", "down")
    reopened.close()


def test_rate_trend_compares_current_with_previous():
    assert exchange_rates.rate_trend(Decimal("4085"), Decimal("4083")) == "up"
    assert exchange_rates.rate_trend(Decimal("4081"), Decimal("4083")) == "down"
    assert exchange_rates.rate_trend(Decimal("4081"), Decimal("4081")) is None
    assert exchange_rates.rate_trend(None, Decimal("4081")) is None
    assert exchange_rates.rate_trend(Decimal("4081"), None) is None
