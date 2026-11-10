"""Display-only formatting for posts from the private exchange group.

These helpers turn free-form exchange posts into compact rows for the
Dashboard's Private rates panel. They are deliberately independent of the
payment parser, payment storage, the bank registry used for speech, and the
audio queue: nothing produced here is persisted, announced, or treated as an
official rate. Ambiguous text is shown without a direction rather than guessed.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

RATE_MIN = Decimal("3800")
RATE_MAX = Decimal("4400")
SUMMARY_WINDOW = timedelta(minutes=15)
SENDER_NAME_LIMIT = 18

KHR_TO_USD = "KHR_TO_USD"
USD_TO_KHR = "USD_TO_KHR"
DIRECTION_LABELS = {KHR_TO_USD: "KHR→USD", USD_TO_KHR: "USD→KHR", None: "·"}
CURRENCY_CODES = {"$": "USD", "៛": "KHR"}

PHOTO_PLACEHOLDER = "[photo — see Telegram]"
NON_TEXT_PLACEHOLDER = "[non-text message]"
PLACEHOLDERS = frozenset({PHOTO_PLACEHOLDER, NON_TEXT_PLACEHOLDER})

_KHMER_DIGITS = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")
_PHONE = re.compile(
    r"(?<![\d,.])(?:\+?855[\s.-]?|0)\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?![\d,.])"
)
_CONTACT_HINT = re.compile(r"(?i)(?<![a-z])acc(?![a-z])|telegram|[☎☏📞📱]")
_PARENTHETICAL = re.compile(r"\(([^()]*)\)")
_MINIMUM_SIZE = re.compile(r"ទំហំ\s*ប្តូរ\s*(.+?)\s*ឡ(?:ើ|េី)ង")
_MILLION = re.compile(r"(\d+(?:[.,]\d+)?)\s*លាន")
_TOKEN = re.compile(
    r"(?P<million>\d+(?:[.,]\d+)?M៛)"
    r"|(?P<number>(?P<pre>\$\s?)?"
    r"(?P<num>\d{1,3}(?:[,.]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"(?P<suf>[$៛])?)"
    r"|(?P<latin>[A-Za-z]+)"
    r"|(?P<khmer>[ក-៚ៜ-៟៰-៿᧠-᧿]+)"
    r"|(?P<currency>[$៛])"
    r"|(?P<sep>[×/])"
)

# Display-only short names for group-chat spellings. This is intentionally
# separate from the payment bank registry, whose exact aliases govern speech.
_LATIN_WORDS = {
    "aba": "ABA",
    "acleda": "AC",
    "ac": "AC",
    "wing": "Wing",
    "amret": "Amret",
    "kb": "KB",
    "prasac": "KB",
    "cana": "Cana",
    "canadia": "Cana",
    "sathapana": "ស្ថាបនា",
    "free": "free",
}
_KHMER_BANKS = {"វីង": "Wing", "អម្រឹត": "Amret", "ស្ថាបនា": "ស្ថាបនា"}
_ANY_ACCOUNT_WORDS = ("គ្រប់កុង", "អីក៏បាន")
_KHMER_CURRENCY_WORDS = (
    ("លុយរៀល", " ៛ "),
    ("រៀល", " ៛ "),
    ("ដុល្លារ", " $ "),
    ("ដុល្លា", " $ "),
    ("ខ្មែរ", " ៛ "),
)
_VERB_SUFFIXES = ("ដូរ", "ដូ", "យក", "ទិញ")
_HAVE_SUFFIXES = ("មាន",)
_GIVE_WORDS = ("អោយ", "ឲ្យ")


@dataclass(frozen=True)
class _Token:
    kind: str  # bank, any, word, currency, rate, size, sep
    text: str
    currency: Optional[str] = None  # USD/KHR for currency tokens and marked sizes
    value: Optional[Decimal] = None
    prefixed: bool = False


@dataclass(frozen=True)
class RateRow:
    """One display row: an offer with a recognised rate, or a cleaned plain line."""

    direction: Optional[str] = None
    rates: tuple[str, ...] = ()
    sizes: tuple[str, ...] = ()
    banks: tuple[str, ...] = ()
    text: str = ""
    rate_values: tuple[Decimal, ...] = field(default=(), compare=False)

    @property
    def is_offer(self) -> bool:
        return bool(self.rates)

    @property
    def label(self) -> str:
        return DIRECTION_LABELS[self.direction]

    @property
    def rate_text(self) -> str:
        return " / ".join(self.rates) + " KHR" if self.rates else ""

    @property
    def size_text(self) -> str:
        return " ".join(self.sizes)

    @property
    def bank_text(self) -> str:
        return "·".join(self.banks)


@dataclass(frozen=True)
class FormattedPost:
    rows: tuple[RateRow, ...]
    notes: tuple[str, ...] = ()


def short_sender_name(name: object, limit: int = SENDER_NAME_LIMIT) -> str:
    """Return a compact sender label without emoji, roles, or phone fragments."""
    value = str(name or "")
    value = re.split(r"[(👉]", value, maxsplit=1)[0]
    value = _remove_symbols(value)
    value = re.sub(r"(?<!\d)\d{3,}(?!\d)", " ", value)
    value = " ".join(value.split()).strip(" -:_|")
    if not value:
        return "Unknown sender"
    counted = 0
    for index, char in enumerate(value):
        if not unicodedata.category(char).startswith("M"):
            counted += 1
            if counted > limit:
                return value[:index].rstrip() + "…"
    return value


def format_rate_post(text: object) -> FormattedPost:
    """Convert one raw group post into compact, display-only rows."""
    raw = str(text or "").strip()
    if not raw:
        return FormattedPost((RateRow(text="…"),))
    if raw in PLACEHOLDERS:
        return FormattedPost((RateRow(text=raw),))

    notes: list[str] = []
    blocks: list[list[str]] = [[]]
    for original_line in raw.replace("​", " ").splitlines():
        line = _clean_line(original_line, notes)
        if line is None:
            continue
        if not line:
            if blocks[-1]:
                blocks.append([])
            continue
        blocks[-1].append(line)

    rows: list[RateRow] = []
    for block in blocks:
        pending: list[list[_Token]] = []
        for line in block:
            if _is_receiving_bank_list(line):
                continue
            tokens = _tokenize(line)
            if not tokens:
                continue
            if any(token.kind == "rate" for token in tokens):
                rows.append(_offer_row([token for group in pending for token in group] + tokens))
                pending = []
            else:
                pending.append(tokens)
        rows.extend(_plain_row(tokens) for tokens in pending)
    rows = [row for row in rows if row.is_offer or row.text]
    if not rows and not notes:
        rows = [RateRow(text="…")]
    return FormattedPost(tuple(rows), tuple(dict.fromkeys(notes)))


def summarize_rates(
    posts: Iterable[tuple[datetime, FormattedPost]],
    now: Optional[datetime] = None,
    window: timedelta = SUMMARY_WINDOW,
) -> dict[str, tuple[Decimal, Decimal]]:
    """Return the low/high tagged rate per direction from recent posts only."""
    current = _as_utc(now or datetime.now(timezone.utc))
    values: dict[str, list[Decimal]] = {KHR_TO_USD: [], USD_TO_KHR: []}
    for posted_at, post in posts:
        posted = _as_utc(posted_at)
        if posted > current or current - posted > window:
            continue
        for row in post.rows:
            if row.direction in values and len(row.rate_values) == 1:
                values[row.direction].append(row.rate_values[0])
    return {
        direction: (min(found), max(found))
        for direction, found in values.items()
        if found
    }


def format_summary_range(bounds: Optional[tuple[Decimal, Decimal]]) -> str:
    if not bounds:
        return "—"
    low, high = (_display_decimal(value) for value in bounds)
    return low if low == high else f"{low}–{high}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _remove_symbols(value: str) -> str:
    return "".join(
        " " if unicodedata.category(char) == "So"
        else "" if char in "‍⃣" or "︀" <= char <= "️"
        else char
        for char in value
    )


def _clean_line(line: str, notes: list[str]) -> Optional[str]:
    """Remove contact details and notes; return None when nothing should remain."""
    has_contact = bool(_PHONE.search(line) or _CONTACT_HINT.search(line))
    line = _PHONE.sub(" ", line.translate(_KHMER_DIGITS))
    line = _remove_symbols(line)
    if has_contact and not re.search(r"\d", line):
        return None

    def keep_note(match: re.Match) -> str:
        note = _format_note(match.group(1))
        if note:
            notes.append(note)
        return " "

    line = _PARENTHETICAL.sub(keep_note, line)
    return " ".join(line.split())


def _format_note(text: str) -> str:
    minimum = _MINIMUM_SIZE.search(text)
    if minimum:
        sizes = [token.text for token in _tokenize(minimum.group(1)) if token.kind == "size"]
        if sizes:
            return f"min {sizes[0]}"
    return _join_tokens(_tokenize(text))


def _is_receiving_bank_list(line: str) -> bool:
    stripped = line.lstrip(" >-–—•·:")
    return stripped.startswith("យក") and not re.search(r"\d", stripped)


def _normalize(line: str) -> str:
    line = line.replace("អីក៍បាន", "អីក៏បាន")
    line = _MILLION.sub(r" \1M៛ ", line)
    for word, replacement in _KHMER_CURRENCY_WORDS:
        line = line.replace(word, replacement)
    for word, replacement in _KHMER_BANKS.items():
        line = line.replace(word, f" {replacement} ")
    for word in _ANY_ACCOUNT_WORDS:
        line = line.replace(word, f" {word} ")
    line = re.sub(r"(?i)\bKB\s*PRASAC\b", "KB", line)
    line = re.sub(r"\${2,}", "$", line)
    line = re.sub(r"\*+|=", " × ", line)
    line = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", " × ", line)
    line = re.sub(r"(?<=\d)\s*[rR](?![A-Za-z])", "៛", line)
    line = re.sub(r"(?<![A-Za-z])R(?![A-Za-z])", " ៛ ", line)
    return line


def _segment_latin(run: str) -> Optional[list[str]]:
    lowered = run.lower()
    if not lowered:
        return []
    for size in range(len(lowered), 0, -1):
        word = _LATIN_WORDS.get(lowered[:size])
        if word is None:
            continue
        rest = _segment_latin(run[size:])
        if rest is not None:
            return [word, *rest]
    return None


def _number_parts(number: str) -> tuple[Decimal, int, bool]:
    grouped = re.fullmatch(r"(\d{1,3}(?:[,.]\d{3})+)(?:[.,](\d{1,2}))?", number)
    if grouped:
        integer, cents, thousands = re.sub(r"[,.]", "", grouped.group(1)), grouped.group(2), True
    else:
        plain = re.fullmatch(r"(\d+)(?:[.,](\d{1,2}))?", number)
        integer, cents, thousands = plain.group(1), plain.group(2), False
    try:
        value = Decimal(f"{integer}.{cents}" if cents else integer)
    except InvalidOperation:
        value = Decimal(0)
    return value, len(integer.lstrip("0") or "0"), thousands


def _display_decimal(value: Decimal) -> str:
    text = f"{value.normalize():f}"
    return text


def _size_text(value: Decimal, currency: Optional[str]) -> str:
    number = f"{int(value):,}" if value == value.to_integral_value() else f"{value:,}"
    return f"{number} {currency}" if currency in {"USD", "KHR"} else number


def _tokenize(line: str) -> list[_Token]:
    tokens: list[_Token] = []
    for match in _TOKEN.finditer(_normalize(line)):
        if match.group("million"):
            million = match.group("million").replace(",", ".").replace("M៛", "M KHR")
            tokens.append(_Token("size", million, "KHR", prefixed=False))
        elif match.group("number"):
            tokens.extend(_number_tokens(match))
        elif match.group("latin"):
            words = _segment_latin(match.group("latin"))
            if words is None:
                tokens.append(_Token("word", match.group("latin")))
            else:
                tokens.extend(_Token("word" if word == "free" else "bank", word) for word in words)
        elif match.group("khmer"):
            word = match.group("khmer")
            if word in _KHMER_BANKS.values():
                tokens.append(_Token("bank", word))
            elif word in _ANY_ACCOUNT_WORDS:
                tokens.append(_Token("any", word))
            else:
                tokens.append(_Token("word", word))
        elif match.group("currency"):
            symbol = match.group("currency")
            tokens.append(_Token("currency", symbol, "USD" if symbol == "$" else "KHR"))
        elif match.group("sep"):
            tokens.append(_Token("sep", match.group("sep")))
    return tokens


def _number_tokens(match: re.Match) -> list[_Token]:
    value, integer_digits, thousands = _number_parts(match.group("num"))
    prefix = bool(match.group("pre"))
    attached_prefix = match.group("pre") == "$"
    suffix = match.group("suf")
    # "$4,000" (dollar sign touching a grouped number) is a trade size; "$ 4,089"
    # or "$4089" after an exchange verb is the rate written beside the currency.
    is_rate = (
        integer_digits == 4
        and RATE_MIN <= value <= RATE_MAX
        and suffix != "$"
        and not (attached_prefix and thousands)
    )
    if is_rate:
        rate = _Token("rate", _display_decimal(value), value=value)
        return [_Token("currency", "$", "USD"), rate] if prefix else [rate]
    currency = "USD" if prefix or suffix == "$" else "KHR" if suffix == "៛" else None
    if currency is None and value < 1000:
        return [_Token("word", match.group(0).strip())]
    return [_Token("size", _size_text(value, currency), currency, value, prefixed=prefix)]


def _ends_with(word: str, endings: tuple[str, ...]) -> bool:
    return any(word.endswith(ending) for ending in endings)


def _direction(tokens: list[_Token]) -> Optional[str]:
    offered: set[str] = set()
    wanted: set[str] = set()
    consumed: set[int] = set()
    for index, token in enumerate(tokens):
        if token.kind == "word" and any(word in token.text for word in _GIVE_WORDS):
            return None
        if token.kind == "word" and (
            _ends_with(token.text, _VERB_SUFFIXES) or _ends_with(token.text, _HAVE_SUFFIXES)
        ):
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            currency = None
            if following is not None and following.kind == "currency":
                currency = following.currency
            elif following is not None and following.kind == "size" and following.prefixed:
                currency = following.currency
            if currency:
                consumed.add(index + 1)
                if _ends_with(token.text, _HAVE_SUFFIXES):
                    offered.add(currency)
                else:
                    wanted.add(currency)
        elif token.kind == "currency" and index not in consumed:
            offered.add(token.currency or "")
    directions = {KHR_TO_USD if currency == "KHR" else USD_TO_KHR for currency in offered}
    directions |= {KHR_TO_USD if currency == "USD" else USD_TO_KHR for currency in wanted}
    return directions.pop() if len(directions) == 1 else None


def _offer_row(tokens: list[_Token]) -> RateRow:
    rates = [token for token in tokens if token.kind == "rate"]
    direction = _direction(tokens) if len(rates) == 1 else None
    sizes = tuple(dict.fromkeys(token.text for token in tokens if token.kind == "size"))
    banks = tuple(dict.fromkeys(token.text for token in tokens if token.kind in {"bank", "any"}))
    return RateRow(
        direction=direction,
        rates=tuple(token.text for token in rates),
        sizes=sizes,
        banks=banks,
        text=_join_tokens(tokens),
        rate_values=tuple(token.value for token in rates if token.value is not None),
    )


def _plain_row(tokens: list[_Token]) -> RateRow:
    return RateRow(text=_join_tokens(tokens))


def _join_tokens(tokens: list[_Token]) -> str:
    parts = [
        f"{token.text} KHR" if token.kind == "rate"
        else CURRENCY_CODES.get(token.text, token.text) if token.kind == "currency"
        else token.text
        for token in tokens
    ]
    return " ".join(part for part in parts if part).strip()
