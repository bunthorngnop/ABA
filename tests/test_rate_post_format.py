"""Synthetic, display-only checks for the private exchange-group formatter.

All phrases below are short made-up examples in the group's writing styles;
they contain no real sender names, phone numbers, or copied private posts.
"""

import ast
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.rate_post_format import (
    KHR_TO_USD,
    NON_TEXT_PLACEHOLDER,
    PHOTO_PLACEHOLDER,
    USD_TO_KHR,
    format_rate_post,
    format_summary_range,
    short_sender_name,
    summarize_rates,
)


def rows(text):
    return [
        (row.label, row.rate_text, row.size_text, row.bank_text) if row.is_offer else ("~", row.text)
        for row in format_rate_post(text).rows
    ]


@pytest.mark.parametrize(
    ("written", "shown"),
    [
        ("4089", "4089 KHR"),
        ("4089.5", "4089.5 KHR"),
        ("4089,5", "4089.5 KHR"),
        ("4089.25", "4089.25 KHR"),
        ("4089,25", "4089.25 KHR"),
        ("4,089", "4089 KHR"),
        ("4.089", "4089 KHR"),
        ("4,089.5", "4089.5 KHR"),
        ("4,089,5", "4089.5 KHR"),
        ("4.089,5", "4089.5 KHR"),
    ],
)
def test_every_rate_style_is_shown_with_a_dot_and_riel_sign(written, shown):
    assert rows(f"ខ្មែរ AC ដូរ $ {written}") == [("KHR→USD", shown, "", "AC")]


def test_rate_band_and_markers_keep_sizes_and_other_numbers_out_of_rates():
    assert rows("ខ្មែរ AC ដូរ 3799") == [("~", "KHR AC ដូរ 3,799")]
    assert rows("ខ្មែរ AC ដូរ 4401") == [("~", "KHR AC ដូរ 4,401")]
    assert rows("ABA 4,000$ ដូរខ្មែរ") == [("~", "ABA 4,000 USD ដូរ KHR")]
    assert rows("ABA $4,000 ដូរខ្មែរ") == [("~", "ABA 4,000 USD ដូរ KHR")]
    assert rows("ខ្មែរដូរ$4089") == [("KHR→USD", "4089 KHR", "", "")]
    assert rows("$ AC 40,000 ដូរខ្មែរ 4090") == [("USD→KHR", "4090 KHR", "40,000", "AC")]


def test_direction_comes_from_the_words_around_exchange_verbs():
    assert rows("ខ្មែរ វីង ABA AC ដូរ $$ 4089") == [("KHR→USD", "4089 KHR", "", "Wing·ABA·AC")]
    assert rows("ABA វីង AC 30000$ ដូរខ្មែរ4091") == [("USD→KHR", "4091 KHR", "30,000 USD", "ABA·Wing·AC")]
    assert rows("ខ្មែរ AC $20,000 យក$ 4089") == [("KHR→USD", "4089 KHR", "20,000 USD", "AC")]
    assert rows("មានខ្មែរ KB 40,000$*4089.5") == [("KHR→USD", "4089.5 KHR", "40,000 USD", "KB")]
    assert rows("មាន$ AC ABA 40,000$ ដូរខ្មែរ 4091") == [("USD→KHR", "4091 KHR", "40,000 USD", "AC·ABA")]
    assert rows("ខ្មែរ AC wing ទិញ $20000= 4089.5") == [("KHR→USD", "4089.5 KHR", "20,000 USD", "AC·Wing")]
    assert rows("ខ្មែរ គ្រប់កុង ដូរ 4089") == [("KHR→USD", "4089 KHR", "", "គ្រប់កុង")]
    assert rows("$ដូរ10000*4091") == [("USD→KHR", "4091 KHR", "10,000", "")]
    assert rows("មានaba 2000$ដូខ្មែរaba 4090") == [("USD→KHR", "4090 KHR", "2,000 USD", "ABA")]


def test_ambiguous_lines_are_shown_without_a_direction():
    assert rows("អោយ ABA 4091.5") == [("·", "4091.5 KHR", "", "ABA")]
    assert rows("ABA4091") == [("·", "4091 KHR", "", "ABA")]
    assert rows("R AbA / $ AbA 50,000$ * 4089,5") == [("·", "4089.5 KHR", "50,000 USD", "ABA")]


def test_lead_in_line_joins_its_rate_line_but_two_offers_never_merge():
    assert rows("ខ្មែរAc\nទិញដុល្លា50000$*4089.5") == [("KHR→USD", "4089.5 KHR", "50,000 USD", "AC")]
    assert rows("ខ្មែរគ្រប់កុង ទិញដុល្លារABA,AC,Amret\n18500$ 4089.5") == [
        ("KHR→USD", "4089.5 KHR", "18,500 USD", "គ្រប់កុង·ABA·AC·Amret"),
    ]
    assert rows("មានខ្មែរ AC 10,000$\n4090\nយក $aba") == [("KHR→USD", "4090 KHR", "10,000 USD", "AC")]
    assert rows("ដុល្លាគ្រប់កុង 30000$ ដូរខ្មែរ4091\nអោយ ABA 4091.5") == [
        ("USD→KHR", "4091 KHR", "30,000 USD", "គ្រប់កុង"),
        ("·", "4091.5 KHR", "", "ABA"),
    ]


def test_contacts_bank_lists_blank_lines_and_notes_are_cleaned():
    post = format_rate_post(
        "ដុល្លារ $AC $60,000 ដូរខ្មែរ 4090.5\n"
        "យកខ្មែរ អម្រឹត ស្ថាបនា AC វីង KB\n\n\n\n"
        "ខ្មែរ AC $40,000 យក$ 4089\n"
        "➨យក$ AC វីង ស្ថាបនា\n\n"
        "(No ABA)\n"
        "👉012 000 0000 Telegram\n"
        "👉👉Acc: Example Name\n"
        "☏ 010 0000 000\n"
        "011000000\n"
        "  (ទំហំប្តូរ 5,000$ ឡេីង)"
    )
    assert [(row.label, row.rate_text, row.size_text, row.bank_text) for row in post.rows] == [
        ("USD→KHR", "4090.5 KHR", "60,000 USD", "AC"),
        ("KHR→USD", "4089 KHR", "40,000 USD", "AC"),
    ]
    assert post.notes == ("No ABA", "min 5,000 USD")
    displayed = " ".join([row.text for row in post.rows] + list(post.notes))
    for hidden in ("012", "010", "011", "Acc", "Example", "Telegram", "Amret", "ស្ថាបនា", "Wing", "KB"):
        assert hidden not in displayed


def test_phone_digits_are_removed_before_rates_are_found():
    assert rows("ABA 4090 090000000") == [("·", "4090 KHR", "", "ABA")]
    assert rows("☏ 096 4090 556") == [("~", "…")]


def test_glued_words_banks_currency_and_separators_are_normalized():
    assert rows("$30000ដូរខ្មែរAmretAC.Wing 4090,5") == [("USD→KHR", "4090.5 KHR", "30,000 USD", "Amret·AC·Wing")]
    assert rows("ខ្មែរACទិញដុល្លារអម្រឹត15000x4090") == [("KHR→USD", "4090 KHR", "15,000", "AC·Amret")]
    assert rows("ABA25000$ដូរacវីងamret") == [("~", "ABA 25,000 USD ដូរ AC Wing Amret")]
    assert rows("Kb100លានយកAc") == [("~", "KB 100M KHR យក AC")]
    assert rows("ABA 300លានយកACfree15000r") == [("~", "ABA 300M KHR យក AC free 15,000 KHR")]
    assert rows("Aba. 140 លាន យក ac") == [("~", "ABA 140M KHR យក AC")]
    assert rows("Cana 50,000$ សុំដូរ AC& ABA") == [("~", "Cana 50,000 USD សុំដូរ AC ABA")]
    assert rows("ABA 400 លានដូរ ខ្មែរ អីក៍បាន") == [("~", "ABA 400M KHR ដូរ KHR អីក៏បាន")]
    assert rows("ខ្មែរ ac ដូ$ ac 10000$**4089,5") == [("KHR→USD", "4089.5 KHR", "10,000 USD", "AC")]
    assert rows("៛ KB PRASAC ដូរ $ 4089") == [("KHR→USD", "4089 KHR", "", "KB")]
    assert rows("ខ្មែរ ស្ថាបនា Sathapana ដូរ $ ៤០៨៩") == [("KHR→USD", "4089 KHR", "", "ស្ថាបនា")]


def test_placeholders_and_empty_posts_stay_plain():
    assert rows(PHOTO_PLACEHOLDER) == [("~", PHOTO_PLACEHOLDER)]
    assert rows(NON_TEXT_PLACEHOLDER) == [("~", NON_TEXT_PLACEHOLDER)]
    assert rows("") == [("~", "…")]
    assert rows("012000000") == [("~", "…")]


def test_sender_names_are_short_without_emoji_roles_or_phone_digits():
    assert short_sender_name("💗Dara Sok (99ផ្សារ) 👉Acc Name: Dara Sok") == "Dara Sok"
    assert short_sender_name("Vanna Mony 097 ( ACC Example)") == "Vanna Mony"
    assert short_sender_name("Lina 🦋🐝") == "Lina"
    assert short_sender_name("Dara Sok and Vanna Mony Exchange Agent") == "Dara Sok and Vanna…"
    assert short_sender_name("💗") == "Unknown sender"
    assert short_sender_name(None) == "Unknown sender"


def test_summary_uses_only_recent_tagged_single_rate_rows():
    now = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
    posts = [
        (now - timedelta(minutes=1), format_rate_post("ខ្មែរ AC ដូរ $ 4089\n\n$ AC ដូរខ្មែរ 4091")),
        (now - timedelta(minutes=14), format_rate_post("មានខ្មែរ KB 10,000$*4089.5")),
        (now - timedelta(minutes=16), format_rate_post("ខ្មែរ AC ដូរ $ 4000")),
        (now + timedelta(minutes=1), format_rate_post("ខ្មែរ AC ដូរ $ 4100")),
        (now - timedelta(minutes=2), format_rate_post("ABA 4095")),
    ]
    summary = summarize_rates(posts, now)
    assert summary == {
        KHR_TO_USD: (Decimal("4089"), Decimal("4089.5")),
        USD_TO_KHR: (Decimal("4091"), Decimal("4091")),
    }
    assert format_summary_range(summary[KHR_TO_USD]) == "4089–4089.5"
    assert format_summary_range(summary[USD_TO_KHR]) == "4091"
    assert format_summary_range(None) == "—"


def test_formatter_is_independent_of_payment_storage_and_speech():
    source = Path("app/rate_post_format.py").read_text(encoding="utf-8")
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(node.module or "")])
    }
    assert imported <= {"re", "unicodedata", "dataclasses", "datetime", "decimal", "typing"}
    for forbidden in ("payment_parser", "bank_normalizer", "database", "audio_queue", "tts", "sqlite"):
        assert forbidden not in source
