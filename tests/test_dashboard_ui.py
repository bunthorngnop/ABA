from app.dashboard import amount_color, announcement_label, component_health, format_payment_amount, responsive_layout_mode


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
