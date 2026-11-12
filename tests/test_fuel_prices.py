"""Ministry of Commerce fuel-price posts: parsing, saving, reader wiring and the ticker text.

The first post is the owner-provided public Ministry announcement; the others are made-up
variants in the same style. No private messages are used.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.config import Settings
from app.dashboard import ticker_segments
from app.database import PaymentStore
from app.exchange_rates import CAMBODIA_TIMEZONE, ExchangeRate
from app.fuel_prices import (
    FUEL_CHANNEL_ID,
    FuelPrices,
    fuel_period_khmer,
    fuel_period_text,
    fuel_post_counts,
    fuel_prices_are_stale,
    merge_with_previous,
    parse_fuel_post,
)
from app.rate_group_reader import TARGET_RATE_GROUP_ID, RateGroupReader

MINISTRY_POST = (
    "ថ្លៃលក់រាយប្រេងឥន្ធនៈនៅតាមស្ថានីយសម្រាប់ការអនុវត្តចាប់ពីវេលាម៉ោង ១ រសៀលថ្ងៃទី ១១ ខែវិច្ឆិកា ឆ្នាំ២០២៦ "
    "រហូតដល់ថ្ងៃទី ២១ ខែវិច្ឆិកា ឆ្នាំ២០២៦                                                                                                "
    "* សាំង = ៤ ៣៥០ រៀល (ចុះថ្លៃ៧០០រៀល)\n"
    "* ម៉ាស៊ូត = ៥ ៣០០ រៀល (ចុះថ្លៃ៣៥០ រៀល)"
)


def test_owner_sample_post_gives_prices_changes_and_period():
    prices = parse_fuel_post(MINISTRY_POST, 77, "2026-11-11T13:00:00+07:00")
    assert prices == FuelPrices(4350, 5300, -700, -350, "2026-11-11", "2026-11-21", 77, "2026-11-11T13:00:00+07:00")
    assert fuel_period_text(prices) == "11–21 Nov"


def test_rise_unchanged_western_digits_and_commas():
    post = (
        "ថ្លៃលក់រាយប្រេងឥន្ធនៈ ចាប់ពីថ្ងៃទី 1 ខែធ្នូ ឆ្នាំ2026 រហូតដល់ថ្ងៃទី 10 ខែធ្នូ ឆ្នាំ2026\n"
        "* សាំង = 4,450 រៀល (ឡើងថ្លៃ100រៀល)\n"
        "* ម៉ាស៊ូត = 5,300 រៀល (នៅដដែល)"
    )
    prices = parse_fuel_post(post)
    assert (prices.regular, prices.regular_change) == (4450, 100)
    assert (prices.diesel, prices.diesel_change) == (5300, 0)
    assert (prices.valid_from, prices.valid_to) == ("2026-12-01", "2026-12-10")


def test_other_posts_and_implausible_prices_are_ignored():
    assert parse_fuel_post("សេចក្តីជូនដំណឹងអំពីតម្លៃទំនិញ") is None
    assert parse_fuel_post(None) is None
    assert parse_fuel_post("ថ្លៃលក់រាយប្រេងឥន្ធនៈ\n* សាំង = ៤ ៣៥០ រៀល") is None  # diesel missing
    assert parse_fuel_post("ថ្លៃលក់រាយប្រេងឥន្ធនៈ\n* សាំង = ៤៣ រៀល\n* ម៉ាស៊ូត = ៥ ៣០០ រៀល") is None


def test_missing_change_is_filled_from_saved_price_and_older_posts_never_win():
    saved = FuelPrices(5050, 5650, message_id=10)
    newer = parse_fuel_post("ថ្លៃលក់រាយប្រេងឥន្ធនៈ\n* សាំង = ៤ ៣៥០ រៀល\n* ម៉ាស៊ូត = ៥ ៧០០ រៀល", 11)
    merged = merge_with_previous(newer, saved)
    assert (merged.regular_change, merged.diesel_change) == (-700, 50)
    assert merge_with_previous(FuelPrices(4000, 5000, message_id=9), saved) is None
    edited = FuelPrices(5000, 5600, -50, -50, message_id=10)
    assert merge_with_previous(edited, saved) == edited


def test_prices_turn_old_after_the_announced_period():
    prices = parse_fuel_post(MINISTRY_POST)
    assert not fuel_prices_are_stale(prices, date(2026, 11, 21))
    assert fuel_prices_are_stale(prices, date(2026, 11, 22))
    undated = FuelPrices(4350, 5300, posted_at="2026-11-11T13:00:00+07:00")
    assert not fuel_prices_are_stale(undated, date(2026, 11, 22))
    assert fuel_prices_are_stale(undated, date(2026, 11, 23))


def gold_rate(price="2418.60", previous="2405.10", fetched=None):
    return ExchangeRate(
        "GOLD", "XAU/USD spot", Decimal(price), None, None, "12 Nov 2026 09:00",
        fetched or datetime.now(CAMBODIA_TIMEZONE), previous_official_rate=Decimal(previous) if previous else None,
    )


def test_ticker_text_shows_totals_khmer_fuel_wording_and_gold():
    prices = parse_fuel_post(MINISTRY_POST)
    segments = ticker_segments({"count": 23, "KHR": "1250000", "USD": "340"}, prices, date(2026, 11, 12), gold_rate())
    text = "".join(piece for piece, _color in segments)
    assert text.startswith("TODAY  23 payments  ·  KHR 1,250,000  ·  USD 340.00")
    assert ("តម្លៃសាំងធម្មតា 4,350៛ ▼700  ·  តម្លៃប្រេងម៉ាស៊ូត 5,300៛ ▼350  ·  "
            "អនុវត្តចាប់ពីថ្ងៃទី 11 ដល់ 21 ខែវិច្ឆិកា ឆ្នាំ2026") in text
    assert "≈ $2,915.99 / ដំឡឹង ▲  ·  ≈ $291.60 / ជី ▲" in text
    colors = dict(segments)
    assert colors["KHR 1,250,000"] == "green" and colors["USD 340.00"] == "usd"  # different colours
    assert colors[" ▼700"] == "green" and colors["4,350៛"] == "amber"
    assert colors[" ▲"] == "red"  # gold uses the fuel colours: up is red
    assert colors[""] == "gold_icon" and colors[" ≈ $2,915.99"] == "gold_shadow"
    assert text.index("តម្លៃសាំងធម្មតា") < text.index("ដំឡឹង")  # totals → fuel → gold


def test_gold_down_is_green_and_rise_in_fuel_is_red():
    colors = dict(ticker_segments({}, FuelPrices(4450, 5300, 100, 0, "2026-12-01", "2026-12-10"), date(2026, 12, 2),
                                  gold_rate("2400", "2418.60")))
    assert colors[" ▲100"] == "red"
    assert colors[" ▼"] == "green"
    assert not any("▲" in piece or "▼" in piece for piece in colors if "5,300" in piece)


def test_ticker_marks_old_prices_and_waits_politely_without_any():
    prices = parse_fuel_post(MINISTRY_POST)
    old = ticker_segments({}, prices, date(2026, 11, 30))
    assert ("  · តម្លៃចាស់", "muted") in old
    assert all(color == "muted" for piece, color in old if "៛" in piece or "▼" in piece)
    waiting = "".join(piece for piece, _color in ticker_segments({}, None, date(2026, 11, 12)))
    assert "តម្លៃសាំងធម្មតា …  ·  តម្លៃប្រេងម៉ាស៊ូត …" in waiting
    assert "ដំឡឹង …  ·  ជី …" in waiting


def test_khmer_period_wording_uses_western_digits():
    assert fuel_period_khmer(FuelPrices(1, 1, valid_from="2026-10-26", valid_to="2026-11-05")) == (
        "អនុវត្តចាប់ពីថ្ងៃទី 26 ខែតុលា ដល់ថ្ងៃទី 5 ខែវិច្ឆិកា ឆ្នាំ2026"
    )
    assert fuel_period_khmer(FuelPrices(1, 1, valid_from="2026-11-11")) == "អនុវត្តចាប់ពីថ្ងៃទី 11 ខែវិច្ឆិកា ឆ្នាំ2026"


def test_store_keeps_only_the_latest_fuel_prices(tmp_path):
    store = PaymentStore(tmp_path / "state.sqlite3")
    try:
        assert store.load_fuel_prices() is None
        store.save_fuel_prices(FuelPrices(5050, 5650, message_id=10).as_dict())
        store.save_fuel_prices(parse_fuel_post(MINISTRY_POST, 11).as_dict())
        assert FuelPrices.from_dict(store.load_fuel_prices()) == parse_fuel_post(MINISTRY_POST, 11)
    finally:
        store.close()


def make_settings(tmp_path):
    return Settings(
        12345, "a" * 32, "+85510000000", tmp_path / "payment_user.session", (), None,
        "PayWayByABA_bot", True, tmp_path / "state.sqlite3", "voice", "+0%",
        rate_group_session_path=tmp_path / "rate_group_user.session",
    )


def message(message_id, text):
    return SimpleNamespace(id=message_id, message=text, date=datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc))


class FuelClient:
    def __init__(self, channel_messages, has_channel=True):
        self.channel_messages = channel_messages
        self.has_channel = has_channel
        self.handlers = []
        self.history_requests = []

    async def iter_dialogs(self):
        yield SimpleNamespace(id=TARGET_RATE_GROUP_ID, entity="group")
        if self.has_channel:
            yield SimpleNamespace(id=FUEL_CHANNEL_ID, entity="ministry")

    def add_event_handler(self, handler, event):
        self.handlers.append((handler, event))

    async def get_messages(self, entity, limit):
        self.history_requests.append((entity, limit))
        return self.channel_messages


def test_reader_publishes_newest_ministry_post_from_history_and_listens_for_more(tmp_path):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))
    client = FuelClient([message(80, "ថ្ងៃនេះ ក្រសួងពាណិជ្ជកម្ម ..."), message(79, MINISTRY_POST), message(60, MINISTRY_POST)])
    reader._client = client

    async def run():
        assert await reader._find_target_group() == "group"
        await reader._load_latest_fuel_post(client)

    asyncio.run(run())
    fuel_events = [value for name, value in events if name == "fuel_prices"]
    assert [value["message_id"] for value in fuel_events] == [79]
    assert fuel_events[0]["regular"] == 4350 and fuel_events[0]["posted_at"] == "2026-11-11T13:00:00+07:00"
    assert client.history_requests == [("ministry", 200)]
    assert len(client.handlers) == 2  # new and edited Ministry posts


def test_live_handler_reads_only_the_ministry_channel(tmp_path):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))
    asyncio.run(reader._handle_fuel_post(SimpleNamespace(chat_id=TARGET_RATE_GROUP_ID, message=message(5, MINISTRY_POST))))
    asyncio.run(reader._handle_fuel_post(SimpleNamespace(chat_id=FUEL_CHANNEL_ID, message=message(6, "ផ្សេងៗ"))))
    assert events == []
    asyncio.run(reader._handle_fuel_post(SimpleNamespace(chat_id=FUEL_CHANNEL_ID, message=message(7, MINISTRY_POST))))
    assert [name for name, _value in events] == ["fuel_prices"]


def test_missing_ministry_channel_does_not_stop_the_private_reader(tmp_path):
    reader = RateGroupReader(make_settings(tmp_path), lambda *_args: None)
    client = FuelClient([], has_channel=False)
    reader._client = client

    async def run():
        assert await reader._find_target_group() == "group"
        await reader._load_latest_fuel_post(client)

    asyncio.run(run())
    assert client.handlers == [] and client.history_requests == []


def test_spelling_variants_without_header_or_equals_sign_still_parse():
    prices = parse_fuel_post("តម្លៃប្រេងឥន្ធនះ\nសាំង ៤ ៣៥០ រៀល\nម៉ាស៊ុត ៥ ៣០០ រៀល")
    assert (prices.regular, prices.diesel) == (4350, 5300)
    assert (prices.regular_change, prices.diesel_change) == (None, None)


def test_post_counts_describe_structure_only():
    counts = fuel_post_counts([MINISTRY_POST, "ផ្សេងៗ", None, ""])
    assert counts == {
        "posts": 4, "with_text": 2, "fuel_word": 1, "regular_word": 1, "diesel_word": 1,
        "riel_word": 4, "equals": 2, "numbers": 6, "price_lines": 2,
    }


def test_marks_typed_in_another_order_still_match():
    # Same words as on screen, but with the vowel and sign marks stored in the opposite order.
    regular = "\u179f\u17c6\u17b6\u1784"          # ស + ំ + ា + ង   (usual: ស + ា + ំ + ង)
    diesel = "\u1798\u17b6\u17c9\u179f\u17bc\u17ca\u178f"  # ម + ា + ៉ + ស + ូ + ៊ + ត
    assert regular != "សាំង" and diesel != "ម៉ាស៊ូត"
    post = MINISTRY_POST.replace("សាំង", regular).replace("ម៉ាស៊ូត", diesel)
    prices = parse_fuel_post(post)
    assert (prices.regular, prices.regular_change, prices.diesel, prices.diesel_change) == (4350, -700, 5300, -350)
    assert (prices.valid_from, prices.valid_to) == ("2026-11-11", "2026-11-21")


def test_riel_sign_and_price_word_variants():
    prices = parse_fuel_post("ប្រេងឥន្ធនៈ\nតម្លៃប្រេងសាំងធម្មតា ៖ ៤ ៣៥០៛ (ឡើងតម្លៃ ៥០ រៀល)\nតម្លៃប្រេងម៉ាស៊ូត ៖ ៥ ៣០០៛")
    assert (prices.regular, prices.regular_change, prices.diesel, prices.diesel_change) == (4350, 50, 5300, None)
