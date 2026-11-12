import json
import math
import os
import queue
import tkinter as tk
import tkinter.font as tkfont
from ctypes import Structure, WINFUNCTYPE, byref, sizeof, windll
from ctypes.wintypes import BOOL, DWORD, HDC, HMONITOR, LPARAM, RECT
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Callable, Iterable, Optional

from .exchange_rates import (
    CAMBODIA_TIMEZONE,
    ExchangeRate,
    compact_effective_at,
    format_rate_display_values,
    format_rate_status,
    format_rate_value,
    gold_local_units,
    rate_trend,
)
from .fuel_prices import FuelPrices, fuel_period_khmer, fuel_prices_are_stale
from .models import ParserStatus
from .payment_parser import build_announcement, parse_payment
from .rate_post_format import (
    DIRECTION_LABELS,
    KHR_TO_USD,
    USD_TO_KHR,
    format_rate_post,
    format_summary_range,
    short_sender_name,
    summarize_rates,
)

SPEAKER_TEST = "ប្រព័ន្ធប្រកាសការទូទាត់កំពុងដំណើរការ។"
SAMPLE_A = "៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253."
SAMPLE_B = "$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850."

COLORS = {
    "background": "#070D1A", "surface": "#101827", "surface_alt": "#151F32",
    "border": "#25324A", "text": "#F8FAFC", "muted": "#94A3B8",
    "green": "#35E58B", "green_dark": "#123D2B", "blue": "#5DA9FF",
    "blue_dark": "#122C4B", "purple": "#B78AFF", "purple_dark": "#302052",
    "amber": "#FBBF24", "usd": "#F6C85F", "usd_flash": "#FFF0B8",
    "red": "#FB7185", "button": "#22304A", "rate_background": "#FFE66D", "rate_text": "#173B70",
}

RATE_PULSE_INTERVAL_MS = 100
RATE_PULSE_STEPS = 24
RATE_PULSE_COLORS = {
    "NBC": ("#F8FAFC", "#B9E8FF"),
    "buy": ("#FB7185", "#FFB7C0"),
    "sell": ("#5DA9FF", "#B8E7FF"),
    "gold": ("#F6C85F", "#FFF0B8"),
}
RATE_ROW_COLORS = {
    "NBC": "#182438",
    "ACLEDA": "#193138",
    "WING": "#28243A",
    "GOLD": "#2E2716",
}
RATE_TABLE_SOURCES = ("ACLEDA", "WING", "GOLD")
NBC_CARD_HEIGHTS = {False: 132, True: 112}
NBC_CARD_FILL = "#0E1626"
NBC_BORDER_GRADIENT = ("#22D3EE", "#8B5CF6")
NBC_PILL_COLORS = {"up": ("#0F3B2A", "#4ADE80"), "down": ("#3A3010", "#FACC15"), "flat": ("#1B2436", "#94A3B8")}
NBC_FIGURE_COLORS = {"up": "#4ADE80", "down": "#FACC15"}
NBC_CARD_TITLE = "អត្រាប្តូរប្រាក់ធនាគារជាតិ"
RATE_TABLE_HEADER_BG = "#22304A"
HISTORY_ROW_HEIGHT = 44
HISTORY_ROW_HEIGHT_TWO_LINES = 68
# AMOUNT right, SENDER left, BANK centred, TIME right (owner-approved 2026-11-12).
HISTORY_COLUMN_ANCHORS = ("e", "w", "center", "e")
HISTORY_COLUMN_JUSTIFY = ("right", "left", "center", "right")
# Scrolling ticker beside the DASHBOARD / SETTINGS tabs: today's totals and Ministry fuel prices.
TICKER_INTERVAL_MS = 40
TICKER_STEP_PX = 1.6  # about 40 px per second
TICKER_GAP_PX = 90
TICKER_FONT_SIZE = 12


def rounded_rect_path(x0: float, y0: float, x1: float, y1: float, radius: float, steps: int = 8) -> list[tuple[float, float]]:
    """Points around a rounded rectangle, clockwise from the top-left arc."""
    radius = max(0.0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    corners = (
        (x0 + radius, y0 + radius, 180),
        (x1 - radius, y0 + radius, 270),
        (x1 - radius, y1 - radius, 0),
        (x0 + radius, y1 - radius, 90),
    )
    points = []
    for cx, cy, start in corners:
        for step in range(steps + 1):
            angle = math.radians(start + 90 * step / steps)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def format_gold_price(value: Decimal) -> str:
    return f"${value:,.2f}"


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
NBC_LOGO_PATH = ASSETS_DIR / "nbc_logo.png"
NBC_LOGO_HEIGHTS = {False: 40, True: 30}
BANK_LOGO_HEIGHTS = {False: 60, True: 44}
BANK_LOGO_FILES = {"ACLEDA": "acleda_logo_{}.png", "WING": "wing_logo_{}.png"}
# Currency coin icons (green KHR ៛, gold USD $) shown before the payment amount.
NOTE_HEIGHTS = (64, 60, 56, 52, 48, 44, 40, 36, 32, 28, 24, 22)
NOTE_TO_DIGIT_RATIO = 1.1
NOTE_FILES = {"KHR": "coin_khr_{}.png", "USD": "coin_usd_{}.png"}
AMOUNT_NOTE_GAP = 14


def load_asset_image(root, name: str) -> Optional[tk.PhotoImage]:
    """Load a pre-sized PNG from assets/; missing or unreadable files simply return None."""
    path = ASSETS_DIR / name
    try:
        return tk.PhotoImage(master=root, file=str(path)) if path.is_file() else None
    except tk.TclError:
        return None


def note_height_for(digit_height: int) -> int:
    """Largest prepared banknote height that does not exceed the digit height."""
    return next((height for height in NOTE_HEIGHTS if height <= digit_height), NOTE_HEIGHTS[-1])


def format_payment_digits(amount: object, currency: object) -> str:
    """Amount without the currency symbol; the banknote image shows the currency."""
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    if currency == "KHR":
        return f"{int(value):,}"
    if currency == "USD":
        return f"{value:,.2f}"
    return "—"


def load_nbc_logo(root, target_height: int, path: Path = NBC_LOGO_PATH) -> Optional[tk.PhotoImage]:
    """Load the owner-supplied NBC logo, scaled near the digit height, with white made transparent."""
    try:
        if not path.is_file():
            return None
        original = tk.PhotoImage(master=root, file=str(path))
        factor = max(1, round(original.height() / max(1, target_height)))
        logo = original.subsample(factor, factor) if factor > 1 else original
        for x in range(logo.width()):
            for y in range(logo.height()):
                red, green, blue = logo.get(x, y)
                if red > 235 and green > 235 and blue > 235:
                    logo.transparency_set(x, y, True)
        return logo
    except (tk.TclError, OSError, ValueError):
        return None


GOLD_UNIT_NAMES = {"damlung": "ដំឡឹង", "chi": "ជី"}
GOLD_UNIT_NAME_SIZES = {False: 12, True: 9}
CAMBODIA_FLAG_HEIGHTS = {False: 18, True: 12}
CAMBODIA_FLAG_COLORS = {"blue": "#032EA1", "red": "#E00025", "white": "#FFFFFF"}


def cambodia_flag_image(root, height: int) -> tk.PhotoImage:
    """A small Cambodian flag (blue/red/blue with a white Angkor Wat) drawn as an image.

    Tk cannot render the flag emoji, so the flag is painted from simple shapes at the
    height of the neighbouring figures.
    """
    height = max(8, int(height))
    width = round(height * 1.5)
    image = tk.PhotoImage(master=root, width=width, height=height)
    band = height / 4
    image.put(CAMBODIA_FLAG_COLORS["blue"], to=(0, 0, width, height))
    image.put(CAMBODIA_FLAG_COLORS["red"], to=(0, round(band), width, round(3 * band)))

    def block(x0: float, y0: float, x1: float, y1: float) -> None:
        left, top = round(width * x0), round(height * y0)
        right, bottom = max(left + 1, round(width * x1)), max(top + 1, round(height * y1))
        image.put(CAMBODIA_FLAG_COLORS["white"], to=(left, top, right, bottom))

    block(0.28, 0.64, 0.72, 0.69)   # terrace
    block(0.32, 0.52, 0.68, 0.64)   # galleries
    block(0.46, 0.33, 0.54, 0.52)   # central tower
    block(0.48, 0.29, 0.52, 0.33)   # central spire
    block(0.36, 0.41, 0.42, 0.52)   # left tower
    block(0.58, 0.41, 0.64, 0.52)   # right tower
    return image
RATE_GROUP_ROW_COLORS = ("#121B2D", "#18233A")
RATE_GROUP_GLOW_COLOR = "#3A3214"
RATE_GROUP_DIRECTION_COLORS = {KHR_TO_USD: "#7DB6FF", USD_TO_KHR: "#FF8A8A", None: "#CBD5E1"}
RATE_GROUP_MUTED_TEXT = "#94A3B8"
RATE_GROUP_FADED_TEXT = "#5E6B80"
RATE_GROUP_ACCENT = "#FFE66D"
RATE_TREND_COLORS = {"up": "#4ADE80", "down": "#FACC15", "flat": "#46536B"}
RATE_TREND_ARROWS = {"up": "▲", "down": "▼", "flat": "▲▼"}
RATE_BEST_OUTLINE = "#FBBF24"
MAX_RATE_GROUP_MESSAGES = 200
RATE_GROUP_FADE_AFTER = timedelta(minutes=15)
RATE_GROUP_OLD_AFTER = timedelta(hours=1)
RATE_GROUP_GLOW_SECONDS = 10
RATE_GROUP_HISTORY_GLOW_LIMIT = timedelta(minutes=2)
# Private-card font sizes: (wide, narrow) for tag, rate, amount, banks, header, arrow/gap.
RATE_GROUP_FONT_SIZES = {
    False: {"tag": 9, "rate": 14, "amount": 12, "banks": 9, "header": 10, "small": 9},
    True: {"tag": 8, "rate": 12, "amount": 10, "banks": 8, "header": 9, "small": 8},
}


def rate_pulse_color(base: str, highlight: str, progress: float) -> str:
    """Blend between two readable rate colors for the gentle figure pulse."""
    amount = max(0.0, min(1.0, progress))
    start = tuple(int(base[index:index + 2], 16) for index in (1, 3, 5))
    end = tuple(int(highlight[index:index + 2], 16) for index in (1, 3, 5))
    channels = tuple(round(left + (right - left) * amount) for left, right in zip(start, end))
    return "#{:02X}{:02X}{:02X}".format(*channels)


def rate_pulse_progress(step: int) -> float:
    """Return one smooth pulse phase, ranging from the base to highlight."""
    phase = (step % RATE_PULSE_STEPS) / RATE_PULSE_STEPS
    return (1 - math.cos(2 * math.pi * phase)) / 2


def _has_khmer_text(value: str) -> bool:
    """True when text needs the Khmer font; the riel sign alone renders through fallback."""
    return any(
        ("ក" <= char <= "៿" and char != "៛") or "᧠" <= char <= "᧿"
        for char in value
    )


def rate_group_message_time(message: dict[str, object]) -> datetime:
    """Return a post's Telegram time for ordering and the 15-minute summary."""
    try:
        value = datetime.fromisoformat(str(message.get("timestamp") or ""))
    except ValueError:
        return datetime.min.replace(tzinfo=CAMBODIA_TIMEZONE)
    return value if value.tzinfo else value.replace(tzinfo=CAMBODIA_TIMEZONE)


def _rate_group_order(message: dict[str, object]) -> tuple[datetime, int]:
    try:
        message_id = int(message.get("id") or 0)
    except (TypeError, ValueError):
        message_id = 0
    return rate_group_message_time(message), message_id


def latest_rate_group_posts(messages: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Keep each sender's newest post, newest sender first; reposts replace older rows."""
    latest: dict[str, dict[str, object]] = {}
    for message in sorted(messages, key=_rate_group_order):
        sender_key = str(message.get("sender") or "").strip().casefold()
        latest.pop(sender_key, None)
        latest[sender_key] = message
    return list(reversed(latest.values()))


def rate_group_summary_bounds(
    messages: Iterable[dict[str, object]],
    now: Optional[datetime] = None,
) -> dict[str, tuple[Decimal, Decimal]]:
    """Low/high tagged rate per direction from each sender's latest post (last 15 min)."""
    posts = [
        (rate_group_message_time(message), format_rate_post(message.get("text")))
        for message in latest_rate_group_posts(messages)
    ]
    return summarize_rates(posts, now)


def rate_group_summary_text(
    messages: Iterable[dict[str, object]],
    now: Optional[datetime] = None,
) -> dict[Optional[str], str]:
    """Return the recent tagged-rate range per direction, e.g. "KHR→USD  4089 – 4090 KHR"."""
    bounds = rate_group_summary_bounds(messages, now)
    texts = {}
    for direction in (KHR_TO_USD, USD_TO_KHR):
        value = format_summary_range(bounds.get(direction)).replace("–", " – ")
        texts[direction] = f"{DIRECTION_LABELS[direction]}  {value}" + (" KHR" if direction in bounds else "")
    return texts


def _post_direction_rates(post) -> dict[str, Decimal]:
    rates: dict[str, Decimal] = {}
    for row in post.rows:
        if row.direction in (KHR_TO_USD, USD_TO_KHR) and len(row.rate_values) == 1:
            rates.setdefault(row.direction, row.rate_values[0])
    return rates


def rate_group_sender_trends(
    messages: Iterable[dict[str, object]],
) -> dict[str, dict[str, tuple[Decimal, Optional[Decimal]]]]:
    """Per sender and direction: (current rate, previous different rate), in memory only."""
    trends: dict[str, dict[str, tuple[Decimal, Optional[Decimal]]]] = {}
    for message in sorted(messages, key=_rate_group_order):
        sender_key = str(message.get("sender") or "").strip().casefold()
        state = trends.setdefault(sender_key, {})
        for direction, value in _post_direction_rates(format_rate_post(message.get("text"))).items():
            current = state.get(direction)
            if current is None:
                state[direction] = (value, None)
            elif value != current[0]:
                state[direction] = (value, current[0])
    return trends


def order_rate_group_posts(
    posts: list[dict[str, object]],
    now: Optional[datetime] = None,
) -> list[dict[str, object]]:
    """Keep newest-first order but move posts older than one hour to the bottom."""
    current = now or datetime.now(timezone.utc)
    recent = [post for post in posts if current - rate_group_message_time(post) <= RATE_GROUP_OLD_AFTER]
    old = [post for post in posts if current - rate_group_message_time(post) > RATE_GROUP_OLD_AFTER]
    return recent + old


def rate_gap_text(rate: Decimal, reference: Optional[Decimal]) -> str:
    """Difference from the NBC official rate, e.g. "+5" or "−2"."""
    if reference is None:
        return ""
    gap = rate - reference
    if gap == 0:
        return "±0"
    text = format_rate_value(abs(gap))
    return f"+{text}" if gap > 0 else f"−{text}"


def best_bank_rates(rates: dict[str, ExchangeRate], now: datetime) -> tuple[set[str], set[str]]:
    """Banks with the highest buy and lowest sell among fresh buy/sell quotes."""
    quotes = {
        source: rate for source, rate in rates.items()
        if rate.buy_rate is not None and rate.sell_rate is not None and not rate.is_stale(now)
    }
    if len(quotes) < 2:
        return set(), set()
    best_buy = max(rate.buy_rate for rate in quotes.values())
    best_sell = min(rate.sell_rate for rate in quotes.values())
    return (
        {source for source, rate in quotes.items() if rate.buy_rate == best_buy},
        {source for source, rate in quotes.items() if rate.sell_rate == best_sell},
    )


def fit_two_lines(text: str, font: tkfont.Font, width: int) -> tuple[str, int]:
    """Return (text, lines) so the text fits in at most two lines of `width` px, ending in … if cut."""
    if width <= 0 or font.measure(text) <= width:
        return text, 1
    words = text.split()
    first = ""
    for index, word in enumerate(words):
        candidate = f"{first} {word}".strip()
        if font.measure(candidate) > width:
            break
        first = candidate
    else:
        index = len(words)
    rest = " ".join(words[index:]) if first else text
    if not first:  # one very long word: split it by characters
        cut = len(text)
        while cut > 1 and font.measure(text[:cut]) > width:
            cut -= 1
        first, rest = text[:cut], text[cut:]
    if font.measure(rest) > width:
        while rest and font.measure(rest + "…") > width:
            rest = rest[:-1]
        rest = rest.rstrip() + "…"
    return f"{first}\n{rest}", 2


def _is_khmer(text: str) -> bool:
    return any("\u1780" <= character <= "\u17ff" for character in text)


# Ticker labels (owner-approved wording, Western digits).
TICKER_FUEL_LABELS = {"regular": "តម្លៃសាំងធម្មតា", "diesel": "តម្លៃប្រេងម៉ាស៊ូត"}
TICKER_GOLD_ICON = "gold_icon"
TICKER_GOLD_TEXT = "gold_shadow"  # gold text drawn with a dark drop shadow
TICKER_GOLD_SHADOW = "#3B2A00"
TICKER_GAP_TEXT = "          "


def _ticker_arrow(change, stale: bool) -> tuple[str, str]:
    """Fuel colours for every ticker arrow: ▲ red when the price rose, ▼ green when it fell."""
    if change is None or change == 0:
        return "", "muted"
    up = change > 0 if not isinstance(change, str) else change == "up"
    return ("▲" if up else "▼"), ("muted" if stale else ("red" if up else "green"))


def ticker_segments(
    summary: dict[str, object], fuel: Optional[FuelPrices], today,
    gold: Optional[ExchangeRate] = None, now: Optional[datetime] = None,
) -> list[tuple[str, str]]:
    """(text, colour) pieces for the tab-bar ticker: today's totals, fuel prices, then gold."""
    try:
        khr = int(Decimal(str(summary.get("KHR", "0"))))
        usd = Decimal(str(summary.get("USD", "0")))
        count = int(summary.get("count", 0))
    except (InvalidOperation, TypeError, ValueError):
        khr, usd, count = 0, Decimal("0"), 0
    noun = "payment" if count == 1 else "payments"
    segments = [
        ("TODAY", "text"), (f"  {count} {noun}", "text"), ("  ·  ", "muted"),
        (f"KHR {khr:,}", "green"), ("  ·  ", "muted"), (f"USD {usd:,.2f}", "usd"),
        (TICKER_GAP_TEXT, "muted"),
    ]
    if fuel is None:
        segments.append((f"{TICKER_FUEL_LABELS['regular']} …  ·  {TICKER_FUEL_LABELS['diesel']} …", "muted"))
    else:
        stale = fuel_prices_are_stale(fuel, today)
        price_color = "muted" if stale else "amber"
        for index, key in enumerate(("regular", "diesel")):
            if index:
                segments.append(("  ·  ", "muted"))
            segments.append((f"{TICKER_FUEL_LABELS[key]} ", price_color))
            segments.append((f"{getattr(fuel, key):,}៛", price_color))
            change = getattr(fuel, f"{key}_change")
            arrow, arrow_color = _ticker_arrow(change, stale)
            if arrow:
                segments.append((f" {arrow}{abs(change):,}", arrow_color))
        period = fuel_period_khmer(fuel)
        if period:
            segments.append(("  ·  ", "muted"))
            segments.append((period, "muted" if stale else "text"))
        if stale:
            segments.append(("  · តម្លៃចាស់", "muted"))
    segments.append((TICKER_GAP_TEXT, "muted"))
    segments.append(("", TICKER_GOLD_ICON))
    price = gold.official_rate if gold is not None else None
    if price is None:
        segments.append(("  ដំឡឹង …  ·  ជី …", "muted"))
        return segments
    stale = gold.is_stale(now or datetime.now(CAMBODIA_TIMEZONE))
    text_color = "muted" if stale else TICKER_GOLD_TEXT
    arrow, arrow_color = _ticker_arrow(gold.trend("official"), stale)
    for index, (unit, value) in enumerate(zip(("damlung", "chi"), gold_local_units(price))):
        if index:
            segments.append(("  ·  ", "muted"))
        segments.append(((" " if index == 0 else "") + f"≈ ${value:,.2f}", text_color))
        segments.append((f" / {GOLD_UNIT_NAMES[unit]}", text_color))
        if arrow:
            segments.append((f" {arrow}", arrow_color))
    return segments


def today_strip_text(summary: dict[str, object]) -> str:
    """Slim payment-card footer, e.g. "Today 23 payments · KHR 1,250,000 · USD 340.00"."""
    try:
        khr = int(Decimal(str(summary.get("KHR", "0"))))
        usd = Decimal(str(summary.get("USD", "0")))
        count = int(summary.get("count", 0))
    except (InvalidOperation, TypeError, ValueError):
        return "Today —"
    noun = "payment" if count == 1 else "payments"
    return f"Today {count} {noun} · KHR {khr:,} · USD {usd:,.2f}"


def rate_group_status_label(status: str) -> str:
    normalized = status.upper()
    if normalized.startswith("CONNECTED"):
        return "CONNECTED"
    if normalized.startswith("CONNECTING"):
        return "CONNECTING"
    if normalized.startswith("DISCONNECTING"):
        return "DISCONNECTING"
    if normalized.startswith("DISCONNECTED") or normalized == "NOT CONNECTED":
        return "DISCONNECTED"
    if normalized.startswith("ERROR"):
        if "CREDENTIAL" in normalized:
            return "LOGIN REQUIRED"
        if "PHONE" in normalized:
            return "INVALID PHONE"
        if "GROUP NOT AVAILABLE" in normalized:
            return "GROUP UNAVAILABLE"
        return "ERROR"
    if normalized.startswith("LOGIN CANCELLED"):
        return "LOGIN CANCELLED"
    return "DISCONNECTED"


def rate_group_status_dot_color(label: str) -> str:
    """Colour for the compact status dot shown beside the title on wide headers."""
    if label == "CONNECTED":
        return "#4ADE80"
    if label in {"CONNECTING", "DISCONNECTING"}:
        return "#FBBF24"
    if label == "DISCONNECTED":
        return "#CBD5E1"
    return "#FB7185"


class _MonitorInfo(Structure):
    _fields_ = (("cbSize", DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", DWORD))


def active_monitors() -> list[dict[str, int | bool]]:
    """Return active Windows monitor work areas without adding a dependency."""
    if os.name != "nt":
        return []
    monitors: list[dict[str, int | bool]] = []
    callback_type = WINFUNCTYPE(BOOL, HMONITOR, HDC, RECT, LPARAM)

    def collect(handle, _dc, _rect, _data):
        info = _MonitorInfo()
        info.cbSize = sizeof(_MonitorInfo)
        if windll.user32.GetMonitorInfoW(handle, byref(info)):
            area = info.rcWork
            monitors.append({
                "left": area.left, "top": area.top, "right": area.right, "bottom": area.bottom,
                "primary": bool(info.dwFlags & 1),
            })
        return True

    callback = callback_type(collect)
    windll.user32.EnumDisplayMonitors(0, 0, callback, 0)
    return monitors


def preferred_secondary_monitor(monitors: list[dict[str, int | bool]]) -> Optional[dict[str, int | bool]]:
    """Choose the active non-primary monitor closest to the primary display."""
    primary = next((monitor for monitor in monitors if monitor["primary"]), None)
    secondary = [monitor for monitor in monitors if not monitor["primary"]]
    if not secondary:
        return None
    if primary is None:
        return secondary[0]
    primary_center = ((int(primary["left"]) + int(primary["right"])) / 2,
                      (int(primary["top"]) + int(primary["bottom"])) / 2)
    return min(secondary, key=lambda monitor: (
        ((int(monitor["left"]) + int(monitor["right"])) / 2 - primary_center[0]) ** 2
        + ((int(monitor["top"]) + int(monitor["bottom"])) / 2 - primary_center[1]) ** 2
    ))


def format_payment_amount(amount: object, currency: object) -> str:
    """Format validated payment data for the large operational display."""
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return "—"
    if currency == "KHR":
        return f"៛ {int(value):,}"
    if currency == "USD":
        return f"$ {value:,.2f}"
    return "—"


def amount_color(currency: object) -> str:
    """Return the theme color for a validated displayed currency."""
    return "usd" if currency == "USD" else "green" if currency == "KHR" else "muted"


def responsive_layout_mode(height: int) -> str:
    """Choose a layout that keeps the payment amount visible on short displays."""
    if height < 680:
        return "short"
    if height < 780:
        return "compact"
    return "normal"

def narrow_header_mode(width: int) -> bool:
    return width < 1080


def announcement_label(status: str) -> tuple[str, str]:
    labels = {
        "QUEUED": ("● ANNOUNCING…", "amber"),
        "SPOKEN": ("✓ ANNOUNCED", "green"),
        "MUTED": ("⊘ NOT ANNOUNCED — MUTED", "amber"),
        "FAILED": ("! ANNOUNCEMENT FAILED", "red"),
    }
    return labels.get(status.upper(), ("AWAITING PAYMENT", "muted"))


def component_health(value: str, component: str) -> tuple[str, str]:
    normalized = value.lower()
    if component == "telegram":
        return (("● CONNECTED", "green") if normalized.startswith("connected") else
                ("● CONNECTING", "amber") if normalized in {"disconnected", "starting"} else ("! DISCONNECTED", "red"))
    if component == "speaker":
        return (("● READY", "green") if normalized == "ready" else
                ("⊘ MUTED", "amber") if normalized == "muted" else ("! " + value.upper(), "red"))
    return (("● VERIFIED", "green") if normalized in {"detected", "verified"} else ("● WAITING", "amber"))


class Dashboard:
    def __init__(
        self,
        announce_test: Callable[[str], None],
        set_muted: Callable[[bool], None],
        count_today: Callable[[], int],
        today_summary: Optional[Callable[[], dict[str, object]]] = None,
        recent_payments: Optional[Callable[[int], list[dict[str, object]]]] = None,
        save_settings: Optional[Callable[[dict[str, str]], None]] = None,
        expected_username: str = "PayWayByABA_bot",
        configured_chat_ids: tuple[int, ...] = (),
        configured_sender_id: Optional[int] = None,
        diagnostic_mode: bool = True,
        start_rate_group_reader: Optional[Callable[[], None]] = None,
        stop_rate_group_reader: Optional[Callable[[], None]] = None,
        initial_exchange_rates: Optional[dict[str, ExchangeRate]] = None,
        nbc_history: Optional[Callable[[int], list[Decimal]]] = None,
        initial_fuel_prices: Optional[dict[str, object]] = None,
    ):
        self.root = tk.Tk()
        self.root.title("ABA Payment Speaker")
        self.root.geometry("1180x800")
        self.root.minsize(900, 600)
        self.root.configure(bg=COLORS["background"])
        self.announce_test = announce_test
        self.set_muted = set_muted
        self.count_today = count_today
        self.today_summary = today_summary or (lambda: {"count": count_today(), "KHR": "0", "USD": "0.00"})
        self.recent_payments = recent_payments or (lambda limit=1000: [])
        self.save_settings = save_settings
        self.expected_username = expected_username.lstrip("@")
        self.saved_chat_ids = set(configured_chat_ids)
        self.saved_sender_id = configured_sender_id
        self.diagnostic_mode = diagnostic_mode
        self.observed: dict[str, object] = {}
        self.source_candidate: Optional[dict[str, object]] = None
        self.events: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.muted = False
        self.last_test_announcement = ""
        self.current_payment_key: Optional[str] = None
        self.current_currency: Optional[str] = None
        self._pulse_token = 0
        self._rate_pulse_step = 0
        self._rate_pulse_after_id = None
        self._display_date = None
        self._layout_after_id = None
        self._layout_mode = None
        self.start_rate_group_reader = start_rate_group_reader or (lambda: None)
        self.stop_rate_group_reader = stop_rate_group_reader or (lambda: None)
        self._rate_group_start_requested = False
        self._rate_group_start_after_id = None
        self.rate_group_messages: dict[int, dict[str, object]] = {}
        self._rate_group_summary_ticks = 0
        self._rate_group_glow: dict[str, datetime] = {}
        self._rate_group_glow_after_id = None
        self._rate_group_summary_trend: dict[str, tuple[Optional[Decimal], Optional[Decimal]]] = {}
        self._rate_group_narrow: Optional[bool] = None
        self.exchange_rates = dict(initial_exchange_rates or {})
        self.fuel_prices: Optional[FuelPrices] = FuelPrices.from_dict(initial_fuel_prices) if initial_fuel_prices else None
        self._today_summary: dict[str, object] = {"count": 0, "KHR": "0", "USD": "0.00"}
        self._ticker_after_id = None
        self._ticker_offset = 0.0
        self._ticker_cycle = 0.0
        self._ticker_drawn: Optional[tuple] = None
        self._ticker_date = None
        self._ticker_tabs: Optional[tuple[int, int]] = None
        self._ticker_fonts: dict[bool, tkfont.Font] = {}
        self.rate_display_labels: dict[str, dict[str, tk.Label]] = {}
        self._responsive_title_fonts: dict[tk.Label, tkfont.Font] = {}
        self._responsive_title_sizes: dict[tk.Label, int] = {}
        self._responsive_rate_label_sizes: dict[tk.Label, int] = {}
        self._dashboard_scroll_update_id = None
        self._operations_scroll_update_id = None
        self.khmer_title_font = self._select_khmer_title_font()
        self.rate_group_font = self._select_rate_group_font()
        self.figure_font = self._installed_font("Bahnschrift")
        self.caption_font = self._installed_font("Orbitron")
        self.label_font = self._installed_font("Montserrat")
        self.condensed_font = self._installed_font("Bahnschrift SemiCondensed")
        self._cambodia_flag = cambodia_flag_image(self.root, CAMBODIA_FLAG_HEIGHTS[False])
        self._nbc_logos = {
            narrow: load_asset_image(self.root, f"nbc_logo_{height}.png") or load_nbc_logo(self.root, height)
            for narrow, height in NBC_LOGO_HEIGHTS.items()
        }
        self._bank_logos = {
            source: {narrow: load_asset_image(self.root, pattern.format(height)) for narrow, height in BANK_LOGO_HEIGHTS.items()}
            for source, pattern in BANK_LOGO_FILES.items()
        }
        self._note_images: dict[tuple[str, int], Optional[tk.PhotoImage]] = {}
        self._amount_base_size = 56
        self.nbc_history = nbc_history or (lambda days=7: [])
        self._nbc_history_values: list[Decimal] = []
        self._nbc_state: dict[str, object] = {}
        self._reload_nbc_history()
        self._history_rows: list[dict[str, object]] = []
        self._history_narrow = False
        self._rate_label_fonts = {
            size: tkfont.Font(root=self.root, family=self.khmer_title_font, size=size)
            for size in range(5, 9)
        }
        initial_source = "Verified" if configured_sender_id is not None else "Waiting"
        self.values = {name: tk.StringVar(value=value) for name, value in {
            "telegram": "Disconnected", "setup": "Starting", "speaker": "Ready", "source": initial_source,
            "amount": "—", "payer": "WAITING FOR PAYMENT", "bank": "—", "announcement": "AWAITING PAYMENT",
            "today": "0", "today_khr": "៛ 0", "today_usd": "$ 0.00", "clock": "", "date": "", "live": "STARTING",
            "rate_group_status": "NOT CONNECTED", "today_strip": "Today 0 payments · KHR 0 · USD 0.00",
            "expected_source": f"@{self.expected_username}", "group_title": "Waiting for a group message",
            "chat_id": ", ".join(str(value) for value in configured_chat_ids) or "—",
            "sender_username": "—", "sender_id": str(configured_sender_id) if configured_sender_id is not None else "—",
            "source_match": "Waiting", "commissioning": "Diagnostic mode is active; production speech is disabled."
        }.items()}
        self._build()
        self.root.bind("<Destroy>", self._on_root_destroy, add="+")
        self.root.bind("<Configure>", self._schedule_responsive_layout)
        self.root.after(150, lambda: self._place_startup_window(8))
        self._rate_group_start_after_id = self.root.after(
            500,
            self._auto_start_rate_group_reader,
        )
        self._refresh_operational_data()
        self._tick_clock()
        self.root.after(200, self._drain_events)

    def _font(self, size: int, weight: str = "normal", family: Optional[str] = None) -> tuple[str, int, str]:
        return (family or "Segoe UI", size, weight)

    def _select_khmer_title_font(self) -> str:
        installed = {name.casefold(): name for name in tkfont.families(self.root)}
        for candidate in ("Khmer OS Muol Light", "Khmer OS Light Moul", "Khmer OS Muol", "Leelawadee UI", "Segoe UI"):
            if candidate.casefold() in installed:
                return installed[candidate.casefold()]
        return "Segoe UI"

    def _installed_font(self, family: str, fallback: str = "Segoe UI") -> str:
        installed = {name.casefold(): name for name in tkfont.families(self.root)}
        return installed.get(family.casefold(), fallback)

    def _select_rate_group_font(self) -> str:
        installed = {name.casefold(): name for name in tkfont.families(self.root)}
        return installed.get("siemreap", self.khmer_title_font)

    def _card(self, parent, color: str = "surface", **grid) -> tk.Frame:
        card = tk.Frame(parent, bg=COLORS[color], highlightbackground=COLORS["border"], highlightthickness=1)
        if grid: card.grid(**grid)
        return card

    def _label(self, parent, text="", variable=None, size=11, color="text", weight="normal", family=None, **kwargs):
        return tk.Label(parent, text=text, textvariable=variable, bg=parent.cget("bg"), fg=COLORS[color],
                        font=self._font(size, weight, family), **kwargs)

    def _button(self, parent, text: str, command, accent="button", **kwargs) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bg=COLORS[accent], fg=COLORS["text"],
                         activebackground=COLORS["border"], activeforeground=COLORS["text"], relief="flat", bd=0,
                         cursor="hand2", font=self._font(10, "bold"), padx=15, pady=9, **kwargs)

    def _build(self) -> None:
        self._configure_styles()
        header = tk.Frame(self.root, bg=COLORS["background"], padx=28, pady=3); header.pack(fill="x"); self.header = header
        for column, weight in enumerate((30, 40, 30)):
            header.grid_columnconfigure(column, weight=weight, uniform="header_columns")
        header.grid_rowconfigure(0, weight=1)
        title = tk.Frame(header, bg=COLORS["background"]); title.grid(row=0, column=0, sticky="w"); self.title_frame = title
        self.title_primary_label = self._label(title, "វីង វណ្ណា-ស្រីម៉ិច", size=24, family=self.khmer_title_font)
        self.title_primary_label.pack(anchor="w")
        self.title_secondary_label = self._label(title, "ប្រព័ន្ធទទួលប្រាក់", size=24, color="green", family=self.khmer_title_font)
        self.title_secondary_label.pack(anchor="w")
        clock = tk.Frame(header, bg=COLORS["background"]); clock.grid(row=0, column=1, sticky="nsew"); self.clock_frame = clock
        self.clock_label = self._label(clock, variable=self.values["clock"], size=56, weight="bold")
        self.clock_label.pack(anchor="center")
        self.date_label = self._label(clock, variable=self.values["date"], size=13, color="muted", weight="bold")
        self.date_label.pack(anchor="center", pady=(0, 2))
        self.live_label = self._label(clock, variable=self.values["live"], size=12, color="amber", weight="bold")
        self.live_label.pack(anchor="center")
        self._build_nbc_header_card(header)
        self.notebook = ttk.Notebook(self.root, style="Dark.TNotebook"); self.notebook.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self.main_tab = tk.Frame(self.notebook, bg=COLORS["background"]); self.diagnostics_tab = tk.Frame(self.notebook, bg=COLORS["background"])
        self.notebook.add(self.main_tab, text="  DASHBOARD  "); self.notebook.add(self.diagnostics_tab, text="  SETTINGS & DIAGNOSTICS  ")
        self._build_main_tab(); self._build_diagnostics_tab(); self.notebook.select(self.main_tab)
        self._build_ticker()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Dark.TNotebook", background=COLORS["background"], borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background=COLORS["surface"], foreground=COLORS["muted"], padding=(18, 9), font=self._font(10, "bold"))
        style.map("Dark.TNotebook.Tab", background=[("selected", COLORS["surface_alt"])], foreground=[("selected", COLORS["text"])])
        style.configure("Payments.Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"], foreground=COLORS["text"], rowheight=40, borderwidth=0, font=self._font(12))
        style.configure("Payments.Treeview.Heading", background=COLORS["surface_alt"], foreground=COLORS["muted"], relief="flat", font=self._font(11, "bold"))
        style.map("Payments.Treeview", background=[("selected", COLORS["blue_dark"])])

    def _build_main_tab(self) -> None:
        viewport = tk.Frame(self.main_tab, bg=COLORS["background"])
        viewport.pack(fill="both", expand=True)
        viewport.grid_rowconfigure(0, weight=1)
        viewport.grid_columnconfigure(0, weight=1)
        self.dashboard_canvas = tk.Canvas(
            viewport,
            bg=COLORS["background"],
            highlightthickness=0,
            bd=0,
        )
        self.dashboard_canvas.grid(row=0, column=0, sticky="nsew")
        self.dashboard_scrollbar = ttk.Scrollbar(
            viewport,
            orient="vertical",
            command=self.dashboard_canvas.yview,
        )
        self.dashboard_scrollbar.grid(row=0, column=1, sticky="ns")
        self.dashboard_scrollbar.grid_remove()
        self.dashboard_canvas.configure(yscrollcommand=self.dashboard_scrollbar.set)
        body = tk.Frame(self.dashboard_canvas, bg=COLORS["background"])
        self.dashboard_body = body
        self.dashboard_window = self.dashboard_canvas.create_window(
            (0, 0), window=body, anchor="nw"
        )
        body.bind("<Configure>", self._schedule_dashboard_scroll_update)
        self.dashboard_canvas.bind("<Configure>", self._resize_dashboard_content)
        self.root.bind_all("<MouseWheel>", self._scroll_dashboard)
        for column, weight in enumerate((50, 25, 25)):
            body.grid_columnconfigure(column, weight=weight, uniform="dashboard_columns")
        body.grid_rowconfigure(0, weight=1)
        payment = self._card(body, row=0, column=0, sticky="nsew", padx=(0, 10), pady=(8, 0)); self.payment_card = payment
        payment.grid_columnconfigure(0, weight=1); payment.grid_rowconfigure(1, weight=1, minsize=120)
        title_row = tk.Frame(payment, bg=COLORS["surface"]); title_row.grid(row=0, column=0, pady=(6, 0)); self.payment_title_row = title_row
        self.payment_title_label = self._label(title_row, "LAST PAYMENT RECEIVED", size=11, color="muted", weight="bold")
        self.payment_title_label.pack(side="left")
        self._label(title_row, "  ·  ", size=11, color="muted", weight="bold").pack(side="left")
        self.announcement_label = self._label(title_row, variable=self.values["announcement"], size=11, color="muted", weight="bold")
        self.announcement_label.pack(side="left")
        amount_row = tk.Frame(payment, bg=COLORS["surface"]); amount_row.grid(row=1, column=0, padx=20, pady=(0, 0))
        self.amount_row = amount_row
        self.amount_note_label = tk.Label(amount_row, bg=COLORS["surface"], bd=0, padx=0, pady=0)
        self.amount_note_label.pack(side="left")
        self.amount_label = self._label(amount_row, variable=self.values["amount"], size=56, color="green", weight="bold")
        self.amount_label.pack(side="left")
        identity = tk.Frame(payment, bg=COLORS["surface"]); identity.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 8))
        identity.grid_columnconfigure(0, weight=1, uniform="identity"); identity.grid_columnconfigure(1, weight=1, uniform="identity")
        sender = tk.Frame(identity, bg=COLORS["blue_dark"], padx=16, pady=11); sender.grid(row=0, column=0, sticky="nsew", padx=(0, 7)); self.sender_card = sender
        self._label(sender, "● FROM (SENDER)", size=9, color="blue", weight="bold").pack(anchor="w")
        self.sender_label = self._label(sender, variable=self.values["payer"], size=21, color="blue", weight="bold", anchor="w", justify="left", wraplength=220)
        self.sender_label.pack(fill="both", expand=True, pady=(3, 0))
        bank = tk.Frame(identity, bg=COLORS["purple_dark"], padx=16, pady=11); bank.grid(row=0, column=1, sticky="nsew", padx=(7, 0)); self.bank_card = bank
        self._label(bank, "▥ FROM BANK", size=9, color="purple", weight="bold").pack(anchor="w")
        self.bank_label = self._label(bank, variable=self.values["bank"], size=21, color="purple", weight="bold", anchor="w", justify="left", wraplength=220)
        self.bank_label.pack(fill="both", expand=True, pady=(3, 0))
        side = tk.Frame(body, bg=COLORS["background"]); side.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 10), pady=(8, 0)); self.dashboard_side = side
        side.grid_columnconfigure(0, weight=1); side.grid_rowconfigure(0, weight=1)
        self._build_exchange_rate_card(side)
        private_side = tk.Frame(body, bg=COLORS["background"])
        private_side.grid(row=0, column=2, rowspan=2, sticky="nsew", pady=(8, 0)); self.private_side = private_side
        private_side.grid_columnconfigure(0, weight=1); private_side.grid_rowconfigure(0, weight=1)
        self._build_private_rate_card(private_side)
        recent = self._card(body, row=1, column=0, sticky="nsew", padx=(0, 10), pady=(12, 0)); recent.grid_columnconfigure(0, weight=1)
        self.recent_card = recent
        headings = tk.Frame(recent, bg=COLORS["surface_alt"], height=34); headings.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 0)); headings.grid_propagate(False)
        self.history_headings = headings
        self._configure_history_columns(headings)
        self.history_heading_labels = []
        for column, title in enumerate(("AMOUNT", "SENDER", "BANK", "TIME")):
            anchor = HISTORY_COLUMN_ANCHORS[column]
            heading = tk.Label(headings, text=title, bg=COLORS["surface_alt"], fg=COLORS["muted"], font=self._font(11, "bold"), anchor=anchor, padx=10)
            heading.grid(row=0, column=column, sticky="nsew"); self.history_heading_labels.append(heading)
        history_panel = tk.Frame(recent, bg=COLORS["surface"]); history_panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8)); history_panel.grid_columnconfigure(0, weight=1)
        self.history_canvas = tk.Canvas(history_panel, bg=COLORS["surface"], height=132, highlightthickness=0, bd=0)
        self.history_canvas.grid(row=0, column=0, sticky="ew")
        self.history_scrollbar = ttk.Scrollbar(history_panel, orient="vertical", command=self.history_canvas.yview)
        self.history_scrollbar.grid(row=0, column=1, sticky="ns")
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)
        self.history_inner = tk.Frame(self.history_canvas, bg=COLORS["surface"])
        self.history_window = self.history_canvas.create_window((0, 0), window=self.history_inner, anchor="nw")
        self.history_canvas.bind("<Configure>", self._resize_history)
        self.history_scrollbar.grid_remove()

    def _build_exchange_rate_card(self, parent) -> None:
        """Rates & gold: a BANK | ទិញ $ | លក់ $ table for ACLEDA and WING plus the gold price."""
        card = self._card(parent, row=0, column=0, sticky="nsew")
        self.rate_card = card
        self.rate_title_label = self._label(
            card,
            "អត្រាប្តូរប្រាក់ និង មាស",
            size=11,
            color="text",
            weight="bold",
            family=self.khmer_title_font,
            anchor="center",
            justify="center",
        )
        self.rate_title_label.pack(fill="x", padx=8, pady=(10, 4))
        self.rate_title_label.bind(
            "<Configure>",
            lambda _event: self._fit_centered_title(self.rate_title_label, 11, 6),
            add="+",
        )
        self.rate_age_label = self._label(card, size=8, color="muted", anchor="center")
        self.rate_age_label.pack(fill="x", side="bottom", padx=8, pady=(2, 8))
        table = tk.Frame(card, bg=COLORS["surface"])
        table.pack(fill="both", expand=True, padx=8, pady=(0, 2))
        self.rate_table = table
        table.grid_columnconfigure(0, weight=30, uniform="bank_rate_columns")
        table.grid_columnconfigure(1, weight=35, uniform="bank_rate_columns")
        table.grid_columnconfigure(2, weight=35, uniform="bank_rate_columns")
        self.rate_table_headers = {}
        for column, (text, color, family) in enumerate((
            ("BANK", "muted", None),
            ("ទិញ $", "red", self.khmer_title_font),
            ("លក់ $", "blue", self.khmer_title_font),
        )):
            header = self._label(table, text, size=9, color=color, weight="bold", family=family, anchor="center")
            header.configure(bg=RATE_TABLE_HEADER_BG, pady=4)
            header.grid(row=0, column=column, sticky="nsew", pady=(0, 3))
            self.rate_table_headers[column] = header

        source_details = (
            ("ACLEDA", "ACLEDA", "Notes"),
            ("WING", "WING", "TT outbound"),
        )
        for index, (source, name, category) in enumerate(source_details, start=1):
            table.grid_rowconfigure(index, weight=1)
            tint = RATE_ROW_COLORS[source]
            bank_cell = tk.Frame(table, bg=tint, padx=6, highlightthickness=0)
            bank_cell.grid(row=index, column=0, sticky="nsew", pady=2)
            bank_label = self._label(bank_cell, name, size=10, color="text", weight="bold", anchor="center")
            bank_label.pack(anchor="center", pady=(4, 0))
            logo = self._bank_logos.get(source, {}).get(False)
            if logo is not None:
                # The bank's logo replaces the small category text under its name.
                category_label = tk.Label(bank_cell, image=logo, bg=tint, bd=0, padx=0, pady=0)
                category_label.pack(anchor="center", expand=True, pady=(2, 4))
            else:
                category_label = self._label(bank_cell, category, size=7, color="muted", anchor="w")
                category_label.pack(anchor="w")
            cells, figures, arrows = {}, {}, {}
            for field, column in (("buy", 1), ("sell", 2)):
                cell = tk.Frame(
                    table, bg=tint, highlightthickness=2, highlightbackground=tint, highlightcolor=tint,
                )
                cell.grid(row=index, column=column, sticky="nsew", pady=2)
                inner = tk.Frame(cell, bg=tint)
                inner.place(relx=0.5, rely=0.5, anchor="center")
                figure = self._label(
                    inner, "—", size=14, color="red" if field == "buy" else "blue", weight="bold", family=self.figure_font,
                )
                figure.pack(side="left")
                arrow = self._label(inner, "", size=10, color="muted", weight="bold")
                arrow.pack(side="left", padx=(3, 0))
                cells[field], figures[field], arrows[field] = cell, figure, arrow
            self.rate_display_labels[source] = {
                "row": bank_cell,
                "bank": bank_label,
                "category": category_label,
                "official": None,
                "buy": figures["buy"],
                "sell": figures["sell"],
                "official_arrow": None,
                "buy_arrow": arrows["buy"],
                "sell_arrow": arrows["sell"],
                "official_cell": None,
                "buy_cell": cells["buy"],
                "sell_cell": cells["sell"],
            }
        self._build_gold_row(table, row=len(source_details) + 1)
        self._refresh_exchange_rate_display()
        self._rate_pulse_after_id = self.root.after(0, self._tick_rate_pulse)

    def _build_gold_row(self, table, row: int) -> None:
        """Full-width gold row: title line, then USD/oz, USD/ដំឡឹង and USD/ជី at the same size."""
        # Weight 0: the gold row keeps its compact height and spare height goes to the bank rows.
        table.grid_rowconfigure(row, weight=0)
        tint = RATE_ROW_COLORS["GOLD"]
        cell = tk.Frame(table, bg=tint, padx=6, highlightthickness=2, highlightbackground=tint, highlightcolor=tint)
        cell.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=2)
        title_line = tk.Frame(cell, bg=tint)
        title_line.pack(fill="x", pady=(1, 0))
        bank_label = self._label(title_line, "GOLD", size=10, color="usd", weight="bold", anchor="w")
        bank_label.pack(side="left")
        category_label = self._label(title_line, "XAU/USD · oz", size=7, color="muted", anchor="w")
        category_label.pack(side="left", padx=(6, 0))
        inner = tk.Frame(cell, bg=tint)
        inner.pack(expand=True)
        figure_row = tk.Frame(inner, bg=tint)
        figure_row.pack()
        figure = self._label(figure_row, "—", size=14, color="usd", weight="bold", family=self.figure_font, pady=0)
        figure.pack(side="left")
        arrow = self._label(figure_row, "", size=10, color="muted", weight="bold", pady=0)
        arrow.pack(side="left", padx=(3, 0))
        local_units = {}
        for unit in ("damlung", "chi"):
            line = tk.Frame(inner, bg=tint)
            line.pack()
            value = self._label(line, "", size=14, color="usd", weight="bold", family=self.figure_font, pady=0)
            value.pack(side="left")
            name = self._label(line, "", size=14, color="usd", weight="bold", family=self.rate_group_font, pady=0)
            name.pack(side="left", padx=(4, 0))
            flag = tk.Label(line, bg=tint, bd=0, padx=0, pady=0)
            flag.pack(side="left", padx=(6, 0))
            unit_arrow = self._label(line, "", size=10, color="muted", weight="bold", pady=0)
            unit_arrow.pack(side="left", padx=(4, 0))
            local_units[unit] = {"line": line, "value": value, "name": name, "flag": flag, "arrow": unit_arrow}
        self.rate_display_labels["GOLD"] = {
            "row": cell,
            "bank": bank_label,
            "category": category_label,
            "official": figure,
            "buy": None,
            "sell": None,
            "official_arrow": arrow,
            "buy_arrow": None,
            "sell_arrow": None,
            "official_cell": cell,
            "buy_cell": None,
            "sell_cell": None,
            "local_units": local_units,
        }

    def _build_nbc_header_card(self, header) -> None:
        """Modern 'glass ticker' NBC card drawn on a canvas in the header's right column."""
        canvas = tk.Canvas(
            header,
            height=NBC_CARD_HEIGHTS[False],
            bg=COLORS["background"],
            highlightthickness=0,
            bd=0,
        )
        canvas.grid(row=0, column=2, sticky="ew")
        self.nbc_card = canvas
        self.nbc_canvas = canvas
        self._nbc_state: dict[str, object] = {}
        canvas.bind("<Configure>", lambda _event: self._draw_nbc_card(), add="+")

    def _nbc_canvas_width(self) -> int:
        width = self.nbc_canvas.winfo_width()
        if width <= 1:
            column = self.header.grid_bbox(2, 0)
            width = column[2] if column else width
        return width

    def nbc_text(self, tag: str) -> str:
        """Text of a named NBC card element (figure, caption, date, pill, unit)."""
        items = self.nbc_canvas.find_withtag(f"nbc_{tag}")
        return self.nbc_canvas.itemcget(items[0], "text") if items else ""

    def _draw_nbc_card(self) -> None:
        canvas = self.nbc_canvas
        canvas.delete("all")
        width = self._nbc_canvas_width()
        height = int(canvas.cget("height"))
        self._nbc_drawn_size = (width, height)
        if width <= 20:
            return
        state = self._nbc_state
        narrow = bool(self._rate_group_narrow)
        stale = bool(state.get("stale"))
        inset = 2
        path = rounded_rect_path(inset, inset, width - inset, height - inset, 16)
        canvas.create_polygon(*[value for point in path for value in point], fill=NBC_CARD_FILL, outline="")
        span = max(1.0, width - 2 * inset)
        for (x1, y1), (x2, y2) in zip(path, path[1:] + path[:1]):
            progress = ((x1 + x2) / 2 - inset) / span
            color = rate_pulse_color(*NBC_BORDER_GRADIENT, progress)
            canvas.create_line(x1, y1, x2, y2, fill=color, width=2)
        canvas.create_line(22, inset + 1, width - 22, inset + 1, fill="#2A3A5A")
        left = 18
        top = 20 if not narrow else 17
        dot_color = COLORS["muted"] if stale else "#4ADE80"
        canvas.create_oval(left - 4, top - 4, left + 4, top + 4, fill=dot_color, outline="", tags=("nbc_dot",))
        caption_size = 8 if narrow else 9
        top_row_color = COLORS["muted"] if not stale else "#FB923C"
        canvas.create_text(
            left + 10, top, text=NBC_CARD_TITLE, anchor="w", fill=top_row_color,
            font=(self.rate_group_font, caption_size + 1, "bold"), tags=("nbc_caption",),
        )
        canvas.create_text(
            width - 18, top, text=str(state.get("date") or ""), anchor="e",
            fill=top_row_color,
            font=(self.caption_font, caption_size, "bold"), tags=("nbc_date",),
        )
        bottom = height - (16 if not narrow else 14)
        # The rate and its trend pill are centred together, horizontally and between the top and bottom rows.
        figure_font = (self.figure_font, 28 if narrow else 38, "bold")
        figure_y = (top + bottom) / 2 + 1
        figure = str(state.get("figure") or "—")
        figure_width = tkfont.Font(root=self.root, font=figure_font).measure(figure)
        has_rate = figure != "—"
        riel_font = (self.rate_group_font, 24 if narrow else 32, "bold")
        riel_width = tkfont.Font(root=self.root, font=riel_font).measure("៛") + 4 if has_rate else 0
        trend = state.get("trend")
        pill_text = str(state.get("pill") or "")
        pill_font = (self.figure_font, 10 if narrow else 12, "bold")
        pill_width = tkfont.Font(root=self.root, font=pill_font).measure(pill_text) + 20 if trend in NBC_PILL_COLORS else 0
        gap = 12 if pill_width else 0
        logo = self._nbc_logos.get(narrow)
        logo_width = logo.width() + 10 if logo is not None else 0
        group_left = (width - (logo_width + figure_width + riel_width + gap + pill_width)) / 2
        if logo is not None:
            canvas.create_image(group_left, figure_y, image=logo, anchor="w", tags=("nbc_logo",))
            group_left += logo_width
        figure_color = COLORS["muted"] if stale else NBC_FIGURE_COLORS.get(str(trend), "#F8FAFC")
        canvas.create_text(
            group_left, figure_y, text=figure, anchor="w", fill=figure_color,
            font=figure_font, tags=("nbc_figure",),
        )
        if riel_width:
            canvas.create_text(
                group_left + figure_width + 4, figure_y + 2, text="៛", anchor="w", fill=figure_color,
                font=riel_font, tags=("nbc_riel",),
            )
        if pill_width:
            x0 = group_left + figure_width + riel_width + gap
            pill_height = 22 if narrow else 26
            path = rounded_rect_path(x0, figure_y - pill_height / 2, x0 + pill_width, figure_y + pill_height / 2, pill_height / 2, 6)
            background, foreground = NBC_PILL_COLORS[str(trend)]
            canvas.create_polygon(*[value for point in path for value in point], fill=background, outline=foreground, width=1)
            canvas.create_text(
                x0 + pill_width / 2, figure_y, text=pill_text, fill=foreground, font=pill_font, tags=("nbc_pill",),
            )
        canvas.create_text(
            left - 2, bottom, text="KHR / USD", anchor="w", fill=COLORS["muted"],
            font=(self.label_font, 8 if narrow else 9, "bold"), tags=("nbc_unit",),
        )
        history = [float(value) for value in self._nbc_history_values]
        if len(history) >= 2:
            spark_width = 96 if narrow else 120
            x_end = width - 18
            x_start = x_end - spark_width
            y_low, y_high = bottom + 6, bottom - 12
            low, high = min(history), max(history)
            spread = (high - low) or 1.0
            points = []
            for index, value in enumerate(history):
                x = x_start + spark_width * index / (len(history) - 1)
                y = y_low + (y_high - y_low) * ((value - low) / spread if high != low else 0.5)
                points.extend((x, y))
            canvas.create_line(*points, fill="#22D3EE", width=2, smooth=True, tags=("nbc_sparkline",))
            canvas.create_oval(points[-2] - 3, points[-1] - 3, points[-2] + 3, points[-1] + 3, fill="#8B5CF6", outline="")
            canvas.create_text(
                x_start - 8, bottom, text=f"{len(history)}-day", anchor="e", fill=COLORS["muted"],
                font=(self.label_font, 7 if narrow else 8), tags=("nbc_spark_label",),
            )

    def _build_private_rate_card(self, parent) -> None:
        """Dark private-rates card with a yellow title bar, summary strip, and sender rows."""
        card = tk.Frame(
            parent,
            bg=COLORS["surface"],
            highlightbackground=RATE_GROUP_ACCENT,
            highlightthickness=1,
        )
        card.grid(row=0, column=0, sticky="nsew")
        self.private_card = card
        self.rate_box = card
        # The status/button footer is a child of the card so it can be packed either
        # into the yellow title bar (wide window) or at the bottom of the card (narrow).
        self.rate_footer = tk.Frame(card, bg=RATE_GROUP_ACCENT)
        self.rate_top_bar = tk.Frame(card, bg=RATE_GROUP_ACCENT, padx=6, pady=3)
        self.rate_top_bar.pack(fill="x", side="top")
        self.rate_group_title_label = tk.Label(
            self.rate_top_bar,
            text="អត្រាប្តូរប្រាក់ឯកជន - Private rates",
            bg=RATE_GROUP_ACCENT,
            fg=COLORS["rate_text"],
            font=self._font(10, "bold", self.rate_group_font),
            anchor="center",
            justify="center",
        )
        self.rate_group_title_label.pack(side="left", fill="x", expand=True)
        self.rate_group_title_label.bind(
            "<Configure>",
            lambda _event: self._fit_centered_title(
                self.rate_group_title_label,
                10,
                6,
                family=self.rate_group_font,
            ),
            add="+",
        )
        self.rate_status_label = tk.Label(
            self.rate_footer,
            text=rate_group_status_label(self.values["rate_group_status"].get()),
            bg=COLORS["rate_text"],
            fg="#FFFFFF",
            font=self._font(7, "bold"),
            padx=4,
            pady=1,
            anchor="w",
        )
        self.rate_status_label.pack(side="left", anchor="w")
        summary_bg = "#1D2A44"
        self.rate_summary_frame = tk.Frame(card, bg=summary_bg, padx=8, pady=4)
        self.rate_summary_frame.pack(fill="x", side="top")
        self.rate_summary_frame.grid_columnconfigure(0, weight=1)
        self.rate_summary_labels: dict[str, tk.Label] = {}
        self.rate_summary_arrows: dict[str, tk.Label] = {}
        for row, direction in enumerate((KHR_TO_USD, USD_TO_KHR)):
            line = tk.Frame(self.rate_summary_frame, bg=summary_bg)
            line.grid(row=row, column=0, sticky="w")
            label = tk.Label(
                line,
                text=f"{DIRECTION_LABELS[direction]}  —",
                bg=summary_bg,
                fg=RATE_GROUP_DIRECTION_COLORS[direction],
                font=self._font(11, "bold"),
                padx=0,
                pady=0,
            )
            label.pack(side="left")
            arrow = tk.Label(line, text="", bg=summary_bg, fg=RATE_GROUP_MUTED_TEXT, font=self._font(11, "bold"))
            arrow.pack(side="left", padx=(4, 0))
            self.rate_summary_labels[direction] = label
            self.rate_summary_arrows[direction] = arrow
        self.rate_summary_caption = tk.Label(
            self.rate_summary_frame,
            text="posts · 15 min",
            bg=summary_bg,
            fg=RATE_GROUP_ACCENT,
            font=self._font(7),
            padx=0,
            pady=0,
        )
        self.rate_summary_caption.grid(row=0, column=1, sticky="ne")
        message_frame = tk.Frame(card, bg=COLORS["surface"])
        self.rate_message_frame = message_frame
        message_frame.pack(fill="both", expand=True, pady=(2, 2))
        self.rate_group_text = tk.Text(
            message_frame,
            width=1,
            height=1,
            wrap="word",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=self._font(9, family=self.rate_group_font),
            spacing1=0,
            spacing2=0,
            spacing3=0,
            cursor="arrow",
            state="disabled",
        )
        self._rate_group_font_tags: set[str] = set()
        self._configure_rate_group_tags(narrow=False)
        self.rate_group_text.pack(side="left", fill="both", expand=True)
        self.rate_group_scrollbar = tk.Scrollbar(
            message_frame,
            orient="vertical",
            command=self.rate_group_text.yview,
            width=8,
            bd=0,
            relief="flat",
            elementborderwidth=0,
            troughcolor=COLORS["surface"],
            bg=COLORS["border"],
            activebackground=RATE_GROUP_ACCENT,
            highlightthickness=0,
        )
        self.rate_group_scrollbar.pack(side="right", fill="y")
        self.rate_group_text.configure(yscrollcommand=self.rate_group_scrollbar.set)
        self.rate_group_text.bind("<MouseWheel>", self._scroll_rate_group)
        self.rate_group_button = tk.Button(
            self.rate_footer,
            text="CONNECT",
            command=self._toggle_rate_group_reader,
            bg=COLORS["rate_text"],
            fg="#FFFFFF",
            activebackground=COLORS["blue_dark"],
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=self._font(7, "bold"),
            padx=6,
            pady=1,
        )
        self.rate_group_button.pack(side="right", anchor="e", padx=(3, 0))
        self._rate_controls_in_top_bar: Optional[bool] = None
        self._arrange_rate_group_controls(narrow=False)
        self._render_rate_group_messages()

    def _fit_centered_title(
        self,
        label: tk.Label,
        preferred_size: int,
        minimum_size: int,
        family: Optional[str] = None,
    ) -> None:
        width = label.winfo_width()
        if width <= 1:
            return
        font = self._responsive_title_fonts.get(label)
        if font is None:
            font = tkfont.Font(
                root=self.root,
                family=family or self.khmer_title_font,
                size=preferred_size,
                weight="bold",
            )
            self._responsive_title_fonts[label] = font
        available_width = max(1, width - 12)
        fitted_size = minimum_size
        for size in range(preferred_size, minimum_size - 1, -1):
            font.configure(size=size)
            if font.measure(label.cget("text")) <= available_width:
                fitted_size = size
                break
        if self._responsive_title_sizes.get(label) != fitted_size:
            label.configure(
                font=self._font(fitted_size, "bold", family or self.khmer_title_font),
                anchor="center",
                justify="center",
            )
            self._responsive_title_sizes[label] = fitted_size

    def _sync_identity_wraplength(self, _event=None) -> None:
        body_width = self.dashboard_body.winfo_width()
        if body_width <= 1:
            return
        payment_width = round(body_width * 0.50) - 10
        identity_width = payment_width - 36
        each_identity_card = max(1, (identity_width - 14) // 2)
        for card, label in (
            (self.sender_card, self.sender_label),
            (self.bank_card, self.bank_label),
        ):
            padding = int(card.cget("padx"))
            wraplength = max(120, each_identity_card - 2 * padding)
            if int(label.cget("wraplength")) != wraplength:
                label.configure(wraplength=wraplength)

    def _refresh_exchange_rate_display(self) -> None:
        now = datetime.now(CAMBODIA_TIMEZONE)
        bank_rates = {source: rate for source, rate in self.exchange_rates.items() if source != "GOLD"}
        self.rate_age_label.configure(text=format_rate_status(bank_rates, now))
        for source, labels in self.rate_display_labels.items():
            rate = self.exchange_rates.get(source)
            stale = rate is None or rate.is_stale(now)
            tint = RATE_ROW_COLORS[source]
            if source == "GOLD":
                price = rate.official_rate if rate is not None else None
                values = {"official": format_gold_price(price) if price is not None else "—"}
                units = dict(zip(("damlung", "chi"), gold_local_units(price))) if price is not None else {}
                for unit, parts in labels["local_units"].items():
                    value_text = f"≈ ${units[unit]:,.2f}" if unit in units else ""
                    name_text = f"/ {GOLD_UNIT_NAMES[unit]}" if unit in units else ""
                    if parts["value"].cget("text") != value_text:
                        parts["value"].configure(text=value_text)
                        parts["name"].configure(text=name_text)
                        parts["flag"].configure(image=self._cambodia_flag if unit in units else "")
                effective = compact_effective_at(rate.effective_at) if rate is not None and rate.effective_at else ""
                category = "XAU/USD · oz" + (f" · {effective}" if effective else "")
                if labels["category"].cget("text") != category:
                    labels["category"].configure(text=category)
            else:
                _quote, buy, sell, _effective = format_rate_display_values(source, rate, now)
                values = {"buy": buy or "—", "sell": sell or "—"}
            for field, text in values.items():
                figure = labels[field]
                if figure.cget("text") != text:
                    figure.configure(text=text)
                has_value = text not in {"—", ""}
                # 2. One arrow at a time: the direction of the figure's last change, or none yet.
                trend = rate.trend(field) if rate is not None and not stale and has_value else None
                self._set_trend_label(labels[f"{field}_arrow"], trend)
                if source == "GOLD":
                    for parts in labels["local_units"].values():
                        self._set_trend_label(parts["arrow"], trend if parts["value"].cget("text") else None)
            labels["bank"].configure(fg=COLORS["muted"] if stale else COLORS["usd" if source == "GOLD" else "text"])
            labels["stale"] = stale
        self._refresh_nbc_header(now)

    def _set_trend_label(self, label: Optional[tk.Label], trend: Optional[str]) -> None:
        if label is None:
            return
        text = RATE_TREND_ARROWS.get(trend or "", "")
        color = RATE_TREND_COLORS.get(trend or "", COLORS["muted"])
        if label.cget("text") != text or label.cget("fg") != color:
            label.configure(text=text, fg=color)

    def _reload_nbc_history(self) -> None:
        try:
            self._nbc_history_values = list(self.nbc_history(7))
        except Exception:
            self._nbc_history_values = []
        self._nbc_state = {}

    def _refresh_nbc_header(self, now: datetime) -> None:
        rate = self.exchange_rates.get("NBC")
        state: dict[str, object] = {"figure": "—", "date": "", "trend": None, "pill": "", "stale": True}
        if rate is not None and rate.official_rate is not None:
            stale = rate.is_stale(now)
            effective = compact_effective_at(rate.effective_at) if rate.effective_at else ""
            state.update(
                figure=format_rate_value(rate.official_rate),
                date=(effective.upper() + (" · STALE" if stale else "")) if effective or stale else "",
                stale=stale,
            )
            trend = None if stale else rate.trend("official")
            if trend and rate.previous_official_rate is not None:
                difference = format_rate_value(abs(rate.official_rate - rate.previous_official_rate))
                sign = "+" if trend == "up" else "−"
                state.update(trend=trend, pill=f"{RATE_TREND_ARROWS[trend]} {sign}{difference}")
        state["history"] = tuple(self._nbc_history_values)
        if state != self._nbc_state:
            self._nbc_state = state
            self._draw_nbc_card()

    def _tick_rate_pulse(self) -> None:
        self._apply_rate_pulse()
        self._rate_pulse_after_id = self.root.after(
            RATE_PULSE_INTERVAL_MS,
            self._tick_rate_pulse,
        )

    def _apply_rate_pulse(self) -> None:
        progress = rate_pulse_progress(self._rate_pulse_step)
        self._rate_pulse_step += 1
        for source, labels in self.rate_display_labels.items():
            if source == "GOLD":
                figure_colors = ((labels["official"], RATE_PULSE_COLORS["gold"]),)
            else:
                figure_colors = (
                    (labels["buy"], RATE_PULSE_COLORS["buy"]),
                    (labels["sell"], RATE_PULSE_COLORS["sell"]),
                )
            for label, (base, highlight) in figure_colors:
                if labels.get("stale"):
                    label.configure(fg=COLORS["muted"])
                else:
                    label.configure(fg=rate_pulse_color(base, highlight, progress))

    def _build_ticker(self) -> None:
        """Scrolling strip in the empty part of the tab row (never covers the tabs)."""
        self.ticker = tk.Canvas(self.root, bg=COLORS["background"], highlightthickness=0, bd=0, height=30)
        self.notebook.bind("<Configure>", self._position_ticker, add="+")
        self._ticker_after_id = self.root.after(TICKER_INTERVAL_MS, self._tick_ticker)

    def _tab_strip_geometry(self) -> Optional[tuple[int, int]]:
        """(right edge of the last tab, tab-row height) in notebook coordinates."""
        notebook = self.notebook
        width = notebook.winfo_width()
        if width <= 1:
            return None

        def on_tab(x: int, y: int) -> bool:
            try:
                return notebook.index(f"@{x},{y}") != ""
            except tk.TclError:
                return False

        height = max((y + 1 for y in range(0, 80) if on_tab(10, y)), default=0)
        if not height:
            return None
        middle = height // 2
        right = max((x + 1 for x in range(0, width, 2) if on_tab(x, middle)), default=0)
        return (right, height) if right else None

    def _position_ticker(self, _event=None) -> None:
        geometry = self._tab_strip_geometry()
        if geometry is None:
            return
        self._ticker_tabs = geometry
        right, height = geometry
        left = right + 18
        width = self.notebook.winfo_width() - left
        if width < 120:
            self.ticker.place_forget()
            return
        self.ticker.place(in_=self.notebook, x=left, y=0, width=width, height=height)
        tk.Misc.lift(self.ticker)  # Canvas.lift() raises canvas items, not the widget
        self.ticker.update_idletasks()
        self._render_ticker(force=True)

    def _current_ticker_segments(self) -> list[tuple[str, str]]:
        now = datetime.now(CAMBODIA_TIMEZONE)
        return ticker_segments(self._today_summary, self.fuel_prices, now.date(), self.exchange_rates.get("GOLD"), now)

    def ticker_text(self) -> str:
        return "".join(text for text, _color in self._current_ticker_segments())

    def _ticker_font(self, khmer: bool) -> tkfont.Font:
        if khmer not in self._ticker_fonts:
            family = self.rate_group_font if khmer else self.figure_font
            self._ticker_fonts[khmer] = tkfont.Font(root=self.root, family=family, size=TICKER_FONT_SIZE, weight="bold")
        return self._ticker_fonts[khmer]

    def _render_ticker(self, force: bool = False) -> None:
        if not hasattr(self, "ticker"):
            return
        today = datetime.now(CAMBODIA_TIMEZONE).date()
        segments = self._current_ticker_segments()
        canvas_width = self.ticker.winfo_width()
        canvas_height = self.ticker.winfo_height()
        key = (tuple(segments), canvas_width, canvas_height)
        if not force and key == self._ticker_drawn:
            return
        self._ticker_drawn = key
        self._ticker_date = today
        self.ticker.delete("ticker")
        if canvas_width <= 1:
            self._ticker_cycle = 0.0
            return
        pieces = [(text, color, self._ticker_font(_is_khmer(text))) for text, color in segments]
        icon_height = max(14, min(26, canvas_height - 12))
        icon_width = int(icon_height * 1.6)

        def width_of(text: str, color: str, font: tkfont.Font) -> int:
            return icon_width + 4 if color == TICKER_GOLD_ICON else font.measure(text)

        content = sum(width_of(*piece) for piece in pieces)
        cycle = float(content + TICKER_GAP_PX)
        self._ticker_cycle = cycle
        if not -cycle < self._ticker_offset <= 0:
            self._ticker_offset = 0.0
        y = canvas_height / 2
        x = self._ticker_offset
        for _copy in range(max(2, math.ceil(canvas_width / cycle) + 1)):
            for text, color, font in pieces:
                if color == TICKER_GOLD_ICON:
                    self._draw_gold_bar(x, y, icon_width, icon_height)
                elif color == TICKER_GOLD_TEXT:
                    self.ticker.create_text(x + 1, y + 2, text=text, fill=TICKER_GOLD_SHADOW, font=font, anchor="w", tags=("ticker",))
                    self.ticker.create_text(x, y, text=text, fill=COLORS["usd"], font=font, anchor="w", tags=("ticker", "gold_text"))
                else:
                    self.ticker.create_text(x, y, text=text, fill=COLORS[color], font=font, anchor="w", tags=("ticker",))
                x += width_of(text, color, font)
            x += TICKER_GAP_PX

    def _draw_gold_bar(self, x: float, y: float, width: int, height: int) -> None:
        """A small gold ingot: dark outline, bright top face, warm front face and a shine line."""
        top, bottom = y - height / 2, y + height / 2
        inset = width * 0.18
        face_top = top + height * 0.38
        tags = ("ticker", "gold_icon")
        self.ticker.create_polygon(
            x + inset, top, x + width - inset, top, x + width, face_top, x, face_top,
            fill="#FFE08A", outline="#8A6410", width=1, tags=tags,
        )
        self.ticker.create_polygon(
            x, face_top, x + width, face_top, x + width, bottom, x, bottom,
            fill="#E0A82E", outline="#8A6410", width=1, tags=tags,
        )
        self.ticker.create_line(
            x + inset + 2, top + 2, x + width * 0.55, top + 2, fill="#FFF7D6", width=2, tags=tags,
        )
        self.ticker.create_line(
            x + 3, bottom - 3, x + width - 3, bottom - 3, fill="#B07D18", width=1, tags=tags,
        )

    def _tick_ticker(self) -> None:
        self._ticker_after_id = None
        try:
            if datetime.now(CAMBODIA_TIMEZONE).date() != self._ticker_date:
                self._render_ticker(force=True)
            if self._ticker_cycle > 0:
                step = TICKER_STEP_PX
                self._ticker_offset -= step
                if self._ticker_offset <= -self._ticker_cycle:
                    self._ticker_offset += self._ticker_cycle
                    self.ticker.move("ticker", self._ticker_cycle - step, 0)
                else:
                    self.ticker.move("ticker", -step, 0)
            self._ticker_after_id = self.root.after(TICKER_INTERVAL_MS, self._tick_ticker)
        except tk.TclError:
            return

    def _on_root_destroy(self, event) -> None:
        if event.widget is not self.root:
            return
        for attribute in ("_rate_pulse_after_id", "_rate_group_start_after_id", "_rate_group_glow_after_id", "_ticker_after_id"):
            after_id = getattr(self, attribute, None)
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)

    def _arrange_rate_group_controls(self, narrow: bool) -> None:
        """Share the title bar with the controls when wide; use a bottom footer when narrow."""
        in_top_bar = not narrow
        if self._rate_controls_in_top_bar == in_top_bar:
            return
        self._rate_controls_in_top_bar = in_top_bar
        self.rate_footer.pack_forget()
        if in_top_bar:
            self.rate_footer.pack(in_=self.rate_top_bar, side="right", anchor="e", padx=(4, 0))
        else:
            self.rate_footer.pack(
                in_=self.private_card,
                fill="x",
                side="bottom",
                before=self.rate_summary_frame,
            )
        self.rate_footer.lift()
        self._update_rate_status_chip()

    def _configure_rate_group_tags(self, narrow: bool) -> None:
        sizes = RATE_GROUP_FONT_SIZES[narrow]
        self._rate_group_sizes = sizes
        text = self.rate_group_text
        for index, row_color in enumerate(RATE_GROUP_ROW_COLORS):
            text.tag_configure(f"message_row_{index}", background=row_color)
        text.tag_configure("glow", background=RATE_GROUP_GLOW_COLOR)
        # Colour tags carry no font; font tags are chosen per segment so Khmer text
        # uses the Khmer font while Latin/number segments keep shorter lines.
        text.tag_configure("sender", foreground=COLORS["text"])
        text.tag_configure("time", foreground=RATE_GROUP_MUTED_TEXT)
        text.tag_configure("edited", foreground=RATE_GROUP_MUTED_TEXT)
        for direction, name in ((KHR_TO_USD, "k2u"), (USD_TO_KHR, "u2k"), (None, "none")):
            color = RATE_GROUP_DIRECTION_COLORS[direction]
            text.tag_configure(f"direction_{name}", foreground=color)
            text.tag_configure(f"rate_{name}", foreground=color)
        for trend, color in RATE_TREND_COLORS.items():
            text.tag_configure(f"trend_{trend}", foreground=color)
        text.tag_configure("gap", foreground=RATE_GROUP_MUTED_TEXT)
        text.tag_configure("size", foreground=COLORS["text"])
        text.tag_configure("banks", foreground=RATE_GROUP_MUTED_TEXT)
        text.tag_configure("plain", foreground="#A9B4C6")
        text.tag_configure("note", foreground=RATE_GROUP_MUTED_TEXT)
        text.tag_configure("faded", foreground=RATE_GROUP_FADED_TEXT)
        measure = tkfont.Font(root=self.root, family="Segoe UI", size=sizes["tag"], weight="bold")
        indent = 6
        rate_stop = indent + measure.measure("USD→KHR") + 10
        text.configure(tabs=(rate_stop,))
        text.tag_configure("offer_line", lmargin1=indent, lmargin2=rate_stop)
        text.tag_configure("detail_line", lmargin1=rate_stop, lmargin2=rate_stop)
        text.tag_configure("indented", lmargin1=indent + 4, lmargin2=indent + 4)
        text.tag_configure("header_line", lmargin1=4, lmargin2=4, spacing1=3)
        for label in self.rate_summary_labels.values():
            label.configure(font=self._font(9 if narrow else 12, "bold", self.figure_font))
        for arrow in self.rate_summary_arrows.values():
            arrow.configure(font=self._font(9 if narrow else 11, "bold"))

    def _refresh_rate_group_summary(self) -> None:
        bounds = rate_group_summary_bounds(self.rate_group_messages.values())
        summary = rate_group_summary_text(self.rate_group_messages.values())
        for direction, label in self.rate_summary_labels.items():
            if label.cget("text") != summary[direction]:
                label.configure(text=summary[direction])
            trend = None
            if direction in bounds:
                low, high = bounds[direction]
                midpoint = (low + high) / 2
                current, previous = self._rate_group_summary_trend.get(direction, (None, None))
                if current is None:
                    self._rate_group_summary_trend[direction] = (midpoint, None)
                elif midpoint != current:
                    self._rate_group_summary_trend[direction] = (midpoint, current)
                current, previous = self._rate_group_summary_trend[direction]
                trend = rate_trend(current, previous)
            self._set_trend_label(self.rate_summary_arrows[direction], trend)

    def _scroll_rate_group(self, event) -> str:
        self.rate_group_text.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _build_status_card(self, parent) -> None:
        card = self._card(parent, row=0, column=0, sticky="ew", pady=(0, 10)); self.status_card = card
        self._label(card, "SYSTEM STATUS", size=10, color="muted", weight="bold").pack(anchor="w", padx=17, pady=(14, 8))
        self.health_labels = {}
        for label, name in (("Telegram session", "telegram"), ("Speaker", "speaker"), ("PayWay source", "source")):
            row = tk.Frame(card, bg=COLORS["surface"], padx=17, pady=4); row.pack(fill="x"); self._label(row, label, size=10).pack(side="left")
            status = self._label(row, "", size=9, color="amber", weight="bold"); status.pack(side="right"); self.health_labels[name] = status
        tk.Frame(card, bg=COLORS["surface"], height=9).pack(); self._refresh_health()

    def _configure_history_columns(self, parent, narrow: Optional[bool] = None) -> None:
        narrow = self._history_narrow if narrow is None else narrow
        parent.grid_columnconfigure(0, weight=0, minsize=118 if narrow else 165)
        parent.grid_columnconfigure(1, weight=5)
        parent.grid_columnconfigure(2, weight=3)
        parent.grid_columnconfigure(3, weight=0, minsize=64 if narrow else 110)

    def _apply_history_columns(self, narrow: bool) -> None:
        self._configure_history_columns(self.history_headings, narrow)
        if self.history_canvas.winfo_width() > 1:
            self._fix_history_columns(self.history_headings, self._history_column_widths(narrow), spare=True)
        for column, label in enumerate(self.history_heading_labels):
            if column in (2, 3):
                font = self._font(9, "bold", self.condensed_font) if narrow else self._font(11, "bold")
            else:
                font = self._font(10 if narrow else 11, "bold")
            label.configure(font=font, padx=6 if narrow else 10)

    def _resize_history(self, event) -> None:
        self.history_canvas.itemconfigure(self.history_window, width=event.width)
        # Re-flow wrapped sender/bank text when the list width changes noticeably.
        if self._history_rows and abs(event.width - getattr(self, "_history_render_width", 0)) > 8:
            if getattr(self, "_history_rerender_id", None) is None:
                self._history_rerender_id = self.root.after_idle(self._rerender_history)

    def _rerender_history(self) -> None:
        self._history_rerender_id = None
        self._render_history(self._history_rows)

    def _history_column_widths(self, narrow: bool) -> list[int]:
        width = self.history_canvas.winfo_width()
        amount, time_width = (118, 64) if narrow else (165, 110)
        rest = max(0, width - amount - time_width)
        return [amount, rest * 11 // 20, rest - rest * 11 // 20, time_width]

    @staticmethod
    def _fix_history_columns(parent, widths: list[int], spare: bool = False) -> None:
        """Pin the four columns to the computed widths so rows and headings stay aligned.

        The heading strip can be wider than the list (when the list scrollbar shows), so headings
        put that extra width in an empty fifth column instead of widening a real column.
        """
        if not any(widths):
            return
        for column, width in enumerate(widths):
            parent.grid_columnconfigure(column, minsize=width, weight=0 if spare else (1 if column == 1 else 0))
        parent.grid_columnconfigure(4, weight=1 if spare else 0)

    def _history_overflows(self) -> bool:
        content = getattr(self, "_history_content_height", self._history_row_count * HISTORY_ROW_HEIGHT)
        return content > int(self.history_canvas.cget("height"))

    def _update_history_scrollbar(self) -> None:
        if self._history_overflows():
            self.history_scrollbar.grid()
        else:
            self.history_scrollbar.grid_remove()

    def _scroll_history(self, event) -> str:
        if self._history_overflows():
            direction = -1 if event.delta > 0 else 1
            self.history_canvas.yview_scroll(direction, "units")
            return "break"
        return self._scroll_dashboard(event) or "break"

    def _bind_history_scroll(self, widget) -> None:
        widget.bind("<MouseWheel>", self._scroll_history)

    def _render_history(self, rows: list[dict[str, object]]) -> None:
        self._history_rows = list(rows)
        narrow = self._history_narrow
        for child in self.history_inner.winfo_children():
            child.destroy()
        self._history_row_count = len(rows)
        self._history_render_width = self.history_canvas.winfo_width()
        column_widths = self._history_column_widths(narrow) if self._history_render_width > 1 else [0, 0, 0, 0]
        padx = 6 if narrow else 10
        content_height = 0
        self._fix_history_columns(self.history_headings, column_widths, spare=True)
        if not rows:
            empty = tk.Label(self.history_inner, text="NO ANNOUNCED PAYMENTS TODAY", bg=COLORS["surface"], fg=COLORS["muted"], font=self._font(12, "bold"), anchor="center")
            empty.grid(row=0, column=0, sticky="nsew"); self.history_inner.grid_columnconfigure(0, weight=1); self._bind_history_scroll(empty)
        for index, row in enumerate(rows):
            background = COLORS["surface"] if index % 2 == 0 else COLORS["surface_alt"]
            line = tk.Frame(self.history_inner, bg=background, height=HISTORY_ROW_HEIGHT)
            line.grid(row=index, column=0, sticky="ew"); line.grid_propagate(False)
            line.grid_rowconfigure(0, weight=1)
            self.history_inner.grid_columnconfigure(0, weight=1)
            self._configure_history_columns(line, narrow)
            self._fix_history_columns(line, column_widths)
            timestamp = str(row.get("received_at") or "")
            try: shown_time = datetime.fromisoformat(timestamp).astimezone().strftime("%I:%M %p")
            except (ValueError, TypeError): shown_time = "—"
            row_foreground = COLORS[amount_color(row.get("currency"))]
            main_size = 13 if narrow else 14
            condensed = (self.condensed_font, 11) if narrow else (None, 14)
            values = (
                (format_payment_amount(row.get("amount"), row.get("currency")), self._font(main_size, "bold")),
                (str(row.get("sender_name") or "—"), self._font(main_size, "bold")),
                (str(row.get("bank") or "OTHER BANK"), self._font(condensed[1], "normal", condensed[0])),
                (shown_time, self._font(condensed[1], "normal", condensed[0])),
            )
            lines = 1
            fitted = []
            for column, (text, font) in enumerate(values):
                measured = tkfont.Font(root=self.root, font=font)
                shown, needed = fit_two_lines(text, measured, column_widths[column] - 2 * padx - 4)
                fitted.append((shown, font))
                lines = max(lines, needed)
            row_height = HISTORY_ROW_HEIGHT_TWO_LINES if lines > 1 else HISTORY_ROW_HEIGHT
            line.configure(height=row_height)
            content_height += row_height
            for column, (text, font) in enumerate(fitted):
                label = tk.Label(
                    line, text=text, bg=background, fg=row_foreground, font=font,
                    anchor=HISTORY_COLUMN_ANCHORS[column], justify=HISTORY_COLUMN_JUSTIFY[column], padx=padx, bd=0,
                )
                label.grid(row=0, column=column, sticky="nsew"); self._bind_history_scroll(label)
            self._bind_history_scroll(line)
        self._history_content_height = content_height
        self._bind_history_scroll(self.history_canvas)
        self.history_inner.update_idletasks()
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        self.history_canvas.yview_moveto(0)
        self._update_history_scrollbar()

    def _build_summary_card(self, parent) -> None:
        card = self._card(parent, row=1, column=0, sticky="ew", pady=(0, 10)); self.today_card = card
        self._label(card, "TODAY", size=10, color="muted", weight="bold").grid(row=0, column=0, columnspan=3, sticky="w", padx=17, pady=(14, 8))
        for index, (name, caption, color) in enumerate((("today", "PAYMENTS", "text"), ("today_khr", "KHR", "green"), ("today_usd", "USD", "blue"))):
            card.grid_columnconfigure(index, weight=1); cell = tk.Frame(card, bg=COLORS["surface"]); cell.grid(row=1, column=index, sticky="ew", padx=9, pady=(0, 14))
            self._label(cell, variable=self.values[name], size=15, color=color, weight="bold").pack(); self._label(cell, caption, size=8, color="muted", weight="bold").pack()

    def _build_controls_card(self, parent) -> None:
        card = self._card(parent, row=2, column=0, sticky="ew", pady=(0, 10)); self.controls_card = card
        self._label(card, "CONTROLS", size=10, color="muted", weight="bold").pack(anchor="w", padx=17, pady=(14, 10))
        self.mute_button = self._button(card, "SPEAKER ON", self._toggle_mute, accent="green_dark"); self.mute_button.pack(fill="x", padx=16, pady=5)
        self._button(card, "TEST SPEAKER", lambda: self.announce_test(SPEAKER_TEST)).pack(fill="x", padx=16, pady=5)
        self._button(card, "SETTINGS / DIAGNOSTICS", lambda: self.notebook.select(self.diagnostics_tab)).pack(fill="x", padx=16, pady=5)
        self.controls_setup_label = self._label(card, variable=self.values["setup"], size=9, color="muted", wraplength=250, justify="left")
        self.controls_setup_label.pack(fill="x", padx=17, pady=(12, 15))

    def _resize_dashboard_content(self, event) -> None:
        self.dashboard_canvas.itemconfigure(self.dashboard_window, width=event.width)
        self._fit_history_height()
        self._schedule_dashboard_scroll_update()

    def _schedule_dashboard_scroll_update(self, _event=None) -> None:
        if self._dashboard_scroll_update_id is None:
            self._dashboard_scroll_update_id = self.root.after_idle(self._update_dashboard_scrollregion)

    def _update_dashboard_scrollregion(self) -> None:
        self._dashboard_scroll_update_id = None
        self.dashboard_canvas.configure(scrollregion=self.dashboard_canvas.bbox("all"))
        content_height = self.dashboard_body.winfo_reqheight()
        viewport_height = self.dashboard_canvas.winfo_height()
        if content_height > viewport_height and self.dashboard_scrollbar.winfo_manager() != "grid":
            self.dashboard_scrollbar.grid()
        elif content_height <= viewport_height and self.dashboard_scrollbar.winfo_manager() == "grid":
            self.dashboard_scrollbar.grid_remove()

    def _resize_operations_content(self, event) -> None:
        self.operations_canvas.itemconfigure(self.operations_window, width=event.width)
        self._schedule_operations_scroll_update()

    def _schedule_operations_scroll_update(self, _event=None) -> None:
        if self._operations_scroll_update_id is None:
            self._operations_scroll_update_id = self.root.after_idle(self._update_operations_scrollregion)

    def _update_operations_scrollregion(self) -> None:
        self._operations_scroll_update_id = None
        self.operations_canvas.configure(scrollregion=self.operations_canvas.bbox("all"))
        content_height = self.operations_body.winfo_reqheight()
        viewport_height = self.operations_canvas.winfo_height()
        if content_height > viewport_height and self.operations_scrollbar.winfo_manager() != "grid":
            self.operations_scrollbar.grid()
        elif content_height <= viewport_height and self.operations_scrollbar.winfo_manager() == "grid":
            self.operations_scrollbar.grid_remove()

    def _scroll_dashboard(self, event) -> Optional[str]:
        widget = event.widget
        while widget is not None:
            if widget is self.operations_body or widget is self.operations_canvas:
                self.operations_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            if widget is self.dashboard_body or widget is self.dashboard_canvas:
                self.dashboard_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            widget = getattr(widget, "master", None)
        return None

    def _schedule_responsive_layout(self, event=None) -> None:
        if event is not None and event.widget is not self.root:
            return
        if self._layout_after_id is not None:
            self.root.after_cancel(self._layout_after_id)
        self._layout_after_id = self.root.after(80, self._apply_responsive_layout)

    def _place_startup_window(self, attempts_left: int) -> None:
        monitors = active_monitors()
        target = preferred_secondary_monitor(monitors)
        if target is not None:
            left, top = int(target["left"]), int(target["top"])
            width = max(900, int(target["right"]) - left)
            height = max(600, int(target["bottom"]) - top)
            self.root.state("normal")
            self.root.geometry(f"{width}x{height}+{left}+{top}")
            self.root.update_idletasks()
            self.root.state("zoomed")
            return
        if attempts_left > 1:
            self.root.after(1000, lambda: self._place_startup_window(attempts_left - 1))
            return
        primary = next((monitor for monitor in monitors if monitor["primary"]), None)
        self.root.state("normal")
        if primary is not None:
            width, height = 1180, 800
            left = int(primary["left"]) + max(0, (int(primary["right"]) - int(primary["left"]) - width) // 2)
            top = int(primary["top"]) + max(0, (int(primary["bottom"]) - int(primary["top"]) - height) // 2)
            self.root.geometry(f"{width}x{height}+{left}+{top}")

    def _apply_responsive_layout(self) -> None:
        self._layout_after_id = None
        mode = responsive_layout_mode(self.root.winfo_height())
        narrow_header = narrow_header_mode(self.root.winfo_width())
        layout_key = (mode, narrow_header)
        self._sync_identity_wraplength()
        compact = mode != "normal"
        self.header.configure(padx=18 if compact or narrow_header else 28, pady=3)
        if layout_key != self._layout_mode:
            self._layout_mode = layout_key
            title_size = 20 if narrow_header else 24
            self.title_primary_label.configure(font=self._font(title_size, family=self.khmer_title_font))
            self.title_secondary_label.configure(font=self._font(title_size, family=self.khmer_title_font))
            self.clock_label.configure(font=self._font(42 if narrow_header else 56, "bold"))
        if self._rate_group_narrow != narrow_header:
            self._rate_group_narrow = narrow_header
            self._configure_rate_group_tags(narrow_header)
            self._render_rate_group_messages(keep_scroll=True)
            self._apply_rate_table_sizes(narrow_header)
            self._refresh_exchange_rate_display()
            self.nbc_canvas.configure(height=NBC_CARD_HEIGHTS[narrow_header])
            self._draw_nbc_card()
            self._history_narrow = narrow_header
            self._apply_history_columns(narrow_header)
            self._render_history(self._history_rows)
        self.root.update_idletasks()
        private_width = self.private_card.winfo_width()
        compact_controls = narrow_header or (private_width > 1 and private_width < 300)
        self._arrange_rate_group_controls(compact_controls)
        self.rate_status_label.configure(font=self._font(6 if narrow_header else 7, "bold"))
        self.rate_group_button.configure(font=self._font(6 if narrow_header else 7, "bold"))
        for card in (self.sender_card, self.bank_card):
            card.configure(padx=12 if compact else 16, pady=4 if compact else 6)
        self.sender_label.configure(font=self._font(18 if compact else 21, "bold"))
        self.bank_label.configure(font=self._font(18 if compact else 21, "bold"))
        self.payment_card.grid_rowconfigure(1, minsize=80 if mode == "short" else 90 if compact else 96)
        if compact:
            self.controls_setup_label.pack_forget()
        elif not self.controls_setup_label.winfo_manager():
            self.controls_setup_label.pack(fill="x", padx=17, pady=(12, 15))
        self._amount_base_size = 42 if mode == "short" else 56
        self._fit_amount()
        self.payment_card.grid_configure(columnspan=1, padx=(0, 10))
        self.dashboard_side.grid()
        self._sync_identity_wraplength()
        card_width = self.rate_card.winfo_width()
        if card_width > 1 and int(self.rate_age_label.cget("wraplength")) != card_width - 16:
            self.rate_age_label.configure(wraplength=card_width - 16)
        self._fit_history_height()
        self._fit_rate_figures()
        if getattr(self, "_nbc_drawn_size", None) != (self._nbc_canvas_width(), int(self.nbc_canvas.cget("height"))):
            self._draw_nbc_card()
        self._schedule_dashboard_scroll_update()

    def _fit_rate_figures(self) -> None:
        """Shrink bank figures (never the cells) so each figure plus its arrow fits on one line."""
        narrow = bool(self._rate_group_narrow)
        base_size, arrow_size = (12, 6) if narrow else (18, 10)
        cells = [
            (labels[field], labels[f"{field}_cell"])
            for source, labels in self.rate_display_labels.items() if source != "GOLD"
            for field in ("buy", "sell")
        ]
        widths = [cell.winfo_width() for _figure, cell in cells if cell.winfo_width() > 1]
        if not widths:
            return
        available = min(widths) - 8
        texts = [figure.cget("text") for figure, _cell in cells] + ["4,444"]
        arrow_width = tkfont.Font(root=self.root, family="Segoe UI", size=arrow_size, weight="bold").measure("▲▼")
        size = base_size
        while size > 9:
            font = tkfont.Font(root=self.root, family=self.figure_font, size=size, weight="bold")
            if max(font.measure(text) for text in texts) + arrow_width <= available:
                break
            size -= 1
        if getattr(self, "_rate_figure_size", None) != size:
            self._rate_figure_size = size
            for figure, _cell in cells:
                figure.configure(font=self._font(size, "bold", self.figure_font))

    def _fit_history_height(self) -> None:
        """Let the recent-payments list use the space left under the payment card."""
        self.root.update_idletasks()
        available = self.dashboard_canvas.winfo_height()
        if available <= 1:
            return
        current = int(self.history_canvas.cget("height"))
        other = self.dashboard_body.winfo_reqheight() - current
        target = max(2 * HISTORY_ROW_HEIGHT, min(10 * HISTORY_ROW_HEIGHT, available - other - 4))
        if abs(target - current) > 1:
            self.history_canvas.configure(height=target)
            self._update_history_scrollbar()

    def _apply_rate_table_sizes(self, narrow: bool) -> None:
        """Compact bank-table and summary typography for windows narrower than 1080 px."""
        figure_size, arrow_size, bank_size = (12, 6, 8) if narrow else (18, 10, 12)
        self._rate_figure_size = None
        for source, labels in self.rate_display_labels.items():
            labels["row"].configure(padx=2 if narrow else 6)
            labels["bank"].configure(font=self._font(bank_size, "bold"))
            logo = self._bank_logos.get(source, {}).get(narrow)
            if logo is not None:
                labels["category"].configure(image=logo)
            else:
                labels["category"].configure(font=self._font(6 if narrow else 8), justify="left")
            for field in ("official", "buy", "sell"):
                if labels.get(field) is not None:
                    labels[field].configure(font=self._font(figure_size, "bold", self.figure_font))
                    labels[f"{field}_arrow"].configure(font=self._font(arrow_size, "bold"), padx=0)
            for parts in labels.get("local_units", {}).values():
                parts["value"].configure(font=self._font(figure_size, "bold", self.figure_font))
                parts["name"].configure(font=self._font(GOLD_UNIT_NAME_SIZES[narrow], "bold", self.rate_group_font))
                parts["arrow"].configure(font=self._font(arrow_size, "bold"), padx=0)
        self._cambodia_flag = cambodia_flag_image(self.root, CAMBODIA_FLAG_HEIGHTS[narrow])
        for parts in self.rate_display_labels["GOLD"]["local_units"].values():
            if parts["value"].cget("text"):
                parts["flag"].configure(image=self._cambodia_flag)
        for column, header in self.rate_table_headers.items():
            family = None if column == 0 else self.khmer_title_font
            header.configure(font=self._font(8 if narrow else 9, "bold", family))
        if narrow:
            self.rate_summary_caption.grid_configure(row=2, column=0, sticky="e")
        else:
            self.rate_summary_caption.grid_configure(row=0, column=1, sticky="ne")

    def _build_diagnostics_tab(self) -> None:
        outer = tk.Frame(self.diagnostics_tab, bg=COLORS["background"], padx=10, pady=10); outer.pack(fill="both", expand=True)
        tools = ttk.Notebook(outer, style="Dark.TNotebook"); tools.pack(fill="both", expand=True); self.diagnostic_notebook = tools
        setup_page = tk.Frame(tools, bg=COLORS["background"])
        parser_page = tk.Frame(tools, bg=COLORS["background"])
        operations_page = tk.Frame(tools, bg=COLORS["background"], padx=8, pady=8)
        self.parser_page = parser_page
        self.operations_page = operations_page
        tools.add(setup_page, text="  TELEGRAM SETUP  ")
        tools.add(parser_page, text="  SAFE PARSER TEST  ")
        tools.add(operations_page, text="  OPERATIONS  ")
        operations_viewport = tk.Frame(operations_page, bg=COLORS["background"])
        operations_viewport.pack(fill="both", expand=True)
        operations_viewport.grid_rowconfigure(0, weight=1)
        operations_viewport.grid_columnconfigure(0, weight=1)
        self.operations_canvas = tk.Canvas(
            operations_viewport,
            bg=COLORS["background"],
            highlightthickness=0,
            bd=0,
        )
        self.operations_canvas.grid(row=0, column=0, sticky="nsew")
        self.operations_scrollbar = ttk.Scrollbar(
            operations_viewport,
            orient="vertical",
            command=self.operations_canvas.yview,
        )
        self.operations_scrollbar.grid(row=0, column=1, sticky="ns")
        self.operations_scrollbar.grid_remove()
        self.operations_canvas.configure(yscrollcommand=self.operations_scrollbar.set)
        operations_body = tk.Frame(self.operations_canvas, bg=COLORS["background"])
        self.operations_body = operations_body
        self.operations_window = self.operations_canvas.create_window(
            (0, 0), window=operations_body, anchor="nw"
        )
        operations_body.bind("<Configure>", self._schedule_operations_scroll_update)
        self.operations_canvas.bind("<Configure>", self._resize_operations_content)
        operations_body.grid_columnconfigure(0, weight=1)
        self._build_status_card(operations_body)
        self._build_summary_card(operations_body)
        self._build_controls_card(operations_body)
        operations_body.grid_rowconfigure(1, weight=1)
        commissioning = self._card(setup_page); commissioning.pack(fill="both", expand=True); self._label(commissioning, "TELEGRAM COMMISSIONING", size=12, weight="bold").grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 8))
        fields = (("Expected source", "expected_source"), ("Observed group", "group_title"), ("Observed chat ID", "chat_id"), ("Sender username", "sender_username"), ("Sender numeric ID", "sender_id"), ("Matches expected source", "source_match"))
        for row_index, (label, name) in enumerate(fields, start=1):
            self._label(commissioning, label, size=9, color="muted", weight="bold").grid(row=row_index, column=0, sticky="nw", padx=(16, 20), pady=3)
            self._label(commissioning, variable=self.values[name], size=10, wraplength=700, justify="left").grid(row=row_index, column=1, sticky="w", pady=3)
        buttons = tk.Frame(commissioning, bg=COLORS["surface"]); buttons.grid(row=7, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 5))
        self.copy_chat_button = self._button(buttons, "COPY CHAT ID", self._copy_chat_id); self.copy_chat_button.pack(side="left", padx=(0, 5))
        self.save_group_button = self._button(buttons, "ADD GROUP ID", self._save_group); self.save_group_button.pack(side="left", padx=5)
        self.copy_sender_button = self._button(buttons, "COPY SENDER ID", self._copy_sender_id); self.copy_sender_button.pack(side="left", padx=5)
        self.verify_source_button = self._button(buttons, "VERIFY & SAVE", self._verify_source, accent="blue_dark"); self.verify_source_button.pack(side="left", padx=5)
        self.production_button = self._button(buttons, "SWITCH TO PRODUCTION", self._switch_to_production, accent="green_dark"); self.production_button.pack(side="left", padx=5)
        self._label(commissioning, variable=self.values["commissioning"], size=9, color="muted", wraplength=950, justify="left").grid(row=8, column=0, columnspan=2, sticky="w", padx=16, pady=(5, 14))
        self._refresh_commissioning_controls()
        tests = self._card(parser_page); tests.pack(fill="both", expand=True); self._label(tests, "SAFE PARSER TEST — NEVER ADDED TO PRODUCTION HISTORY", size=10, color="muted", weight="bold").pack(anchor="w", padx=16, pady=(12, 7))
        test_buttons = tk.Frame(tests, bg=COLORS["surface"]); test_buttons.pack(fill="x", padx=16)
        for text, command in (("LOAD KHR SAMPLE", lambda: self._load(SAMPLE_A)), ("LOAD USD SAMPLE", lambda: self._load(SAMPLE_B)), ("PARSE", self._parse_test), ("SPEAK PARSED TEST", self._speak_parsed)):
            self._button(test_buttons, text, command).pack(side="left", padx=(0, 7))
        self.test_input = scrolledtext.ScrolledText(tests, height=3, wrap="word", bg=COLORS["surface_alt"], fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat", font=("Consolas", 10)); self.test_input.pack(fill="x", padx=16, pady=8)
        self.test_output = scrolledtext.ScrolledText(tests, height=4, wrap="word", state="disabled", bg=COLORS["surface_alt"], fg=COLORS["text"], relief="flat", font=("Consolas", 9)); self.test_output.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def _load(self, text: str) -> None: self.test_input.delete("1.0", "end"); self.test_input.insert("1.0", text)

    def _parse_test(self) -> None:
        result = parse_payment(self.test_input.get("1.0", "end").strip(), allow_test_fixture=True); announcement = build_announcement(result) if result.status == ParserStatus.VALID else ""; self.last_test_announcement = announcement
        payload = {"amount": str(result.amount) if result.amount is not None else None, "currency": result.currency, "sender_name": result.sender_name, "raw_bank_label": result.raw_bank_label, "canonical_bank": result.canonical_bank, "display_bank": result.display_bank, "spoken_bank": result.spoken_bank, "institution_status": result.institution_status, "payment_channel": result.payment_channel, "valid_incoming_payment": result.valid_incoming_payment, "status": result.status.value, "reason": result.reason_if_rejected, "announcement": announcement}
        self.test_output.configure(state="normal"); self.test_output.delete("1.0", "end"); self.test_output.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2)); self.test_output.configure(state="disabled")

    def _speak_parsed(self) -> None:
        if not self.last_test_announcement: messagebox.showwarning("No valid test", "Parse a valid confirmed sample first."); return
        self.announce_test(self.last_test_announcement)

    def _toggle_mute(self) -> None:
        self.muted = not self.muted; self.set_muted(self.muted); self.values["speaker"].set("Muted" if self.muted else "Ready")
        self.mute_button.configure(text="SPEAKER OFF — MUTED" if self.muted else "SPEAKER ON", bg=COLORS["surface_alt"] if self.muted else COLORS["green_dark"]); self._refresh_health()

    def _copy(self, value: object, label: str) -> None:
        if value is None: return
        self.root.clipboard_clear(); self.root.clipboard_append(str(value)); self.root.update_idletasks(); self.values["commissioning"].set(f"{label} copied to the clipboard.")

    def _copy_chat_id(self) -> None: self._copy(self.observed.get("chat_id"), "Chat ID")
    def _copy_sender_id(self) -> None:
        if self.source_candidate: self._copy(self.source_candidate.get("sender_id"), "Verified source candidate ID")

    def _save(self, updates: dict[str, str]) -> bool:
        if not self.save_settings: messagebox.showerror("Cannot save", "No configuration save handler is available."); return False
        try: self.save_settings(updates); return True
        except Exception as exc: messagebox.showerror("Could not save", f"The .env settings could not be saved: {exc}"); return False

    def _save_group(self) -> None:
        chat_id = self.observed.get("chat_id")
        if chat_id is None: return
        updated = self.saved_chat_ids | {int(chat_id)}
        if self._save({"ALLOWED_CHAT_IDS": ",".join(str(group_id) for group_id in sorted(updated))}):
            self.saved_chat_ids = updated; self.values["commissioning"].set(f"Group ID added safely. {len(updated)} allowed group(s) configured. Diagnostic mode remains active."); self._refresh_commissioning_controls()

    def _verify_source(self) -> None:
        candidate = self.source_candidate
        if not candidate or not candidate.get("expected_source_detected"): messagebox.showwarning("Source not verified", "Wait for a genuine @PayWayByABA_bot message."); return
        chat_id, sender_id = candidate.get("chat_id"), candidate.get("sender_id")
        if chat_id is None or sender_id is None: return
        updated = self.saved_chat_ids | {int(chat_id)}
        if self._save({"ALLOWED_CHAT_IDS": ",".join(str(group_id) for group_id in sorted(updated)), "ALLOWED_ABA_SENDER_ID": str(sender_id)}):
            self.saved_chat_ids, self.saved_sender_id = updated, int(sender_id); self.values["source"].set("Verified"); self.values["commissioning"].set("Verified numeric group and ABA sender IDs saved. Restart after switching modes."); self._refresh_commissioning_controls(); self._refresh_health()

    def _switch_to_production(self) -> None:
        if not self.saved_chat_ids or self.saved_sender_id is None: messagebox.showwarning("Setup incomplete", "Verify and save both numeric IDs first."); return
        if self._save({"DIAGNOSTIC_MODE": "false"}):
            self.values["commissioning"].set("Production mode saved. Close and restart the application to activate it."); self.production_button.configure(state="disabled"); messagebox.showinfo("Restart required", "Production mode is saved. Close and restart the application.")

    def _refresh_commissioning_controls(self) -> None:
        has_chat = self.observed.get("chat_id") is not None; has_sender = bool(self.source_candidate and self.source_candidate.get("sender_id") is not None); has_verified = bool(self.source_candidate and self.source_candidate.get("expected_source_detected"))
        states = ((self.copy_chat_button, has_chat), (self.save_group_button, has_chat), (self.copy_sender_button, has_sender), (self.verify_source_button, has_verified), (self.production_button, self.diagnostic_mode and bool(self.saved_chat_ids) and self.saved_sender_id is not None))
        for button, enabled in states: button.configure(state="normal" if enabled else "disabled")

    def _apply_diagnostic(self, data: dict[str, object]) -> None:
        self.observed = dict(data)
        if data.get("expected_source_detected"): self.source_candidate = dict(data)
        display = self.source_candidate or self.observed; username = display.get("username")
        self.values["group_title"].set(str(display.get("chat_title") or "(untitled chat)")); self.values["chat_id"].set(str(display.get("chat_id") or "—")); self.values["sender_username"].set(f"@{username}" if username else "(none)"); self.values["sender_id"].set(str(display.get("sender_id") or "—")); self.values["source_match"].set("YES — ready for operator verification" if display.get("expected_source_detected") else "NO — ordinary/other sender")
        self.values["commissioning"].set("Expected source detected. Review and click Verify & Save." if display.get("expected_source_detected") else "Group discovered. Save its chat ID, then wait for @PayWayByABA_bot."); self._refresh_commissioning_controls()

    def _apply_payment(self, data: dict[str, object]) -> None:
        self.current_payment_key = str(data.get("event_key") or "") or None
        self.current_currency = str(data.get("currency") or "") or None
        self._show_amount(data.get("amount"), self.current_currency)
        self.values["payer"].set(str(data.get("payer") or "UNKNOWN SENDER"))
        self.values["bank"].set(str(data.get("bank") or "OTHER BANK"))
        self._set_announcement_state("QUEUED")
        self._pulse_token += 1
        self._pulse_amount(0, self._pulse_token)

    def _note_image(self, currency: Optional[str], height: int) -> Optional[tk.PhotoImage]:
        pattern = NOTE_FILES.get(currency or "")
        if pattern is None:
            return None
        key = (str(currency), height)
        if key not in self._note_images:
            self._note_images[key] = load_asset_image(self.root, pattern.format(height))
        return self._note_images[key]

    def _show_amount(self, amount: object, currency: Optional[str]) -> None:
        self.values["amount"].set(format_payment_digits(amount, currency))
        self._fit_amount()

    def _fit_amount(self) -> None:
        """Banknote at the digit height before the amount, shrinking the font so it stays on one line."""
        text = self.values["amount"].get()
        available = self.payment_card.winfo_width() - 40
        if available <= 1:
            available = 10_000
        chosen_size, chosen_note = self._amount_base_size, None
        for size in range(self._amount_base_size, 23, -2):
            font = tkfont.Font(root=self.root, family="Segoe UI", size=size, weight="bold")
            digit_height = int(font.metrics("ascent") * 0.66)
            target_height = round(digit_height * NOTE_TO_DIGIT_RATIO)
            note = self._note_image(self.current_currency, note_height_for(target_height)) if text != "—" else None
            note_width = note.width() + AMOUNT_NOTE_GAP if note is not None else 0
            chosen_size, chosen_note = size, note
            if font.measure(text) + note_width <= available:
                break
        self.amount_label.configure(font=self._font(chosen_size, "bold"))
        # Centre the note on the digits, which sit below the label's geometric centre (descender space).
        metrics = tkfont.Font(root=self.root, family="Segoe UI", size=chosen_size, weight="bold").metrics()
        cap_height = metrics["ascent"] * 0.66
        offset = max(0, round((metrics["ascent"] - metrics["descent"] - cap_height)))
        if chosen_note is None:
            self.amount_note_label.configure(image="")
            self.amount_note_label.pack_forget()
        else:
            self.amount_note_label.configure(image=chosen_note)
            if not self.amount_note_label.winfo_manager():
                self.amount_note_label.pack(side="left", padx=(0, AMOUNT_NOTE_GAP), before=self.amount_label)
            self.amount_note_label.pack_configure(pady=(offset, 0))

    def _set_announcement_state(self, status: str) -> None:
        label, color = announcement_label(status); self.values["announcement"].set(label); self.announcement_label.configure(fg=COLORS[color])

    def _apply_announcement_status(self, data: dict[str, object]) -> None:
        if str(data.get("event_key")) != self.current_payment_key: return
        status = str(data.get("status") or ""); self._set_announcement_state(status)
        if status == "SPOKEN": self._refresh_operational_data()

    def _pulse_amount(self, step: int, token: int) -> None:
        if token != self._pulse_token:
            return
        color_name = amount_color(self.current_currency)
        base = COLORS[color_name]
        highlight = COLORS["usd_flash"] if self.current_currency == "USD" else "#B8FFD8"
        if step >= 6:
            self.amount_label.configure(fg=base)
            return
        self.amount_label.configure(fg=highlight if step % 2 == 0 else base)
        self.root.after(130, lambda: self._pulse_amount(step + 1, token))

    def _refresh_operational_data(self) -> None:
        try: summary = self.today_summary()
        except Exception: summary = {"count": self.count_today(), "KHR": "0", "USD": "0.00"}
        self.values["today"].set(str(summary.get("count", 0))); self.values["today_khr"].set(format_payment_amount(summary.get("KHR", "0"), "KHR")); self.values["today_usd"].set(format_payment_amount(summary.get("USD", "0"), "USD"))
        self.values["today_strip"].set(today_strip_text(summary))
        self._today_summary = summary
        self._render_ticker()
        try: rows = self.recent_payments(1000)
        except Exception: rows = []
        self._render_history(rows)
        if self.current_payment_key is None and rows:
            latest = rows[0]; self.current_payment_key = str(latest.get("event_key") or "") or None; self.current_currency = str(latest.get("currency") or "") or None; self._show_amount(latest.get("amount"), self.current_currency); self.amount_label.configure(fg=COLORS[amount_color(self.current_currency)]); self.values["payer"].set(str(latest.get("sender_name") or "UNKNOWN SENDER")); self.values["bank"].set(str(latest.get("bank") or "OTHER BANK")); self._set_announcement_state("SPOKEN")

    def _refresh_health(self) -> None:
        for name in ("telegram", "speaker", "source"):
            text, color = component_health(self.values[name].get(), name); self.health_labels[name].configure(text=text, fg=COLORS[color])
        connected = self.values["telegram"].get().lower().startswith("connected"); ready = connected and not self.muted and self.saved_sender_id is not None and not self.diagnostic_mode
        if ready: live_text, color = "● LIVE", "green"
        elif self.muted: live_text, color = "⊘ MUTED", "amber"
        elif self.diagnostic_mode: live_text, color = "● SETUP MODE", "amber"
        else: live_text, color = "● CONNECTING", "amber"
        self.values["live"].set(live_text); self.live_label.configure(fg=COLORS[color])

    def _store_rate_group_message(self, value: dict[str, object], now: Optional[datetime] = None) -> None:
        try:
            message_id = int(value.get("id"))
        except (TypeError, ValueError):
            return
        current = now or datetime.now(timezone.utc)
        sender_key = str(value.get("sender") or "").strip().casefold()
        previous = next(
            (
                message for message in latest_rate_group_posts(self.rate_group_messages.values())
                if str(message.get("sender") or "").strip().casefold() == sender_key
            ),
            None,
        )
        self.rate_group_messages[message_id] = dict(value)
        if len(self.rate_group_messages) > MAX_RATE_GROUP_MESSAGES:
            for stale in sorted(self.rate_group_messages.values(), key=_rate_group_order)[
                : len(self.rate_group_messages) - MAX_RATE_GROUP_MESSAGES
            ]:
                self.rate_group_messages.pop(int(stale["id"]), None)
        # Glow only for live posts whose offers changed; history loaded at connect stays calm.
        if current - rate_group_message_time(value) > RATE_GROUP_HISTORY_GLOW_LIMIT:
            return
        new_offers = format_rate_post(value.get("text")).rows
        old_offers = format_rate_post(previous.get("text")).rows if previous else None
        if previous is None or new_offers != old_offers:
            self._rate_group_glow[sender_key] = current + timedelta(seconds=RATE_GROUP_GLOW_SECONDS)
            self._schedule_rate_group_glow_end()

    def _schedule_rate_group_glow_end(self) -> None:
        if getattr(self, "_rate_group_glow_after_id", None) is not None:
            self.root.after_cancel(self._rate_group_glow_after_id)
        self._rate_group_glow_after_id = self.root.after(
            RATE_GROUP_GLOW_SECONDS * 1000 + 200,
            self._end_rate_group_glow,
        )

    def _end_rate_group_glow(self) -> None:
        self._rate_group_glow_after_id = None
        now = datetime.now(timezone.utc)
        self._rate_group_glow = {key: until for key, until in self._rate_group_glow.items() if until > now}
        self._render_rate_group_messages(keep_scroll=True)
        if self._rate_group_glow:
            self._schedule_rate_group_glow_end()

    def _remove_rate_group_messages(self, value: dict[str, object]) -> None:
        for message_id in value.get("ids") or ():
            try:
                self.rate_group_messages.pop(int(message_id), None)
            except (TypeError, ValueError):
                continue

    def _insert_rate_group(
        self,
        value: str,
        tags: tuple[str, ...],
        size: Optional[int] = None,
        bold: bool = False,
        khmer: Optional[bool] = None,
        figure: bool = False,
    ) -> None:
        if not value:
            return
        size = size or self._rate_group_sizes["banks"]
        use_khmer = _has_khmer_text(value) if khmer is None else khmer
        kind = "k" if use_khmer else "f" if figure else "l"
        font_tag = f"font_{size}_{'b' if bold else 'n'}_{kind}"
        if font_tag not in self._rate_group_font_tags:
            family = self.rate_group_font if use_khmer else self.figure_font if figure else "Segoe UI"
            self.rate_group_text.tag_configure(font_tag, font=self._font(size, "bold" if bold else "normal", family))
            self._rate_group_font_tags.add(font_tag)
        self.rate_group_text.insert("end", value, (*tags, font_tag))

    def _render_rate_group_messages(self, keep_scroll: bool = False, now: Optional[datetime] = None) -> None:
        text = self.rate_group_text
        sizes = self._rate_group_sizes
        current = now or datetime.now(timezone.utc)
        top = text.yview()[0] if keep_scroll else 0.0
        text.configure(state="normal")
        text.delete("1.0", "end")
        posts = order_rate_group_posts(latest_rate_group_posts(self.rate_group_messages.values()), current)
        if not posts:
            self._insert_rate_group(
                "Connect the group member's account to show posts from the configured group only.",
                ("plain", "indented"),
            )
        trends = rate_group_sender_trends(self.rate_group_messages.values())
        nbc = self.exchange_rates.get("NBC")
        nbc_rate = nbc.official_rate if nbc is not None and not nbc.is_stale(datetime.now(CAMBODIA_TIMEZONE)) else None
        for index, message in enumerate(posts):
            sender_key = str(message.get("sender") or "").strip().casefold()
            glowing = self._rate_group_glow.get(sender_key, current) > current
            faded = current - rate_group_message_time(message) > RATE_GROUP_FADE_AFTER
            row_tags = ("glow",) if glowing else (f"message_row_{index % len(RATE_GROUP_ROW_COLORS)}",)
            if faded:
                row_tags = (*row_tags, "faded")
            formatted = format_rate_post(message.get("text"))
            sender = short_sender_name(message.get("sender"))
            header = (*row_tags, "header_line")
            self._insert_rate_group(f"{message.get('posted_at') or ''}  ", (*header, "time"), sizes["small"], True)
            self._insert_rate_group(sender, (*header, "sender"), sizes["header"], True)
            if message.get("edited"):
                self._insert_rate_group(" ✎", (*header, "edited"), sizes["small"])
            self._insert_rate_group("\n", header, sizes["header"], khmer=_has_khmer_text(sender))
            sender_trends = trends.get(sender_key, {})
            for row in formatted.rows:
                if row.is_offer:
                    self._insert_rate_group_offer(row, row_tags, sender_trends, nbc_rate, faded)
                else:
                    tags = (*row_tags, "indented", "plain")
                    self._insert_rate_group(row.text, tags, sizes["banks"])
                    self._insert_rate_group("\n", tags, sizes["banks"], khmer=_has_khmer_text(row.text))
            for note in formatted.notes:
                tags = (*row_tags, "detail_line", "note")
                self._insert_rate_group(note, tags, sizes["small"])
                self._insert_rate_group("\n", tags, sizes["small"], khmer=_has_khmer_text(note))
        if posts:
            text.delete("end-2c", "end-1c")
        text.configure(state="disabled")
        text.yview_moveto(top)
        self._refresh_rate_group_summary()

    def _insert_rate_group_offer(self, row, row_tags, sender_trends, nbc_rate, faded) -> None:
        sizes = self._rate_group_sizes
        name = {KHR_TO_USD: "k2u", USD_TO_KHR: "u2k"}.get(row.direction, "none")
        line = (*row_tags, "offer_line")
        self._insert_rate_group(row.label, (*line, f"direction_{name}"), sizes["tag"], True)
        self._insert_rate_group("\t", line, sizes["tag"])
        self._insert_rate_group(row.rate_text, (*line, f"rate_{name}"), sizes["rate"], True, figure=True)
        if row.direction in sender_trends and len(row.rate_values) == 1:
            current, previous = sender_trends[row.direction]
            trend = rate_trend(row.rate_values[0], previous) if row.rate_values[0] == current else None
            if trend and not faded:
                self._insert_rate_group(f" {RATE_TREND_ARROWS[trend]}", (*line, f"trend_{trend}"), sizes["small"] + 2, True)
        if len(row.rate_values) == 1:
            gap = rate_gap_text(row.rate_values[0], nbc_rate)
            if gap:
                self._insert_rate_group(f"  {gap}", (*line, "gap"), sizes["small"])
        self._insert_rate_group("\n", line, sizes["rate"])
        if row.size_text or row.bank_text:
            detail = (*row_tags, "detail_line")
            if row.size_text:
                self._insert_rate_group(row.size_text, (*detail, "size"), sizes["amount"], True, figure=True)
            if row.bank_text:
                prefix = "  " if row.size_text else ""
                self._insert_rate_group(prefix + row.bank_text, (*detail, "banks"), sizes["banks"])
            self._insert_rate_group("\n", detail, sizes["amount"] if row.size_text else sizes["banks"],
                                    khmer=_has_khmer_text(row.bank_text))

    def _auto_start_rate_group_reader(self) -> None:
        self._rate_group_start_after_id = None
        if not self._rate_group_start_requested:
            self._toggle_rate_group_reader()

    def _toggle_rate_group_reader(self) -> None:
        status = self.values["rate_group_status"].get()
        if status.startswith("CONNECTED"):
            self._rate_group_start_requested = False
            self.rate_group_button.configure(text="DISCONNECTING...", state="disabled")
            self._apply_rate_group_status("DISCONNECTING")
            self.stop_rate_group_reader()
            return
        self._rate_group_start_requested = True
        self.rate_group_button.configure(text="CONNECTING...", state="disabled")
        self.start_rate_group_reader()

    def _update_rate_status_chip(self) -> None:
        label = rate_group_status_label(self.values["rate_group_status"].get())
        if self._rate_controls_in_top_bar:
            self.rate_status_label.configure(text="●", fg=rate_group_status_dot_color(label))
        else:
            self.rate_status_label.configure(text=label, fg="#FFFFFF")

    def _apply_rate_group_status(self, value: str) -> None:
        self.values["rate_group_status"].set(value)
        self._update_rate_status_chip()
        if value.startswith("CONNECTED"):
            self._rate_group_start_requested = True
            self.rate_group_button.configure(text="DISCONNECT", state="normal")
        elif value == "CONNECTING":
            self._rate_group_start_requested = True
            self.rate_group_button.configure(text="CONNECTING...", state="disabled")
        elif value == "DISCONNECTING":
            self._rate_group_start_requested = False
            self.rate_group_button.configure(text="DISCONNECTING...", state="disabled")
        else:
            self._rate_group_start_requested = False
            self.rate_group_button.configure(text="CONNECT", state="normal")

    def _tick_clock(self) -> None:
        now = datetime.now()
        if self._display_date is not None and self._display_date != now.date():
            self._refresh_operational_data()
        self._display_date = now.date()
        self.values["clock"].set(now.strftime("%I:%M:%S %p")); self.values["date"].set(now.strftime("%A, %d %B %Y"))
        self._refresh_exchange_rate_display()
        self._rate_group_summary_ticks += 1
        if self._rate_group_summary_ticks >= 30:
            self._rate_group_summary_ticks = 0
            self._render_rate_group_messages(keep_scroll=True)
        self.root.after(1000, self._tick_clock)

    def publish(self, event: str, value: object) -> None: self.events.put((event, value))
    def _handle_auth_request(self, request: dict[str, object]) -> None:
        kind = str(request["kind"]); value = simpledialog.askstring("Telegram login", str(request["prompt"]), parent=self.root, show="*" if kind == "password" else None); request["responses"].put(value)

    def _drain_events(self) -> None:
        while True:
            try: event, value = self.events.get_nowait()
            except queue.Empty: break
            if event in {"telegram", "setup", "source"}: self.values[event].set(str(value))
            elif event == "auth_request": self._handle_auth_request(value)
            elif event == "rate_group_auth_request": self._handle_auth_request(value)
            elif event == "rate_group_status": self._apply_rate_group_status(str(value))
            elif event == "rate_group_message" and isinstance(value, dict):
                self._store_rate_group_message(value)
                self._render_rate_group_messages()
            elif event == "rate_group_message_deleted" and isinstance(value, dict):
                self._remove_rate_group_messages(value)
                self._render_rate_group_messages()
            elif event == "exchange_rates" and isinstance(value, dict):
                self.exchange_rates = value
                self._reload_nbc_history()
                self._refresh_exchange_rate_display()
                self._render_rate_group_messages(keep_scroll=True)
                self._render_ticker()
            elif event == "fuel_prices" and isinstance(value, dict):
                self.fuel_prices = FuelPrices.from_dict(value) or self.fuel_prices
                self._render_ticker()
            elif event == "speaker": self.values["speaker"].set(str(value))
            elif event == "payment": self._apply_payment(value)
            elif event == "announcement_status": self._apply_announcement_status(value)
            elif event == "diagnostic": self._apply_diagnostic(value)
            self._refresh_health()
        self.root.after(200, self._drain_events)

    def run(self) -> None: self.root.mainloop()
