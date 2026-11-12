"""Regular-petrol and diesel pump prices from the owner-chosen fuel-price Telegram channel.

Display only: the dashboard ticker shows the latest សាំង and ម៉ាស៊ូត prices. Nothing here is
used for payments. Example post (owner-provided public announcement):

    ថ្លៃលក់រាយប្រេងឥន្ធនៈនៅតាមស្ថានីយសម្រាប់ការអនុវត្តចាប់ពីវេលាម៉ោង ១ រសៀលថ្ងៃទី ១១ ខែវិច្ឆិកា ឆ្នាំ២០២៦ ...
    * សាំង = ៤ ៣៥០ រៀល (ចុះថ្លៃ៧០០រៀល)
    * ម៉ាស៊ូត = ៥ ៣០០ រៀល (ចុះថ្លៃ៣៥០ រៀល)
"""

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Optional

# Fuel-price Telegram channel (owner-provided 2026-11-12; replaces the Ministry channel -1001254362029,
# whose posts carry the prices only inside the image).
FUEL_CHANNEL_ID = -1003653280106
# The channel also posts daily commodity prices, so look well back for the last announcement.
FUEL_HISTORY_MESSAGES = 200
FUEL_PRICE_MIN = 2_000
FUEL_PRICE_MAX = 10_000
# Without an end date, prices count as old after one 10-day cycle plus a day.
FUEL_STALE_AFTER = timedelta(days=11)

REGULAR = "regular"
DIESEL = "diesel"
FUEL_LABELS = {REGULAR: "សាំង", DIESEL: "ម៉ាស៊ូត"}

_KHMER_DIGITS = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)
# Khmer vowel signs and diacritics that follow a consonant. Keyboards may type them in different
# orders (e.g. ា+ំ or ំ+ា) that look identical on screen, so runs of them are put in one order.
_KHMER_MARKS = re.compile("[\u17b4-\u17d3\u17dd]{2,}")


def _canonical(text: str) -> str:
    return _KHMER_MARKS.sub(lambda match: "".join(sorted(match.group(0))), text)


def _words(*words: str) -> str:
    return "|".join(re.escape(_canonical(word)) for word in words)


KHMER_MONTHS = {
    "មករា": 1, "កុម្ភៈ": 2, "មីនា": 3, "មេសា": 4, "ឧសភា": 5, "មិថុនា": 6,
    "កក្កដា": 7, "សីហា": 8, "កញ្ញា": 9, "តុលា": 10, "វិច្ឆិកា": 11, "ធ្នូ": 12,
}
_MONTHS_CANONICAL = {_canonical(name): number for name, number in KHMER_MONTHS.items()}
_NUMBER = r"[0-9](?:[0-9]|[ ,.\u00a0](?=[0-9]))*"
_REGULAR_WORDS = ("សាំង",)
_DIESEL_WORDS = ("ម៉ាស៊ូត", "ម៉ាស៊ុត", "ម៉ាសូត")
_RIEL = _words("រៀល") + "|៛"
_PRICE_LINE = re.compile(
    rf"(?P<fuel>{_words(*_REGULAR_WORDS, *_DIESEL_WORDS)})[^\n0-9=:៖]{{0,40}}?\s*[=:៖]?\s*"
    rf"(?P<price>{_NUMBER})\s*(?:{_RIEL})(?P<rest>[^\n]*)"
)
_REGULAR_CANONICAL = {_canonical(word) for word in _REGULAR_WORDS}
_CHANGE = re.compile(rf"(?P<direction>{_words('ចុះថ្លៃ', 'ឡើងថ្លៃ', 'ចុះតម្លៃ', 'ឡើងតម្លៃ')})\s*(?P<amount>{_NUMBER})?")
_DOWN_WORDS = {_canonical("ចុះថ្លៃ"), _canonical("ចុះតម្លៃ")}
_UNCHANGED = re.compile(_words("នៅដដែល", "មិនប្រែប្រួល", "ថេរ"))
_DATE = re.compile(
    rf"(?:{_words('ថ្ងៃទី')})\s*(?P<day>[0-9]{{1,2}})\s*(?:{_words('ខែ')})\s*(?P<month>[^\s0-9]+?)\s*"
    rf"(?:{_words('ឆ្នាំ')})\s*(?P<year>[0-9]{{4}})"
)
_HEADER = _canonical("ប្រេងឥន្ធន")  # also matches the ឥន្ធនះ spelling


def fuel_post_counts(texts) -> dict[str, int]:
    """Structure-only counts for logging why no announcement was found (never any post text)."""
    counts = {
        "posts": 0, "with_text": 0, "fuel_word": 0, "regular_word": 0, "diesel_word": 0,
        "riel_word": 0, "equals": 0, "numbers": 0, "price_lines": 0,
    }
    for text in texts:
        counts["posts"] += 1
        if not isinstance(text, str) or not text.strip():
            continue
        normalized = _normalize(text)
        counts["with_text"] += 1
        counts["fuel_word"] += _HEADER in normalized
        counts["regular_word"] += any(_canonical(word) in normalized for word in _REGULAR_WORDS)
        counts["diesel_word"] += any(_canonical(word) in normalized for word in _DIESEL_WORDS)
        if _HEADER in normalized:
            counts["riel_word"] += len(re.findall(_RIEL, normalized))
            counts["equals"] += normalized.count("=")
            counts["numbers"] += len(re.findall(r"[0-9]{3,}|[0-9] [0-9]{3}", normalized))
        counts["price_lines"] += len(_PRICE_LINE.findall(normalized))
    return counts


@dataclass(frozen=True)
class FuelPrices:
    regular: int
    diesel: int
    # Signed riel change stated in the post (negative = cheaper); None when the post doesn't say.
    regular_change: Optional[int] = None
    diesel_change: Optional[int] = None
    valid_from: Optional[str] = None  # ISO date
    valid_to: Optional[str] = None  # ISO date
    message_id: int = 0
    posted_at: str = ""  # ISO datetime

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> Optional["FuelPrices"]:
        try:
            return cls(
                regular=int(value["regular"]), diesel=int(value["diesel"]),
                regular_change=_optional_int(value.get("regular_change")),
                diesel_change=_optional_int(value.get("diesel_change")),
                valid_from=value.get("valid_from") or None, valid_to=value.get("valid_to") or None,
                message_id=int(value.get("message_id") or 0), posted_at=str(value.get("posted_at") or ""),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _optional_int(value: object) -> Optional[int]:
    return None if value is None or value == "" else int(value)


def _number(text: str) -> int:
    return int(re.sub(r"[^0-9]", "", text))


def _normalize(text: str) -> str:
    return _canonical(text.translate(_INVISIBLE).translate(_KHMER_DIGITS))


def parse_fuel_post(text: object, message_id: int = 0, posted_at: str = "") -> Optional[FuelPrices]:
    """Return regular and diesel prices from a Ministry announcement, or None for any other post."""
    if not isinstance(text, str):
        return None
    normalized = _normalize(text)
    found: dict[str, tuple[int, Optional[int]]] = {}
    for match in _PRICE_LINE.finditer(normalized):
        fuel = REGULAR if match.group("fuel") in _REGULAR_CANONICAL else DIESEL
        if fuel in found:
            continue
        price = _number(match.group("price"))
        if not FUEL_PRICE_MIN <= price <= FUEL_PRICE_MAX:
            return None
        found[fuel] = (price, _parse_change(match.group("rest")))
    if REGULAR not in found or DIESEL not in found:
        return None
    dates = [_parse_date(match) for match in _DATE.finditer(normalized)]
    dates = [value for value in dates if value is not None]
    valid_from = dates[0].isoformat() if dates else None
    valid_to = dates[1].isoformat() if len(dates) > 1 else None
    return FuelPrices(
        regular=found[REGULAR][0], diesel=found[DIESEL][0],
        regular_change=found[REGULAR][1], diesel_change=found[DIESEL][1],
        valid_from=valid_from, valid_to=valid_to, message_id=int(message_id), posted_at=posted_at,
    )


def _parse_change(rest: str) -> Optional[int]:
    match = _CHANGE.search(rest)
    if match:
        amount = _number(match.group("amount")) if match.group("amount") else 0
        return -amount if match.group("direction") in _DOWN_WORDS else amount
    if _UNCHANGED.search(rest):
        return 0
    return None


def _parse_date(match: re.Match) -> Optional[date]:
    month = _MONTHS_CANONICAL.get(match.group("month"))
    if month is None:
        return None
    try:
        return date(int(match.group("year")), month, int(match.group("day")))
    except ValueError:
        return None


def merge_with_previous(new: FuelPrices, previous: Optional[FuelPrices]) -> Optional[FuelPrices]:
    """Decide what to keep: ignore older posts and fill a missing change from the saved price.

    Returns None when the saved prices come from a newer post (so they should stay).
    """
    if previous is not None and previous.message_id > new.message_id:
        return None
    if previous is None or previous.message_id == new.message_id:
        return new
    changes = {}
    for fuel in (REGULAR, DIESEL):
        if getattr(new, f"{fuel}_change") is None:
            changes[f"{fuel}_change"] = getattr(new, fuel) - getattr(previous, fuel)
    if not changes:
        return new
    return FuelPrices(**{**new.as_dict(), **changes})


def fuel_prices_are_stale(prices: FuelPrices, today: date) -> bool:
    if prices.valid_to:
        try:
            return today > date.fromisoformat(prices.valid_to)
        except ValueError:
            pass
    reference = prices.valid_from or prices.posted_at[:10]
    try:
        return today - date.fromisoformat(reference) > FUEL_STALE_AFTER
    except ValueError:
        return True


def fuel_period_text(prices: FuelPrices) -> str:
    """"11–21 Nov", or "from 11 Nov" without an end date."""
    try:
        start = date.fromisoformat(prices.valid_from) if prices.valid_from else None
        end = date.fromisoformat(prices.valid_to) if prices.valid_to else None
    except ValueError:
        return ""
    if start and end:
        if start.month == end.month:
            return f"{start.day}–{end.day} {end.strftime('%b')}"
        return f"{start.day} {start.strftime('%b')}–{end.day} {end.strftime('%b')}"
    if start:
        return f"from {start.day} {start.strftime('%b')}"
    if prices.posted_at:
        try:
            posted = datetime.fromisoformat(prices.posted_at)
            return f"{posted.day} {posted.strftime('%b')}"
        except ValueError:
            return ""
    return ""


_KHMER_MONTH_NAMES = {number: name for name, number in KHMER_MONTHS.items()}


def fuel_period_khmer(prices: FuelPrices) -> str:
    """Owner-approved wording with Western digits, e.g. "អនុវត្តចាប់ពីថ្ងៃទី 11 ដល់ 21 ខែវិច្ឆិកា ឆ្នាំ2026"."""
    try:
        start = date.fromisoformat(prices.valid_from) if prices.valid_from else None
        end = date.fromisoformat(prices.valid_to) if prices.valid_to else None
    except ValueError:
        return ""
    if start is None:
        return ""
    month = _KHMER_MONTH_NAMES[start.month]
    if end is None:
        return f"អនុវត្តចាប់ពីថ្ងៃទី {start.day} ខែ{month} ឆ្នាំ{start.year}"
    end_month = _KHMER_MONTH_NAMES[end.month]
    if (start.year, start.month) == (end.year, end.month):
        return f"អនុវត្តចាប់ពីថ្ងៃទី {start.day} ដល់ {end.day} ខែ{month} ឆ្នាំ{end.year}"
    if start.year == end.year:
        return f"អនុវត្តចាប់ពីថ្ងៃទី {start.day} ខែ{month} ដល់ថ្ងៃទី {end.day} ខែ{end_month} ឆ្នាំ{end.year}"
    return (f"អនុវត្តចាប់ពីថ្ងៃទី {start.day} ខែ{month} ឆ្នាំ{start.year} "
            f"ដល់ថ្ងៃទី {end.day} ខែ{end_month} ឆ្នាំ{end.year}")
