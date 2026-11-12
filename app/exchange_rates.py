import json
import logging
import re
import ssl
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Callable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CAMBODIA_TIMEZONE = timezone(timedelta(hours=7), "ICT")
RATE_REFRESH_INTERVAL_SECONDS = 15 * 60
RATE_SOURCE_TIMEOUT_SECONDS = 5
RATE_STALE_AFTER = timedelta(hours=24)
# NBC publishes no rate on weekends/holidays; its last published rate stays current this long.
NBC_STALE_AFTER = timedelta(days=4)
NBC_NOT_PUBLISHED_MESSAGE = "NBC official USD/KHR reference rate was not found"
MAX_PAGE_BYTES = 2_000_000
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateSource:
    key: str
    category: str
    url: str


RATE_SOURCES = (
    RateSource(
        "NBC",
        "Official reference rate",
        "https://nbc.gov.kh/en/statistics/exchange-rate",
    ),
    RateSource(
        "ACLEDA",
        "Notes",
        "https://www.acledabank.com.kh/kh/eng/ps_cmforeignexchange?t=p",
    ),
    RateSource(
        "WING",
        "Telegraphic Transfer Outbound",
        "https://www.wingbank.com.kh/en/exchange-rate",
    ),
)
GOLD_SOURCE = RateSource(
    "GOLD",
    "XAU/USD spot",
    "https://www.goldapi.io/api/price/XAU/USD",
)
# Official USD/CNY central parity (人民币汇率中间价), published by CFETS under PBOC authority each
# China working day at 9:15 Beijing time.
CNY_SOURCE = RateSource(
    "CNY",
    "PBOC central parity",
    "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json",
)
# chinamoney.com.cn does not send its intermediate certificate. This public intermediate (issued by
# UCA Global G2 Root, which Windows trusts; valid to 2035) completes the chain; verification and the
# hostname check stay fully on. Used only for CFETS requests.
CFETS_INTERMEDIATE_CERT = Path(__file__).resolve().parent.parent / "assets" / "certs" / "sheca_ov_tls_rsa_ca_a1.pem"
CNY_RATE_MIN = Decimal("5")
CNY_RATE_MAX = Decimal("10")
GOLD_REFRESH_INTERVAL = timedelta(hours=12)
TROY_OUNCE_GRAMS = Decimal("31.1034768")
DAMLUNG_GRAMS = Decimal("37.5")
CHI_GRAMS = Decimal("3.75")
_NUMBER = re.compile(r"^[\d,]+(?:\.\d+)?$")


@dataclass(frozen=True)
class ExchangeRate:
    source: str
    category: str
    official_rate: Optional[Decimal]
    buy_rate: Optional[Decimal]
    sell_rate: Optional[Decimal]
    effective_at: str
    fetched_at: Optional[datetime]
    last_error: Optional[str] = None
    previous_official_rate: Optional[Decimal] = None
    previous_buy_rate: Optional[Decimal] = None
    previous_sell_rate: Optional[Decimal] = None

    def trend(self, field: str) -> Optional[str]:
        """Return "up"/"down" against the previous different value of official/buy/sell."""
        return rate_trend(
            getattr(self, f"{field}_rate", None),
            getattr(self, f"previous_{field}_rate", None),
        )

    def is_stale(self, now: datetime) -> bool:
        if self.last_error or self.fetched_at is None:
            return True
        fetched_at = _as_cambodia_datetime(self.fetched_at)
        current = _as_cambodia_datetime(now)
        limit = NBC_STALE_AFTER if self.source == "NBC" else RATE_STALE_AFTER
        return current < fetched_at or current - fetched_at > limit


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.rows: list[list[str]] = []
        self._ignored_depth = 0
        self._row: Optional[list[str]] = None
        self._cell_parts: Optional[list[str]] = None

    def handle_starttag(self, tag: str, _: list[tuple[str, Optional[str]]]) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif not self._ignored_depth:
            if tag == "tr":
                self._row = []
            elif tag in {"td", "th"} and self._row is not None:
                self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth:
            if tag in {"td", "th"} and self._cell_parts is not None and self._row is not None:
                self._row.append(_collapse("".join(self._cell_parts)))
                self._cell_parts = None
            elif tag == "tr" and self._row is not None:
                if self._row:
                    self.rows.append(self._row)
                self._row = None
                self.text_parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        self.text_parts.append(data)
        if self._cell_parts is not None:
            self._cell_parts.append(data)


def _collapse(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _as_cambodia_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=CAMBODIA_TIMEZONE)
    return value.astimezone(CAMBODIA_TIMEZONE)


def _parse_number(value: str) -> Decimal:
    candidate = _collapse(value).replace("KHR", "").strip()
    if not _NUMBER.fullmatch(candidate):
        raise ValueError(f"Invalid exchange-rate number: {value!r}")
    try:
        return Decimal(candidate.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid exchange-rate number: {value!r}") from exc


def _parse_table_pair(rows: list[list[str]], pair: str) -> tuple[Decimal, Decimal]:
    for row in rows:
        if not any(re.sub(r"\s+", "", cell).upper() == pair for cell in row):
            continue
        values = []
        for cell in row:
            candidate = _collapse(cell).replace("KHR", "").strip()
            if _NUMBER.fullmatch(candidate):
                values.append(_parse_number(candidate))
        if len(values) >= 2:
            return values[-2], values[-1]
    raise ValueError(f"USD/KHR buy and sell rates were not found in the {pair} table")


def _page_content(html: str) -> tuple[str, list[list[str]]]:
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    return _collapse(" ".join(parser.text_parts)), parser.rows


def _rate(
    source: str,
    category: str,
    *,
    official_rate: Optional[Decimal] = None,
    buy_rate: Optional[Decimal] = None,
    sell_rate: Optional[Decimal] = None,
    effective_at: str,
    fetched_at: Optional[datetime] = None,
) -> ExchangeRate:
    return ExchangeRate(
        source=source,
        category=category,
        official_rate=official_rate,
        buy_rate=buy_rate,
        sell_rate=sell_rate,
        effective_at=effective_at,
        fetched_at=_as_cambodia_datetime(fetched_at or datetime.now(CAMBODIA_TIMEZONE)),
    )


def parse_nbc_page(html: str, fetched_at: Optional[datetime] = None) -> ExchangeRate:
    text, _ = _page_content(html)
    match = re.search(
        r"(?P<date>(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4}))"
        r"\s*\|\s*Official rate:\s*(?P<rate>[\d,]+(?:\.\d+)?)\s*Riel\s*/\s*US Dollar",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(NBC_NOT_PUBLISHED_MESSAGE)
    return _rate(
        "NBC",
        "Official reference rate",
        official_rate=_parse_number(match.group("rate")),
        effective_at=match.group("date"),
        fetched_at=fetched_at,
    )


def parse_acleda_page(html: str, fetched_at: Optional[datetime] = None) -> ExchangeRate:
    text, rows = _page_content(html)
    effective = re.search(
        r"Exchange Rate\s+as of\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}"
        r"(?:\s+\d{1,2}:\d{2}\s*[AP]M)?)",
        text,
        re.IGNORECASE,
    )
    if not effective:
        raise ValueError("ACLEDA exchange-rate effective date/time was not found")
    buy, sell = _parse_table_pair(rows, "USD/KHR")
    return _rate(
        "ACLEDA",
        "Notes",
        buy_rate=buy,
        sell_rate=sell,
        effective_at=effective.group(1),
        fetched_at=fetched_at,
    )


def parse_wing_page(html: str, fetched_at: Optional[datetime] = None) -> ExchangeRate:
    text, rows = _page_content(html)
    effective = re.search(r"As of\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", text, re.IGNORECASE)
    if not effective:
        raise ValueError("Wing Bank exchange-rate effective date was not found")
    buy, sell = _parse_table_pair(rows, "USD/KHR")
    return _rate(
        "WING",
        "Telegraphic Transfer Outbound",
        buy_rate=buy,
        sell_rate=sell,
        effective_at=effective.group(1),
        fetched_at=fetched_at,
    )


_PARSERS: dict[str, Callable[[str, Optional[datetime]], ExchangeRate]] = {
    "NBC": parse_nbc_page,
    "ACLEDA": parse_acleda_page,
    "WING": parse_wing_page,
}


def fetch_rate(source: RateSource, timeout: int = RATE_SOURCE_TIMEOUT_SECONDS) -> ExchangeRate:
    request = Request(
        source.url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content = response.read(MAX_PAGE_BYTES + 1)
        charset = response.headers.get_content_charset() or "utf-8"
    if len(content) > MAX_PAGE_BYTES:
        raise ValueError(f"{source.key} exchange-rate page exceeded the size limit")
    html = content.decode(charset, errors="replace")
    return _PARSERS[source.key](html, datetime.now(CAMBODIA_TIMEZONE))


def _cny_rate(value: str, day: datetime, fetched_at: Optional[datetime]) -> ExchangeRate:
    rate = Decimal(value)
    if not CNY_RATE_MIN <= rate <= CNY_RATE_MAX:
        raise ValueError("USD/CNY central parity is outside the expected range")
    return ExchangeRate(
        CNY_SOURCE.key, CNY_SOURCE.category, rate, None, None,
        f"{day.day} {day.strftime('%B %Y')}", fetched_at or datetime.now(CAMBODIA_TIMEZONE),
    )


def parse_cny_parity_json(text: str, fetched_at: Optional[datetime] = None) -> ExchangeRate:
    """CFETS ccpr.json: data.lastDate "2026-11-12 9:15" and records[] with vrtEName "USD/CNY"."""
    try:
        payload = json.loads(text)
        last_date = str(payload["data"]["lastDate"]).split()[0]
        day = datetime.strptime(last_date, "%Y-%m-%d")
        record = next(item for item in payload["records"] if str(item.get("vrtEName", "")).upper() == "USD/CNY")
        return _cny_rate(str(record["price"]), day, fetched_at)
    except (KeyError, TypeError, ValueError, StopIteration, InvalidOperation) as exc:
        raise ValueError("USD/CNY central parity was not found in the CFETS data") from exc


def _cfets_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if CFETS_INTERMEDIATE_CERT.is_file():
        context.load_verify_locations(cafile=str(CFETS_INTERMEDIATE_CERT))
    return context


def _fetch_text(url: str, timeout: int, context: Optional[ssl.SSLContext] = None) -> str:
    request = Request(url, headers={"User-Agent": "ABA-Payment-Speaker/1.0 (rates display)"})
    with urlopen(request, timeout=timeout, context=context) as response:
        content = response.read(MAX_PAGE_BYTES + 1)
        charset = response.headers.get_content_charset() or "utf-8"
    if len(content) > MAX_PAGE_BYTES:
        raise ValueError("USD/CNY source exceeded the size limit")
    return content.decode(charset, errors="replace")


def fetch_cny_parity(timeout: int = RATE_SOURCE_TIMEOUT_SECONDS) -> ExchangeRate:
    """Official USD/CNY central parity from the CFETS data feed (certificate-verified)."""
    return parse_cny_parity_json(_fetch_text(CNY_SOURCE.url, timeout, _cfets_context()))


def parse_gold_response(payload: bytes, fetched_at: Optional[datetime] = None) -> ExchangeRate:
    """Parse a GoldAPI.io XAU/USD response into a USD-per-troy-ounce gold price."""
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict) or data.get("metal") not in (None, "XAU") or data.get("currency") not in (None, "USD"):
        raise ValueError("GOLD response is not XAU/USD")
    try:
        price = Decimal(str(data["price"]))
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise ValueError("GOLD response has no valid price") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError("GOLD response has no valid price")
    effective = ""
    timestamp = data.get("timestamp")
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        effective = datetime.fromtimestamp(timestamp, CAMBODIA_TIMEZONE).strftime("%d %b %Y %H:%M")
    return ExchangeRate(
        source="GOLD",
        category=GOLD_SOURCE.category,
        official_rate=price.quantize(Decimal("0.01")),
        buy_rate=None,
        sell_rate=None,
        effective_at=effective,
        fetched_at=fetched_at or datetime.now(CAMBODIA_TIMEZONE),
    )


def fetch_gold_price(api_key: str, timeout: int = RATE_SOURCE_TIMEOUT_SECONDS) -> ExchangeRate:
    """Fetch the gold price with the owner's private key (sent as a header, never logged)."""
    request = Request(
        GOLD_SOURCE.url,
        headers={"x-access-token": api_key, "Accept": "application/json", "User-Agent": "ABA-Payment-Speaker/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        content = response.read(MAX_PAGE_BYTES + 1)
    if len(content) > MAX_PAGE_BYTES:
        raise ValueError("GOLD response exceeded the size limit")
    return parse_gold_response(content)


def gold_refresh_due(cached: Optional["ExchangeRate"], now: datetime) -> bool:
    """Refresh gold only when the cached price is missing or at least 12 hours old."""
    if cached is None or cached.fetched_at is None or cached.official_rate is None:
        return True
    fetched_at = _as_cambodia_datetime(cached.fetched_at)
    current = _as_cambodia_datetime(now)
    return current < fetched_at or current - fetched_at >= GOLD_REFRESH_INTERVAL


def gold_local_units(price_per_ounce: Decimal) -> tuple[Decimal, Decimal]:
    """Convert USD per troy ounce to USD per ដំឡឹង (37.5 g) and per ជី (3.75 g)."""
    per_gram = price_per_ounce / TROY_OUNCE_GRAMS
    return (
        (per_gram * DAMLUNG_GRAMS).quantize(Decimal("0.01")),
        (per_gram * CHI_GRAMS).quantize(Decimal("0.01")),
    )


def load_rate_rows(store) -> dict[str, ExchangeRate]:
    return {row["source"]: rate_from_record(row) for row in store.load_exchange_rates()}


def rate_from_record(row: dict[str, object]) -> ExchangeRate:
    fetched = row.get("fetched_at")
    fetched_at = datetime.fromisoformat(str(fetched)) if fetched else None
    return ExchangeRate(
        source=str(row["source"]),
        category=str(row["category"]),
        official_rate=_record_decimal(row.get("official_rate")),
        buy_rate=_record_decimal(row.get("buy_rate")),
        sell_rate=_record_decimal(row.get("sell_rate")),
        effective_at=str(row.get("effective_at") or ""),
        fetched_at=fetched_at,
        last_error=str(row["last_error"]) if row.get("last_error") else None,
        previous_official_rate=_record_decimal(row.get("previous_official_rate")),
        previous_buy_rate=_record_decimal(row.get("previous_buy_rate")),
        previous_sell_rate=_record_decimal(row.get("previous_sell_rate")),
    )


def _record_decimal(value: object) -> Optional[Decimal]:
    return Decimal(str(value)) if value is not None else None


def rate_trend(current: Optional[Decimal], previous: Optional[Decimal]) -> Optional[str]:
    if current is None or previous is None or current == previous:
        return None
    return "up" if current > previous else "down"


def _display_number(value: Decimal) -> str:
    formatted = f"{value:,f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def format_rate_value(value: Decimal) -> str:
    return _display_number(value)


def compact_effective_at(value: str) -> str:
    formats = (
        "%B %d, %Y %I:%M %p",
        "%B %d %Y %I:%M %p",
        "%d %B %Y",
        "%d %b %Y",
        "%d %b %Y %H:%M",
    )
    for date_format in formats:
        try:
            effective = datetime.strptime(value.strip(), date_format)
        except ValueError:
            continue
        compact = f"{effective.day} {effective:%b}"
        if "%H" in date_format or "%I" in date_format:
            compact += f" {effective:%H:%M}"
        return compact
    return value


def format_rate_display_values(
    source: str,
    rate: Optional[ExchangeRate],
    now: datetime,
) -> tuple[str, str, str, str]:
    if rate is None:
        return "UNAVAILABLE", "", "", ""

    effective = compact_effective_at(rate.effective_at) if rate.effective_at else ""
    if rate.is_stale(now):
        effective = f"{effective} · STALE" if effective else "STALE"

    if source == "NBC":
        if rate.official_rate is None:
            return "UNAVAILABLE", "", "", effective
        return format_rate_value(rate.official_rate), "", "", effective

    if rate.buy_rate is None or rate.sell_rate is None:
        return "UNAVAILABLE", "", "", effective
    return "", format_rate_value(rate.buy_rate), format_rate_value(rate.sell_rate), effective


def format_rate_row(source: str, rate: Optional[ExchangeRate], now: datetime) -> str:
    labels = {"NBC": "NBC OFFICIAL", "ACLEDA": "ACLEDA NOTES", "WING": "WING TELEGRAPHIC TRANSFER OUTBOUND"}
    label = labels.get(source, source)
    if rate is None or all(value is None for value in (rate.official_rate, rate.buy_rate, rate.sell_rate)):
        return f"{label}\nUNAVAILABLE"
    if rate.official_rate is not None:
        values = f"{_display_number(rate.official_rate)} KHR/USD"
    elif rate.buy_rate is not None and rate.sell_rate is not None:
        values = f"B {_display_number(rate.buy_rate)} / S {_display_number(rate.sell_rate)} KHR/USD"
    else:
        values = "UNAVAILABLE"
    stale = " · STALE" if rate.is_stale(now) else ""
    effective = f" · {rate.effective_at}" if rate.effective_at else ""
    return f"{label}\n{values}{effective}{stale}"


def format_rate_status(rates: dict[str, ExchangeRate], now: datetime) -> str:
    if not rates:
        return "KHR per USD · loading rates"
    if all(rate.official_rate is None and rate.buy_rate is None and rate.sell_rate is None for rate in rates.values()):
        return "KHR per USD · rates unavailable"
    fetched = [rate.fetched_at for rate in rates.values() if rate.fetched_at is not None]
    if not fetched:
        return "KHR per USD · rates unavailable"
    latest = max(_as_cambodia_datetime(value) for value in fetched)
    age = max(timedelta(0), _as_cambodia_datetime(now) - latest)
    minutes = int(age.total_seconds() // 60)
    age_label = "less than 1m ago" if minutes == 0 else f"{minutes}m ago"
    failed = any(rate.last_error for rate in rates.values())
    return f"KHR per USD · checked {age_label}" + (" · source issue" if failed else "")


class ExchangeRateMonitor:
    def __init__(
        self,
        store,
        publish: Callable[[dict[str, ExchangeRate]], None],
        interval: int = RATE_REFRESH_INTERVAL_SECONDS,
        gold_api_key: str = "",
        clock: Callable[[], datetime] = lambda: datetime.now(CAMBODIA_TIMEZONE),
    ):
        self.store = store
        self.publish = publish
        self.interval = interval
        self.gold_api_key = gold_api_key
        self.clock = clock
        self._gold_retry_after: Optional[datetime] = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="exchange-rate-refresh", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def refresh_once(self) -> dict[str, ExchangeRate]:
        for source in (*RATE_SOURCES, CNY_SOURCE):
            try:
                rate = fetch_cny_parity() if source is CNY_SOURCE else fetch_rate(source)
            except ValueError as exc:
                if source.key == "NBC" and str(exc) == NBC_NOT_PUBLISHED_MESSAGE:
                    # Weekends/holidays: NBC shows no new rate; keep the last published one current.
                    logger.info("NBC has no newly published rate; keeping the last published rate")
                    try:
                        self.store.clear_exchange_rate_error(source.key)
                    except Exception:
                        logger.exception("Could not clear NBC error state")
                    continue
                logger.warning("Exchange-rate source %s refresh failed: %s", source.key, exc)
                try:
                    self.store.mark_exchange_rate_error(source.key, source.category, str(exc)[:200])
                except Exception:
                    logger.exception("Could not save exchange-rate error state for %s", source.key)
                continue
            except (HTTPError, URLError, TimeoutError, OSError, UnicodeError) as exc:
                logger.warning("Exchange-rate source %s refresh failed: %s", source.key, exc)
                try:
                    self.store.mark_exchange_rate_error(source.key, source.category, str(exc)[:200])
                except Exception:
                    logger.exception("Could not save exchange-rate error state for %s", source.key)
                continue
            try:
                self.store.save_exchange_rate(rate)
            except Exception:
                logger.exception("Could not cache exchange rate from %s", source.key)
        self._refresh_gold()
        try:
            rates = load_rate_rows(self.store)
        except Exception:
            logger.exception("Could not load cached exchange rates")
            return {}
        self.publish(rates)
        return rates

    def _refresh_gold(self) -> None:
        """Fetch gold at most every 12 hours (free daily quota), retrying failures hourly."""
        if not self.gold_api_key:
            return
        now = self.clock()
        if self._gold_retry_after is not None and now < self._gold_retry_after:
            return
        try:
            cached = load_rate_rows(self.store).get("GOLD")
        except Exception:
            logger.exception("Could not read cached gold price")
            return
        if not gold_refresh_due(cached, now):
            return
        try:
            rate = fetch_gold_price(self.gold_api_key)
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeError, ValueError) as exc:
            reason = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
            logger.warning("Gold price refresh failed: %s", reason)
            self._gold_retry_after = now + timedelta(hours=1)
            try:
                self.store.mark_exchange_rate_error(GOLD_SOURCE.key, GOLD_SOURCE.category, reason)
            except Exception:
                logger.exception("Could not save gold error state")
            return
        self._gold_retry_after = None
        try:
            self.store.save_exchange_rate(rate)
        except Exception:
            logger.exception("Could not cache gold price")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh_once()
            except Exception:
                logger.exception("Unexpected exchange-rate refresh failure")
            if self._stop.wait(self.interval):
                break

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=18)
