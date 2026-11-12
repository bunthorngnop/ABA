from datetime import datetime, timedelta, timezone
from decimal import Decimal
import tkinter as tk
import tkinter.font as tkfont

import pytest

from app.dashboard import (
    COLORS,
    Dashboard,
    GOLD_UNIT_NAMES,
    RATE_BEST_OUTLINE,
    RATE_PULSE_INTERVAL_MS,
    RATE_PULSE_STEPS,
    RATE_GROUP_DIRECTION_COLORS,
    RATE_GROUP_GLOW_COLOR,
    RATE_GROUP_ROW_COLORS,
    RATE_ROW_COLORS,
    RATE_TABLE_HEADER_BG,
    RATE_TREND_COLORS,
    amount_color,
    announcement_label,
    best_bank_rates,
    cambodia_flag_image,
    component_health,
    format_payment_amount,
    latest_rate_group_posts,
    narrow_header_mode,
    order_rate_group_posts,
    preferred_secondary_monitor,
    rate_gap_text,
    rate_group_sender_trends,
    rate_group_status_dot_color,
    rate_group_status_label,
    rate_group_summary_text,
    rate_pulse_color,
    rate_pulse_progress,
    responsive_layout_mode,
    today_strip_text,
)
from app.exchange_rates import CAMBODIA_TIMEZONE, ExchangeRate
from app.rate_post_format import KHR_TO_USD, USD_TO_KHR


def test_khr_and_usd_amounts_have_large_display_format():
    assert format_payment_amount("50000", "KHR") == "៛ 50,000"
    assert format_payment_amount("5", "USD") == "$ 5.00"


def test_unknown_currency_or_amount_is_not_invented():
    assert format_payment_amount("5", "EUR") == "—"
    assert format_payment_amount("not-a-number", "USD") == "—"


def test_khr_and_usd_amounts_have_distinct_theme_colors():
    assert amount_color("KHR") == "green"
    assert amount_color("USD") == "usd"
    assert amount_color("EUR") == "muted"


def test_long_sender_name_is_not_truncated_or_replaced_by_display_formatter():
    long_name = "SOK DARA WITH A VERY LONG VERIFIED CUSTOMER NAME"
    # Sender data is placed in a wrapping label as-is; only amounts are formatted.
    assert str(long_name) == long_name


def test_responsive_layout_modes_protect_short_displays():
    assert responsive_layout_mode(900) == "normal"
    assert responsive_layout_mode(720) == "compact"
    assert responsive_layout_mode(600) == "short"


def test_narrow_header_compacts_clock_title_and_rate_box():
    assert narrow_header_mode(900)
    assert narrow_header_mode(1079)
    assert not narrow_header_mode(1080)


def _group_message(message_id, sender, minutes_ago, text, now=None):
    posted = (now or datetime.now(timezone.utc)) - timedelta(minutes=minutes_ago)
    return {
        "id": message_id,
        "sender": sender,
        "posted_at": posted.strftime("%H:%M"),
        "timestamp": posted.isoformat(),
        "text": text,
    }


def _rates(fetched_at=None, nbc_previous=None, acleda_previous_buy=None, gold_previous=None, cny_previous=None):
    fetched_at = fetched_at or datetime.now(CAMBODIA_TIMEZONE)
    return {
        "NBC": ExchangeRate(
            "NBC", "Official reference rate", Decimal("4085"), None, None,
            "7 November 2026", fetched_at, previous_official_rate=nbc_previous,
        ),
        "ACLEDA": ExchangeRate(
            "ACLEDA", "Notes", None, Decimal("4081"), Decimal("4095"),
            "November 7, 2026 4:15 PM", fetched_at, previous_buy_rate=acleda_previous_buy,
        ),
        "WING": ExchangeRate(
            "WING", "Telegraphic Transfer Outbound", None, Decimal("4083"), Decimal("4093"),
            "07 Nov 2026", fetched_at,
        ),
        "GOLD": ExchangeRate(
            "GOLD", "XAU/USD spot", Decimal("2418.60"), None, None,
            "07 Nov 2026 14:05", fetched_at, previous_official_rate=gold_previous,
        ),
        "CNY": ExchangeRate(
            "CNY", "PBOC central parity", Decimal("6.7174"), None, None,
            "12 November 2026", fetched_at, previous_official_rate=cny_previous,
        ),
    }


def test_private_reader_keeps_latest_post_per_sender_newest_first():
    messages = [
        _group_message(1, " Dara ", 9, "old"),
        _group_message(2, "Sok", 8, "sok"),
        _group_message(3, "Dara", 7, "repost"),
        _group_message(4, "Vanna", 1, "newest"),
    ]
    assert [message["text"] for message in latest_rate_group_posts(messages)] == [
        "newest",
        "repost",
        "sok",
    ]
    assert latest_rate_group_posts([]) == []


def test_posts_older_than_an_hour_move_to_the_bottom():
    now = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)
    posts = [
        _group_message(1, "Old", 61, "old", now),
        _group_message(2, "Fresh", 2, "fresh", now),
        _group_message(3, "Faded", 20, "faded", now),
    ]
    ordered = order_rate_group_posts(latest_rate_group_posts(posts), now)
    assert [post["text"] for post in ordered] == ["fresh", "faded", "old"]


def test_private_reader_summary_uses_recent_tagged_rates_only():
    now = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
    messages = [
        _group_message(1, "Dara", 2, "ខ្មែរ AC ដូរ $ 4089\n$ ABA ដូរខ្មែរ 4090,5", now),
        _group_message(2, "Sok", 5, "មានខ្មែរ KB 20,000$*4089.25", now),
        _group_message(3, "Vanna", 40, "ខ្មែរ AC ដូរ $ 4070", now),
        _group_message(4, "Lina", 3, "ABA 4095", now),
    ]
    assert rate_group_summary_text(messages, now) == {
        KHR_TO_USD: "KHR→USD  4089 – 4089.25 KHR",
        USD_TO_KHR: "USD→KHR  4090.5 KHR",
    }
    assert rate_group_summary_text([], now) == {KHR_TO_USD: "KHR→USD  —", USD_TO_KHR: "USD→KHR  —"}


def test_sender_trends_compare_with_the_senders_previous_different_rate():
    messages = [
        _group_message(1, "Dara", 9, "ខ្មែរ AC ដូរ $ 4088"),
        _group_message(2, "Dara", 7, "ខ្មែរ AC ដូរ $ 4089\n\n$ AC ដូរខ្មែរ 4091"),
        _group_message(3, "Dara", 5, "ខ្មែរ AC ដូរ $ 4089\n\n$ AC ដូរខ្មែរ 4090.5"),
        _group_message(4, "Sok", 3, "ខ្មែរ KB ដូរ $ 4090"),
    ]
    trends = rate_group_sender_trends(messages)
    assert trends["dara"][KHR_TO_USD] == (Decimal("4089"), Decimal("4088"))
    assert trends["dara"][USD_TO_KHR] == (Decimal("4090.5"), Decimal("4091"))
    assert trends["sok"][KHR_TO_USD] == (Decimal("4090"), None)


def test_gap_to_nbc_best_bank_rates_and_today_strip():
    assert rate_gap_text(Decimal("4090"), Decimal("4085")) == "+5"
    assert rate_gap_text(Decimal("4083.5"), Decimal("4085")) == "−1.5"
    assert rate_gap_text(Decimal("4085"), Decimal("4085")) == "±0"
    assert rate_gap_text(Decimal("4085"), None) == ""
    now = datetime.now(CAMBODIA_TIMEZONE)
    assert best_bank_rates(_rates(now), now) == ({"WING"}, {"WING"})
    stale = _rates(now - timedelta(days=2))
    assert best_bank_rates(stale, now) == (set(), set())
    assert today_strip_text({"count": 23, "KHR": "1250000", "USD": "340"}) == (
        "Today 23 payments · KHR 1,250,000 · USD 340.00"
    )
    assert today_strip_text({"count": 1, "KHR": "0", "USD": "0.00"}) == "Today 1 payment · KHR 0 · USD 0.00"


def test_private_reader_status_labels_remain_compact():
    assert rate_group_status_label("CONNECTED · PRIVATE GROUP") == "CONNECTED"
    assert rate_group_status_label("ERROR · GROUP NOT AVAILABLE") == "GROUP UNAVAILABLE"
    colors = {
        label: rate_group_status_dot_color(label)
        for label in ("CONNECTED", "CONNECTING", "DISCONNECTED", "ERROR")
    }
    assert len(set(colors.values())) == 4


def test_rate_pulse_colors_remain_subtle_and_smooth():
    assert RATE_PULSE_INTERVAL_MS == 100
    assert RATE_PULSE_STEPS == 24
    assert rate_pulse_progress(0) == 0
    assert rate_pulse_progress(12) == 1
    assert rate_pulse_progress(24) == 0
    assert rate_pulse_color("#FB7185", "#FFB7C0", 0) == "#FB7185"
    assert rate_pulse_color("#FB7185", "#FFB7C0", 1) == "#FFB7C0"
    assert rate_pulse_color("#5DA9FF", "#B8E7FF", 1) == "#B8E7FF"
    assert rate_pulse_color("#F8FAFC", "#B9E8FF", 0.5) == "#D8F1FE"
    for base, highlight in (("#FB7185", "#FFB7C0"), ("#5DA9FF", "#B8E7FF")):
        for color in (rate_pulse_color(base, highlight, step / 24) for step in range(25)):
            red, green, blue = (int(color[index:index + 2], 16) for index in (1, 3, 5))
            assert red > green if base == "#FB7185" else blue > red


def _make_dashboard(**kwargs):
    try:
        dashboard = Dashboard(lambda _text: None, lambda _muted: None, lambda: 0, **kwargs)
    except tk.TclError as exc:
        pytest.skip(f"Tk is unavailable: {exc}")
    dashboard._place_startup_window = lambda *_args, **_kwargs: None
    return dashboard


def _layout(dashboard, geometry):
    dashboard.root.geometry(geometry)
    for _ in range(2):
        dashboard.root.update()
        dashboard._apply_responsive_layout()
        dashboard.root.update_idletasks()
    dashboard._update_dashboard_scrollregion()
    dashboard.root.update_idletasks()


def test_rates_table_with_official_cny_row_and_nbc_glass_card_show_figures_and_arrows():
    now = datetime.now(CAMBODIA_TIMEZONE)
    history = [Decimal(value) for value in ("4079", "4081", "4080", "4083", "4085")]
    dashboard = _make_dashboard(
        initial_exchange_rates=_rates(
            now, nbc_previous=Decimal("4083"), acleda_previous_buy=Decimal("4083"), gold_previous=Decimal("2405.10"),
            cny_previous=Decimal("6.7157"),
        ),
        nbc_history=lambda days=7: history,
    )
    try:
        _layout(dashboard, "1382x744")
        assert dashboard.rate_title_label.cget("text").replace("\n", " ") == "អត្រាប្តូរប្រាក់ រៀល ដុល្លារ និងយ័ន (ចិន)"
        assert [dashboard.rate_table_headers[column].cget("text") for column in range(3)] == ["BANK", "ទិញ $", "លក់ $"]
        assert list(dashboard.rate_display_labels) == ["ACLEDA", "WING", "CNY"]
        labels = dashboard.rate_display_labels
        assert (labels["ACLEDA"]["buy"].cget("text"), labels["ACLEDA"]["sell"].cget("text")) == ("4,081", "4,095")
        assert (labels["WING"]["buy"].cget("text"), labels["WING"]["sell"].cget("text")) == ("4,083", "4,093")
        cny = labels["CNY"]
        assert cny["bank"].cget("text") == "USD/CNY"
        assert (cny["official"].cget("text"), cny["unit"].cget("text")) == ("6.7174", "¥")
        assert int(cny["official_cell"].grid_info()["columnspan"]) == 2  # one midpoint across ទិញ and លក់
        assert cny["caption"].cget("text") == "PBOC central rate · 12 Nov"
        assert cny["official_arrow"].cget("text") == "▲"
        assert cny["official_arrow"].cget("fg") == RATE_TREND_COLORS["up"]
        assert str(cny["category"].cget("image"))  # the supplied logo, like the bank rows
        cny_font = tkfont.Font(root=dashboard.root, font=cny["official"].cget("font"))
        bank_font = tkfont.Font(root=dashboard.root, font=labels["ACLEDA"]["buy"].cget("font"))
        assert (cny_font.cget("size"), cny_font.cget("family")) == (bank_font.cget("size"), bank_font.cget("family"))
        unit_font = tkfont.Font(root=dashboard.root, font=cny["unit"].cget("font"))
        assert unit_font.cget("size") < cny_font.cget("size")  # small yuan sign
        assert labels["ACLEDA"]["buy_arrow"].cget("text") == "▼"
        assert labels["ACLEDA"]["buy_arrow"].cget("fg") == RATE_TREND_COLORS["down"]
        # Unchanged figures show no arrow (never both ▲ and ▼); no cell is outlined.
        assert labels["WING"]["buy_arrow"].cget("text") == ""
        for source in ("ACLEDA", "WING"):
            for field in ("buy", "sell"):
                assert labels[source][f"{field}_cell"].cget("highlightbackground") == RATE_ROW_COLORS[source]
            assert labels[source]["bank"].cget("anchor") == "center"
            assert labels[source]["bank"].pack_info()["anchor"] == "center"
        for source, source_labels in labels.items():
            assert source_labels["row"].cget("bg") == RATE_ROW_COLORS[source]
        figure_font = tkfont.Font(root=dashboard.root, font=labels["ACLEDA"]["buy"].cget("font"))
        assert (figure_font.cget("size"), figure_font.cget("family")) == (18, dashboard.figure_font)
        assert "KHR per USD" in dashboard.rate_age_label.cget("text")
        assert dashboard.nbc_card.master is dashboard.header
        assert isinstance(dashboard.nbc_card, tk.Canvas)
        assert dashboard.nbc_text("figure") == "4,085"
        assert dashboard.nbc_text("caption") == "អត្រាប្តូរប្រាក់ធនាគារជាតិ"
        canvas = dashboard.nbc_canvas
        caption_item = canvas.find_withtag("nbc_caption")[0]
        date_item = canvas.find_withtag("nbc_date")[0]
        assert canvas.itemcget(caption_item, "fill") == canvas.itemcget(date_item, "fill")
        assert dashboard.nbc_text("riel") == "៛"
        figure_item = canvas.find_withtag("nbc_figure")[0]
        assert canvas.itemcget(figure_item, "fill") == RATE_TREND_COLORS["up"]
        assert canvas.itemcget(canvas.find_withtag("nbc_riel")[0], "fill") == RATE_TREND_COLORS["up"]
        figure_box = canvas.bbox(canvas.find_withtag("nbc_figure")[0])
        pill_box = canvas.bbox(canvas.find_withtag("nbc_pill")[0])
        riel_box = canvas.bbox(canvas.find_withtag("nbc_riel")[0])
        assert figure_box[2] <= riel_box[0] + 4 and riel_box[2] <= pill_box[0]
        logo_items = canvas.find_withtag("nbc_logo")
        group_left = canvas.bbox(logo_items[0])[0] if logo_items else figure_box[0]
        group_center_x = (group_left + pill_box[2]) / 2
        assert abs(group_center_x - canvas.winfo_width() / 2) <= 16
        assert abs((figure_box[1] + figure_box[3]) / 2 - int(canvas.cget("height")) / 2) <= 8
        for column in range(3):
            assert dashboard.rate_table_headers[column].cget("bg") == RATE_TABLE_HEADER_BG
        assert dashboard.nbc_text("date") == "7 NOV"
        assert dashboard.nbc_text("pill") == "▲ +2"
        assert dashboard.nbc_text("unit") == "KHR / USD"
        assert dashboard.nbc_text("spark_label") == "5-day"
        assert dashboard.nbc_canvas.find_withtag("nbc_sparkline")
        dashboard.root.after_cancel(dashboard._rate_pulse_after_id)
        dashboard._rate_pulse_after_id = None
        dashboard._rate_pulse_step = 12
        dashboard._apply_rate_pulse()
        assert labels["CNY"]["official"].cget("fg") == "#FFD1D1"
        assert labels["ACLEDA"]["buy"].cget("fg") == "#FFB7C0"
        assert labels["WING"]["sell"].cget("fg") == "#B8E7FF"
        dashboard.exchange_rates = _rates(now)
        dashboard._refresh_exchange_rate_display()
        assert dashboard.nbc_text("pill") == ""
        dashboard.exchange_rates = _rates(now - timedelta(days=5))
        dashboard._refresh_exchange_rate_display()
        dashboard._apply_rate_pulse()
        assert labels["ACLEDA"]["buy"].cget("fg") == COLORS["muted"]
        assert labels["ACLEDA"]["buy_arrow"].cget("text") == ""
        assert "STALE" in dashboard.nbc_text("date")
        assert dashboard.nbc_text("pill") == ""
        dashboard.exchange_rates = {}
        dashboard._refresh_exchange_rate_display()
        assert labels["CNY"]["official"].cget("text") == "—"
        assert labels["CNY"]["unit"].cget("text") == ""
        assert labels["CNY"]["official_arrow"].cget("text") == ""
        assert dashboard.nbc_text("figure") == "—"
        dashboard._tick_rate_pulse()
        assert dashboard._rate_pulse_after_id is not None
    finally:
        dashboard.root.destroy()
    assert dashboard._rate_pulse_after_id is None


def test_dashboard_uses_half_and_quarter_columns_with_private_card():
    dashboard = _make_dashboard(
        today_summary=lambda: {"count": 3, "KHR": "52000", "USD": "12.5"},
        initial_exchange_rates=_rates(),
    )
    try:
        assert dashboard.private_card.master is dashboard.private_side
        assert dashboard.rate_card.master is dashboard.dashboard_side
        assert not any(isinstance(child, tk.Text) for child in dashboard.header.winfo_children())
        assert dashboard.rate_group_title_label.cget("text") == "អត្រាប្តូរប្រាក់ឯកជន - Private rates"
        assert dashboard.private_card.cget("bg") == COLORS["surface"]
        assert dashboard.rate_top_bar.cget("bg") == "#FFE66D"
        assert dashboard.rate_title_label.cget("text").replace("\n", " ") == "អត្រាប្តូរប្រាក់ រៀល ដុល្លារ និងយ័ន (ចិន)"
        assert dashboard.controls_card.master is dashboard.operations_body
        assert dashboard.status_card.master is dashboard.operations_body
        assert dashboard.today_card.master is dashboard.operations_body
        assert not hasattr(dashboard, "today_strip_label")
        assert "TODAY  3 payments  ·  KHR 52,000  ·  USD 12.50" in dashboard.ticker_text()
        assert not hasattr(dashboard, "rate_group_unverified_label")
        dashboard._apply_rate_group_status("CONNECTED · PRIVATE GROUP")
        assert dashboard.rate_status_label.cget("text") == "●"
        assert dashboard.rate_group_button.cget("text") == "DISCONNECT"
        for geometry in ("900x600", "1180x800", "1382x744"):
            _layout(dashboard, geometry)
            narrow = geometry == "900x600"
            cards = (dashboard.payment_card, dashboard.rate_card, dashboard.private_card)
            total = sum(card.winfo_width() for card in cards)
            assert abs(cards[0].winfo_width() / total - 0.50) < 0.02
            assert abs(cards[1].winfo_width() / total - 0.25) < 0.02
            assert abs(cards[2].winfo_width() / total - 0.25) < 0.02
            assert len({card.winfo_rooty() for card in cards}) == 1
            assert abs(dashboard.recent_card.winfo_width() - dashboard.payment_card.winfo_width()) <= 1
            recent_bottom = dashboard.recent_card.winfo_rooty() + dashboard.recent_card.winfo_height()
            for side_card in cards[1:]:
                assert side_card.winfo_rooty() + side_card.winfo_height() == recent_bottom
            history_height = int(dashboard.history_canvas.cget("height"))
            assert history_height >= 88
            # The list shrinks (down to two rows) before the Dashboard itself needs to scroll.
            assert history_height == 88 or dashboard.dashboard_scrollbar.winfo_manager() == ""
            bank_font = tkfont.Font(root=dashboard.root, font=dashboard.history_heading_labels[2].cget("font"))
            assert bank_font.cget("family") == (dashboard.condensed_font if narrow else "Segoe UI")
            assert dashboard.header.winfo_height() <= 170
            assert dashboard.nbc_card.winfo_height() <= dashboard.clock_frame.winfo_height()
            assert dashboard.nbc_card.winfo_height() == (112 if narrow else 132)
            root_center_x = dashboard.root.winfo_rootx() + int(geometry.split("x")[0]) / 2
            for label in (dashboard.clock_label, dashboard.date_label, dashboard.live_label):
                assert abs(label.winfo_rootx() + label.winfo_width() / 2 - root_center_x) < 10
            clock_right = dashboard.clock_label.winfo_rootx() + dashboard.clock_label.winfo_width()
            assert clock_right <= dashboard.nbc_card.winfo_rootx()
            controls_on_top = geometry == "1382x744"
            assert dashboard._rate_controls_in_top_bar is controls_on_top
            assert dashboard.rate_status_label.cget("text") == ("●" if controls_on_top else "CONNECTED")
            assert dashboard.rate_group_text.winfo_height() >= (250 if narrow else 300)
            assert dashboard.rate_group_scrollbar.winfo_width() <= 10
            for title in (dashboard.rate_title_label, dashboard.rate_group_title_label):
                title_font = tkfont.Font(root=dashboard.root, font=title.cget("font"))
                assert max(title_font.measure(line) for line in title.cget("text").split("\n")) <= title.winfo_width() - 12
            for labels in dashboard.rate_display_labels.values():
                for field in ("official", "buy", "sell"):
                    figure = labels.get(field)
                    if figure is not None:
                        assert figure.winfo_reqwidth() + labels[f"{field}_arrow"].winfo_reqwidth() <= (
                            labels[f"{field}_cell"].winfo_width()
                        )
                assert labels["bank"].winfo_reqwidth() <= labels["row"].winfo_width()
            if narrow:
                assert dashboard.dashboard_scrollbar.winfo_manager() == "grid"
    finally:
        dashboard.root.destroy()


def test_private_card_renders_two_line_offers_with_usd_khr_arrows_gaps_and_glow():
    now = datetime.now(timezone.utc)
    dashboard = _make_dashboard(initial_exchange_rates=_rates())
    try:
        _layout(dashboard, "1382x744")
        dashboard._store_rate_group_message(_group_message(
            1, "💗Dara Sok (99ផ្សារ) 👉Acc Name: Dara", 30,
            "ខ្មែរ វីង AC ដូរ $$ 4088\n\n$$ ABA 30000$ ដូរខ្មែរ 4091",
        ), now=now)
        dashboard._store_rate_group_message(_group_message(
            2, "💗Dara Sok (99ផ្សារ) 👉Acc Name: Dara", 1,
            "ខ្មែរ វីង AC ដូរ $$ 4089\n\n$$ ABA 30000$ ដូរខ្មែរ 4090,5\nយកខ្មែរ អម្រឹត KB\n☎️ 012000000",
        ), now=now)
        dashboard._store_rate_group_message(_group_message(3, "Sok 097", 3, "Kb100លានយកAc"), now=now)
        dashboard._store_rate_group_message(_group_message(4, "Old Trader", 90, "ខ្មែរ AC ដូរ $ 4080"), now=now)
        dashboard._render_rate_group_messages(now=now)
        text = dashboard.rate_group_text
        displayed = text.get("1.0", "end")
        assert displayed.index("  Dara Sok\n") < displayed.index("  Sok\n") < displayed.index("  Old Trader\n")
        for hidden in ("012000000", "Acc", "💗", "097", "យកខ្មែរ", "៛", "$"):
            assert hidden not in displayed
        assert "KHR→USD\t4089 KHR ▲  +4\nWing·AC\n" in displayed
        assert "USD→KHR\t4090.5 KHR ▼  +5.5\n30,000 USD  ABA\n" in displayed
        assert "KB 100M KHR យក AC" in displayed
        for name, direction, rate in (("k2u", KHR_TO_USD, "4089 KHR"), ("u2k", USD_TO_KHR, "4090.5 KHR")):
            ranges = text.tag_ranges(f"rate_{name}")
            values = [text.get(ranges[i], ranges[i + 1]) for i in range(0, len(ranges), 2)]
            assert rate in values
            assert text.tag_cget(f"rate_{name}", "foreground") == RATE_GROUP_DIRECTION_COLORS[direction]
        rate_index = text.search("4090.5 KHR", "1.0")
        rate_font = next(tag for tag in text.tag_names(rate_index) if tag.startswith("font_"))
        assert tkfont.Font(root=dashboard.root, font=text.tag_cget(rate_font, "font")).cget("size") == 14
        size_index = text.search("30,000 USD", "1.0")
        size_font = next(tag for tag in text.tag_names(size_index) if tag.startswith("font_"))
        size_font_value = tkfont.Font(root=dashboard.root, font=text.tag_cget(size_font, "font"))
        assert (size_font_value.cget("size"), size_font_value.cget("weight")) == (12, "bold")
        assert "glow" in text.tag_names(text.search("Dara Sok", "1.0"))
        assert text.tag_cget("glow", "background") == RATE_GROUP_GLOW_COLOR
        assert "glow" not in text.tag_names(text.search("Old Trader", "1.0"))
        assert "faded" in text.tag_names(text.search("Old Trader", "1.0"))
        assert "faded" not in text.tag_names(text.search("Dara Sok", "1.0"))
        assert text.tag_cget("trend_up", "foreground") == RATE_TREND_COLORS["up"]
        assert text.tag_cget(f"message_row_0", "background") == RATE_GROUP_ROW_COLORS[0]
        assert dashboard.rate_summary_labels[KHR_TO_USD].cget("text") == "KHR→USD  4089 KHR"
        assert dashboard.rate_summary_labels[USD_TO_KHR].cget("text") == "USD→KHR  4090.5 KHR"
        dashboard._store_rate_group_message(
            {**_group_message(3, "Sok 097", 0, "ខ្មែរ ABA ដូរ $ 4090"), "edited": True}, now=now,
        )
        dashboard._render_rate_group_messages(now=now)
        displayed = text.get("1.0", "end")
        assert "✎" in displayed and "KB 100M KHR" not in displayed
        assert dashboard.rate_summary_labels[KHR_TO_USD].cget("text") == "KHR→USD  4089 – 4090 KHR"
        assert dashboard.rate_summary_arrows[KHR_TO_USD].cget("text") == "▲"
        dashboard._remove_rate_group_messages({"ids": [3]})
        dashboard._render_rate_group_messages(now=now)
        assert "4090 KHR" not in text.get("1.0", "end")
        dashboard._rate_group_glow.clear()
        dashboard._render_rate_group_messages(now=now)
        assert "glow" not in text.tag_names(text.search("Dara Sok", "1.0"))
    finally:
        dashboard.root.destroy()


def test_history_posts_loaded_at_connect_do_not_glow():
    now = datetime.now(timezone.utc)
    dashboard = _make_dashboard()
    try:
        dashboard._store_rate_group_message(_group_message(1, "Dara", 30, "ខ្មែរ AC ដូរ $ 4089"), now=now)
        assert dashboard._rate_group_glow == {}
        dashboard._store_rate_group_message(_group_message(2, "Dara", 0, "ខ្មែរ AC ដូរ $ 4089"), now=now)
        assert dashboard._rate_group_glow == {}
        dashboard._store_rate_group_message(_group_message(3, "Dara", 0, "ខ្មែរ AC ដូរ $ 4090"), now=now)
        assert "dara" in dashboard._rate_group_glow
    finally:
        dashboard.root.destroy()


def test_operations_panel_scrolls_to_controls():
    dashboard = _make_dashboard()
    try:
        _layout(dashboard, "900x600")
        dashboard.notebook.select(dashboard.diagnostics_tab)
        dashboard.diagnostic_notebook.select(dashboard.operations_page)
        dashboard.root.update_idletasks()
        dashboard._update_operations_scrollregion()
        dashboard.root.update_idletasks()
        assert dashboard.operations_scrollbar.winfo_manager() == "grid"
        dashboard.operations_canvas.yview_moveto(1)
        dashboard.root.update_idletasks()
        operations_bottom = dashboard.controls_card.winfo_rooty() + dashboard.controls_card.winfo_height()
        viewport_bottom = dashboard.operations_canvas.winfo_rooty() + dashboard.operations_canvas.winfo_height()
        assert operations_bottom <= viewport_bottom
    finally:
        dashboard.root.destroy()


def test_secondary_monitor_is_preferred_over_primary():
    primary = {"left": 0, "top": 0, "right": 1920, "bottom": 1080, "primary": True}
    secondary = {"left": 1920, "top": 0, "right": 3200, "bottom": 1024, "primary": False}
    assert preferred_secondary_monitor([primary, secondary]) == secondary
    assert preferred_secondary_monitor([primary]) is None


def test_announcement_state_never_claims_success_early():
    assert announcement_label("QUEUED")[0] == "● ANNOUNCING…"
    assert announcement_label("SPOKEN")[0] == "✓ ANNOUNCED"
    assert "MUTED" in announcement_label("MUTED")[0]
    assert "FAILED" in announcement_label("FAILED")[0]


def test_live_component_status_mapping_is_truthful():
    assert component_health("Connected as Operator", "telegram") == ("● CONNECTED", "green")
    assert component_health("Error", "telegram")[1] == "red"
    assert component_health("Muted", "speaker") == ("⊘ MUTED", "amber")
    assert component_health("Waiting", "source") == ("● WAITING", "amber")
    assert component_health("Verified", "source") == ("● VERIFIED", "green")


def test_private_reader_auto_connect_is_scheduled_once_and_runs():
    calls = []
    dashboard = _make_dashboard(start_rate_group_reader=lambda: calls.append("start"))
    try:
        assert dashboard._rate_group_start_after_id is not None
        dashboard._auto_start_rate_group_reader()
        assert calls == ["start"]
        assert dashboard.rate_group_button.cget("text") == "CONNECTING..."
        dashboard._auto_start_rate_group_reader()
        assert calls == ["start"]
    finally:
        dashboard.root.destroy()


def test_cambodia_flag_is_drawn_with_blue_red_bands_and_white_temple():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk is unavailable: {exc}")
    try:
        flag = cambodia_flag_image(root, 20)
        assert (flag.width(), flag.height()) == (30, 20)
        assert flag.get(1, 1) == (3, 46, 161)
        assert flag.get(1, 10) == (224, 0, 37)
        assert flag.get(1, 18) == (3, 46, 161)
        assert flag.get(15, 8) == (255, 255, 255)
    finally:
        root.destroy()


def test_nbc_logo_sits_before_the_rate_and_missing_logo_is_optional(tmp_path):
    from app.dashboard import load_nbc_logo

    dashboard = _make_dashboard(initial_exchange_rates=_rates())
    try:
        _layout(dashboard, "1382x744")
        canvas = dashboard.nbc_canvas
        logo_items = canvas.find_withtag("nbc_logo")
        assert logo_items, "assets/nbc_logo.png should be shown"
        logo_box = canvas.bbox(logo_items[0])
        figure_box = canvas.bbox(canvas.find_withtag("nbc_figure")[0])
        assert logo_box[2] <= figure_box[0]
        assert 30 <= logo_box[3] - logo_box[1] <= 50
        assert load_nbc_logo(dashboard.root, 40, tmp_path / "missing.png") is None
        dashboard._nbc_logos = {False: None, True: None}
        dashboard._draw_nbc_card()
        assert not canvas.find_withtag("nbc_logo")
        assert dashboard.nbc_text("figure") == "4,085"
    finally:
        dashboard.root.destroy()


def test_bank_logos_replace_category_text_and_rows_do_not_grow():
    dashboard = _make_dashboard(initial_exchange_rates=_rates())
    try:
        _layout(dashboard, "1382x744")
        before = {
            source: (labels["row"].winfo_height(), labels["row"].winfo_width())
            for source, labels in dashboard.rate_display_labels.items()
        }
        for source in ("ACLEDA", "WING"):
            category = dashboard.rate_display_labels[source]["category"]
            assert category.cget("image"), f"{source} logo should be shown"
            assert category.cget("text") == ""
            assert category.winfo_reqheight() == 60
            cell = dashboard.rate_display_labels[source]["row"]
            center = category.winfo_rootx() + category.winfo_width() / 2
            assert abs(center - (cell.winfo_rootx() + cell.winfo_width() / 2)) <= 3
        dashboard._refresh_exchange_rate_display()
        dashboard.root.update()
        after = {
            source: (labels["row"].winfo_height(), labels["row"].winfo_width())
            for source, labels in dashboard.rate_display_labels.items()
        }
        assert after == before
        _layout(dashboard, "900x600")
        assert dashboard.rate_display_labels["ACLEDA"]["category"].winfo_reqheight() == 44
    finally:
        dashboard.root.destroy()


def test_payment_amount_shows_banknote_at_digit_height_on_one_line():
    from app.dashboard import format_payment_digits, load_asset_image, note_height_for

    assert format_payment_digits("1000000", "KHR") == "1,000,000"
    assert format_payment_digits("12.5", "USD") == "12.50"
    assert format_payment_digits("5", "EUR") == "—"
    assert note_height_for(66) == 64
    assert note_height_for(55) == 52
    assert note_height_for(41) == 40
    assert note_height_for(10) == 22
    dashboard = _make_dashboard()
    try:
        assert load_asset_image(dashboard.root, "missing.png") is None
        _layout(dashboard, "1382x744")
        assert not dashboard.amount_note_label.winfo_manager()
        for currency, amount, text in (("KHR", "1000000", "1,000,000"), ("USD", "12.50", "12.50")):
            dashboard.current_currency = currency
            dashboard._show_amount(amount, currency)
            dashboard.root.update()
            assert dashboard.values["amount"].get() == text
            assert dashboard.amount_note_label.winfo_manager() == "pack"
            digit_height = int(
                tkfont.Font(root=dashboard.root, font=dashboard.amount_label.cget("font")).metrics("ascent") * 0.66
            )
            note = dashboard._note_images[(currency, note_height_for(round(digit_height * 1.1)))]
            assert dashboard.amount_note_label.cget("image") == str(note)
            assert note.height() > digit_height
            assert note.height() == 56
            assert note.width() == note.height()
            note_center = dashboard.amount_note_label.winfo_rooty() + dashboard.amount_note_label.winfo_height() / 2
            label_font = tkfont.Font(root=dashboard.root, font=dashboard.amount_label.cget("font"))
            digits_center = (
                dashboard.amount_label.winfo_rooty() + label_font.metrics("ascent") - digit_height / 2
            )
            assert abs(note_center - digits_center) <= 4
            assert dashboard.amount_note_label.winfo_rooty() < dashboard.amount_label.winfo_rooty() + dashboard.amount_label.winfo_height()
        dashboard.current_currency = "KHR"
        dashboard._show_amount("123456789000", "KHR")
        dashboard.root.update()
        row_width = dashboard.amount_note_label.winfo_reqwidth() + dashboard.amount_label.winfo_reqwidth()
        assert row_width <= dashboard.payment_card.winfo_width() - 40
        assert tkfont.Font(root=dashboard.root, font=dashboard.amount_label.cget("font")).cget("size") < 56
        dashboard._show_amount(None, None)
        assert dashboard.values["amount"].get() == "—"
        assert not dashboard.amount_note_label.winfo_manager()
    finally:
        dashboard.root.destroy()


def test_ticker_sits_beside_the_tabs_scrolls_and_shows_fuel_prices():
    dashboard = _make_dashboard(today_summary=lambda: {"count": 2, "KHR": "8000", "USD": "1.5"})
    try:
        for geometry in ("900x600", "1180x800", "1382x744"):
            _layout(dashboard, geometry)
            dashboard._position_ticker()
            dashboard.root.update_idletasks()
            tabs_right, tab_height = dashboard._ticker_tabs
            assert dashboard.ticker.winfo_manager() == "place"
            left = dashboard.ticker.winfo_x() - dashboard.notebook.winfo_x()  # notebook coordinates
            assert left >= tabs_right  # never covers the tabs
            assert dashboard.ticker.winfo_y() == dashboard.notebook.winfo_y()
            assert dashboard.ticker.winfo_height() == tab_height
            assert left + dashboard.ticker.winfo_width() <= dashboard.notebook.winfo_width()
        # The status shares the title row, and the list title is gone.
        assert dashboard.announcement_label.master is dashboard.payment_title_row
        assert not any(
            isinstance(child, tk.Label) and "RECENT" in str(child.cget("text"))
            for child in dashboard.recent_card.winfo_children()
        )
        first = dashboard.ticker.coords(dashboard.ticker.find_withtag("ticker")[0])[0]
        for _ in range(5):
            dashboard._tick_ticker()
        assert dashboard.ticker.coords(dashboard.ticker.find_withtag("ticker")[0])[0] < first
        assert "TODAY  2 payments  ·  KHR 8,000  ·  USD 1.50" in dashboard.ticker_text()
        dashboard.publish("fuel_prices", {
            "regular": 4350, "diesel": 5300, "regular_change": -700, "diesel_change": -350,
            "valid_from": "2099-11-11", "valid_to": "2099-11-21", "message_id": 1, "posted_at": "",
        })
        dashboard._drain_events()
        texts = [dashboard.ticker.itemcget(item, "text") for item in dashboard.ticker.find_withtag("ticker")
                 if dashboard.ticker.type(item) == "text"]
        assert "4,350៛" in texts and " ▼700" in texts
        assert dashboard.ticker.find_withtag("gold_icon")  # drawn gold bar
    finally:
        dashboard.root.destroy()
    assert dashboard._ticker_after_id is None



def test_history_columns_align_and_long_text_wraps_to_two_lines():
    rows = [
        {"amount": "25000", "currency": "KHR", "sender_name": "SOK DARA", "bank": "ABA",
         "received_at": "2026-11-12T08:00:00+00:00"},
        {"amount": "12.50", "currency": "USD", "sender_name": "NHEAN MONYRACHANA SOPHEAKTRA CHANRAKSMEY",
         "bank": "FOREIGN TRADE BANK OF CAMBODIA", "received_at": "2026-11-12T08:01:00+00:00"},
    ]
    dashboard = _make_dashboard(recent_payments=lambda limit=1000: rows)
    try:
        _layout(dashboard, "1382x744")
        dashboard._render_history(rows)
        dashboard.root.update_idletasks()
        lines = dashboard.history_inner.winfo_children()
        assert [line.winfo_height() for line in lines] == [44, 68]
        labels = lines[1].winfo_children()
        assert [label.cget("anchor") for label in labels] == ["e", "w", "center", "e"]
        assert [label.cget("justify") for label in labels] == ["right", "left", "center", "right"]
        assert labels[1].cget("text").count("\n") == 1
        assert [heading.cget("anchor") for heading in dashboard.history_heading_labels] == ["e", "w", "center", "e"]
        for column, label in enumerate(labels):  # columns stay aligned with the headings
            heading = dashboard.history_heading_labels[column]
            assert abs(label.winfo_rootx() - heading.winfo_rootx()) <= 2
    finally:
        dashboard.root.destroy()
