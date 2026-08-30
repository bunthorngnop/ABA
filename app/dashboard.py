import json
import queue
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Callable, Optional

from .models import ParserStatus
from .payment_parser import build_announcement, parse_payment

SPEAKER_TEST = "ប្រព័ន្ធប្រកាសការទូទាត់កំពុងដំណើរការ។"
SAMPLE_A = "៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253."
SAMPLE_B = "$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850."

COLORS = {
    "background": "#070D1A", "surface": "#101827", "surface_alt": "#151F32",
    "border": "#25324A", "text": "#F8FAFC", "muted": "#94A3B8",
    "green": "#35E58B", "green_dark": "#123D2B", "blue": "#5DA9FF",
    "blue_dark": "#122C4B", "purple": "#B78AFF", "purple_dark": "#302052",
    "amber": "#FBBF24", "usd": "#F6C85F", "usd_flash": "#FFF0B8",
    "red": "#FB7185", "button": "#22304A",
}


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
        self._display_date = None
        self._layout_after_id = None
        self._layout_mode = None
        self.khmer_title_font = self._select_khmer_title_font()
        initial_source = "Verified" if configured_sender_id is not None else "Waiting"
        self.values = {name: tk.StringVar(value=value) for name, value in {
            "telegram": "Disconnected", "setup": "Starting", "speaker": "Ready", "source": initial_source,
            "amount": "—", "payer": "WAITING FOR PAYMENT", "bank": "—", "announcement": "AWAITING PAYMENT",
            "today": "0", "today_khr": "៛ 0", "today_usd": "$ 0.00", "clock": "", "date": "", "live": "STARTING",
            "expected_source": f"@{self.expected_username}", "group_title": "Waiting for a group message",
            "chat_id": ", ".join(str(value) for value in configured_chat_ids) or "—",
            "sender_username": "—", "sender_id": str(configured_sender_id) if configured_sender_id is not None else "—",
            "source_match": "Waiting", "commissioning": "Diagnostic mode is active; production speech is disabled."
        }.items()}
        self._build()
        self.root.bind("<Configure>", self._schedule_responsive_layout)
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
        header = tk.Frame(self.root, bg=COLORS["background"], padx=28, pady=9); header.pack(fill="x"); self.header = header
        header.grid_columnconfigure(0, weight=1, uniform="header_side")
        header.grid_columnconfigure(1, weight=0)
        header.grid_columnconfigure(2, weight=1, uniform="header_side")
        title = tk.Frame(header, bg=COLORS["background"]); title.grid(row=0, column=0, rowspan=2, sticky="w")
        self.title_primary_label = self._label(title, "វីង វណ្ណា-ស្រីម៉ិច", size=24, family=self.khmer_title_font)
        self.title_primary_label.pack(anchor="w")
        self.title_secondary_label = self._label(title, "ប្រព័ន្ធទទួលប្រាក់", size=24, color="green", family=self.khmer_title_font)
        self.title_secondary_label.pack(anchor="w")
        clock = tk.Frame(header, bg=COLORS["background"]); clock.grid(row=0, column=1, rowspan=2)
        self.clock_label = self._label(clock, variable=self.values["clock"], size=56, weight="bold")
        self.clock_label.pack()
        self._label(clock, variable=self.values["date"], size=13, color="muted", weight="bold").pack(pady=(0, 2))
        live = tk.Frame(header, bg=COLORS["background"]); live.grid(row=0, column=2, rowspan=2, sticky="e")
        self.live_label = self._label(live, variable=self.values["live"], size=12, color="amber", weight="bold")
        self.live_label.pack(anchor="e")
        self.notebook = ttk.Notebook(self.root, style="Dark.TNotebook"); self.notebook.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        self.main_tab = tk.Frame(self.notebook, bg=COLORS["background"]); self.diagnostics_tab = tk.Frame(self.notebook, bg=COLORS["background"])
        self.notebook.add(self.main_tab, text="  DASHBOARD  "); self.notebook.add(self.diagnostics_tab, text="  SETTINGS & DIAGNOSTICS  ")
        self._build_main_tab(); self._build_diagnostics_tab(); self.notebook.select(self.main_tab)

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
        body = tk.Frame(self.main_tab, bg=COLORS["background"]); body.pack(fill="both", expand=True); self.dashboard_body = body
        body.grid_columnconfigure(0, weight=7); body.grid_columnconfigure(1, weight=3); body.grid_rowconfigure(0, weight=1)
        payment = self._card(body, row=0, column=0, sticky="nsew", padx=(0, 12), pady=(8, 0)); self.payment_card = payment
        payment.grid_columnconfigure(0, weight=1); payment.grid_rowconfigure(1, weight=1, minsize=120)
        self._label(payment, "LAST PAYMENT RECEIVED", size=11, color="muted", weight="bold").grid(row=0, column=0, pady=(14, 0))
        self.amount_label = self._label(payment, variable=self.values["amount"], size=56, color="green", weight="bold")
        self.amount_label.grid(row=1, column=0, padx=20, pady=(8, 6), sticky="nsew")
        self.announcement_label = self._label(payment, variable=self.values["announcement"], size=12, color="muted", weight="bold")
        self.announcement_label.grid(row=2, column=0, pady=(0, 10))
        identity = tk.Frame(payment, bg=COLORS["surface"]); identity.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        identity.grid_columnconfigure(0, weight=1, uniform="identity"); identity.grid_columnconfigure(1, weight=1, uniform="identity")
        sender = tk.Frame(identity, bg=COLORS["blue_dark"], padx=16, pady=11); sender.grid(row=0, column=0, sticky="nsew", padx=(0, 7)); self.sender_card = sender
        self._label(sender, "● FROM (SENDER)", size=9, color="blue", weight="bold").pack(anchor="w")
        self.sender_label = self._label(sender, variable=self.values["payer"], size=21, color="blue", weight="bold", anchor="w", justify="left", wraplength=360)
        self.sender_label.pack(fill="both", expand=True, pady=(8, 0))
        bank = tk.Frame(identity, bg=COLORS["purple_dark"], padx=16, pady=11); bank.grid(row=0, column=1, sticky="nsew", padx=(7, 0)); self.bank_card = bank
        self._label(bank, "▥ FROM BANK", size=9, color="purple", weight="bold").pack(anchor="w")
        self.bank_label = self._label(bank, variable=self.values["bank"], size=21, color="purple", weight="bold", anchor="w", justify="left", wraplength=300)
        self.bank_label.pack(fill="both", expand=True, pady=(8, 0))
        side = tk.Frame(body, bg=COLORS["background"]); side.grid(row=0, column=1, sticky="nsew", pady=(8, 0)); self.dashboard_side = side
        side.grid_columnconfigure(0, weight=1); side.grid_rowconfigure(2, weight=1)
        self._build_status_card(side); self._build_summary_card(side); self._build_controls_card(side)
        recent = self._card(body, row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0)); recent.grid_columnconfigure(0, weight=1)
        self._label(recent, "RECENT ANNOUNCED PAYMENTS — TODAY", size=10, color="muted", weight="bold").grid(row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(14, 8))
        headings = tk.Frame(recent, bg=COLORS["surface_alt"], height=34); headings.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14); headings.grid_propagate(False)
        self._configure_history_columns(headings)
        for column, title, anchor in ((0, "AMOUNT", "w"), (1, "SENDER", "w"), (2, "BANK", "w"), (3, "TIME", "e")):
            tk.Label(headings, text=title, bg=COLORS["surface_alt"], fg=COLORS["muted"], font=self._font(11, "bold"), anchor=anchor, padx=10).grid(row=0, column=column, sticky="nsew")
        history_panel = tk.Frame(recent, bg=COLORS["surface"]); history_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14)); history_panel.grid_columnconfigure(0, weight=1)
        self.history_canvas = tk.Canvas(history_panel, bg=COLORS["surface"], height=132, highlightthickness=0, bd=0)
        self.history_canvas.grid(row=0, column=0, sticky="ew")
        self.history_scrollbar = ttk.Scrollbar(history_panel, orient="vertical", command=self.history_canvas.yview)
        self.history_scrollbar.grid(row=0, column=1, sticky="ns")
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)
        self.history_inner = tk.Frame(self.history_canvas, bg=COLORS["surface"])
        self.history_window = self.history_canvas.create_window((0, 0), window=self.history_inner, anchor="nw")
        self.history_canvas.bind("<Configure>", self._resize_history)
        self.history_scrollbar.grid_remove()

    def _build_status_card(self, parent) -> None:
        card = self._card(parent, row=0, column=0, sticky="ew", pady=(0, 10)); self._label(card, "SYSTEM STATUS", size=10, color="muted", weight="bold").pack(anchor="w", padx=17, pady=(14, 8))
        self.health_labels = {}
        for label, name in (("Telegram session", "telegram"), ("Speaker", "speaker"), ("PayWay source", "source")):
            row = tk.Frame(card, bg=COLORS["surface"], padx=17, pady=4); row.pack(fill="x"); self._label(row, label, size=10).pack(side="left")
            status = self._label(row, "", size=9, color="amber", weight="bold"); status.pack(side="right"); self.health_labels[name] = status
        tk.Frame(card, bg=COLORS["surface"], height=9).pack(); self._refresh_health()

    @staticmethod
    def _configure_history_columns(parent) -> None:
        parent.grid_columnconfigure(0, weight=0, minsize=165)
        parent.grid_columnconfigure(1, weight=5)
        parent.grid_columnconfigure(2, weight=3)
        parent.grid_columnconfigure(3, weight=0, minsize=125)

    def _resize_history(self, event) -> None:
        self.history_canvas.itemconfigure(self.history_window, width=event.width)

    def _scroll_history(self, event) -> str:
        if self._history_row_count > 3:
            direction = -1 if event.delta > 0 else 1
            self.history_canvas.yview_scroll(direction, "units")
        return "break"

    def _bind_history_scroll(self, widget) -> None:
        widget.bind("<MouseWheel>", self._scroll_history)

    def _render_history(self, rows: list[dict[str, object]]) -> None:
        for child in self.history_inner.winfo_children():
            child.destroy()
        self._history_row_count = len(rows)
        if not rows:
            empty = tk.Label(self.history_inner, text="NO ANNOUNCED PAYMENTS TODAY", bg=COLORS["surface"], fg=COLORS["muted"], font=self._font(12, "bold"), anchor="center")
            empty.grid(row=0, column=0, sticky="nsew"); self.history_inner.grid_columnconfigure(0, weight=1); self._bind_history_scroll(empty)
        for index, row in enumerate(rows):
            background = COLORS["surface"] if index % 2 == 0 else COLORS["surface_alt"]
            line = tk.Frame(self.history_inner, bg=background, height=44)
            line.grid(row=index, column=0, sticky="ew"); line.grid_propagate(False)
            self.history_inner.grid_columnconfigure(0, weight=1)
            self._configure_history_columns(line)
            timestamp = str(row.get("received_at") or "")
            try: shown_time = datetime.fromisoformat(timestamp).astimezone().strftime("%I:%M %p")
            except (ValueError, TypeError): shown_time = "—"
            row_foreground = COLORS[amount_color(row.get("currency"))]
            values = (
                (format_payment_amount(row.get("amount"), row.get("currency")), row_foreground, "w", "bold"),
                (str(row.get("sender_name") or "—"), row_foreground, "w", "bold"),
                (str(row.get("bank") or "OTHER BANK"), row_foreground, "w", "normal"),
                (shown_time, row_foreground, "e", "normal"),
            )
            for column, (text, foreground, anchor, weight) in enumerate(values):
                label = tk.Label(line, text=text, bg=background, fg=foreground, font=self._font(14, weight), anchor=anchor, padx=10)
                label.grid(row=0, column=column, sticky="nsew"); self._bind_history_scroll(label)
            self._bind_history_scroll(line)
        self._bind_history_scroll(self.history_canvas)
        self.history_inner.update_idletasks()
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        self.history_canvas.yview_moveto(0)
        if len(rows) > 3: self.history_scrollbar.grid()
        else: self.history_scrollbar.grid_remove()

    def _build_summary_card(self, parent) -> None:
        card = self._card(parent, row=1, column=0, sticky="ew", pady=(0, 10)); self._label(card, "TODAY", size=10, color="muted", weight="bold").grid(row=0, column=0, columnspan=3, sticky="w", padx=17, pady=(14, 8))
        for index, (name, caption, color) in enumerate((("today", "PAYMENTS", "text"), ("today_khr", "KHR", "green"), ("today_usd", "USD", "blue"))):
            card.grid_columnconfigure(index, weight=1); cell = tk.Frame(card, bg=COLORS["surface"]); cell.grid(row=1, column=index, sticky="ew", padx=9, pady=(0, 14))
            self._label(cell, variable=self.values[name], size=15, color=color, weight="bold").pack(); self._label(cell, caption, size=8, color="muted", weight="bold").pack()

    def _build_controls_card(self, parent) -> None:
        card = self._card(parent, row=2, column=0, sticky="nsew"); self._label(card, "CONTROLS", size=10, color="muted", weight="bold").pack(anchor="w", padx=17, pady=(14, 10))
        self.mute_button = self._button(card, "SPEAKER ON", self._toggle_mute, accent="green_dark"); self.mute_button.pack(fill="x", padx=16, pady=5)
        self._button(card, "TEST SPEAKER", lambda: self.announce_test(SPEAKER_TEST)).pack(fill="x", padx=16, pady=5)
        self._button(card, "SETTINGS / DIAGNOSTICS", lambda: self.notebook.select(self.diagnostics_tab)).pack(fill="x", padx=16, pady=5)
        self.controls_setup_label = self._label(card, variable=self.values["setup"], size=9, color="muted", wraplength=250, justify="left")
        self.controls_setup_label.pack(fill="x", padx=17, pady=(12, 15))

    def _schedule_responsive_layout(self, event=None) -> None:
        if event is not None and event.widget is not self.root:
            return
        if self._layout_after_id is not None:
            self.root.after_cancel(self._layout_after_id)
        self._layout_after_id = self.root.after(80, self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        self._layout_after_id = None
        mode = responsive_layout_mode(self.root.winfo_height())
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        compact = mode != "normal"
        self.header.configure(padx=18 if compact else 28, pady=5 if compact else 9)
        for card in (self.sender_card, self.bank_card):
            card.configure(padx=12 if compact else 16, pady=6 if compact else 11)
        self.sender_label.configure(font=self._font(18 if compact else 21, "bold"))
        self.bank_label.configure(font=self._font(18 if compact else 21, "bold"))
        self.payment_card.grid_rowconfigure(1, minsize=105 if compact else 120)
        if compact:
            self.controls_setup_label.pack_forget()
        elif not self.controls_setup_label.winfo_manager():
            self.controls_setup_label.pack(fill="x", padx=17, pady=(12, 15))
        if mode == "short":
            self.dashboard_side.grid_remove()
            self.payment_card.grid_configure(columnspan=2, padx=0)
        else:
            self.payment_card.grid_configure(columnspan=1, padx=(0, 12))
            self.dashboard_side.grid()

    def _build_diagnostics_tab(self) -> None:
        outer = tk.Frame(self.diagnostics_tab, bg=COLORS["background"], padx=10, pady=10); outer.pack(fill="both", expand=True)
        tools = ttk.Notebook(outer, style="Dark.TNotebook"); tools.pack(fill="both", expand=True); self.diagnostic_notebook = tools
        setup_page = tk.Frame(tools, bg=COLORS["background"]); parser_page = tk.Frame(tools, bg=COLORS["background"]); self.parser_page = parser_page
        tools.add(setup_page, text="  TELEGRAM SETUP  "); tools.add(parser_page, text="  SAFE PARSER TEST  ")
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
        self.values["amount"].set(format_payment_amount(data.get("amount"), self.current_currency))
        self.values["payer"].set(str(data.get("payer") or "UNKNOWN SENDER"))
        self.values["bank"].set(str(data.get("bank") or "OTHER BANK"))
        self._set_announcement_state("QUEUED")
        self._pulse_token += 1
        self._pulse_amount(0, self._pulse_token)

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
        try: rows = self.recent_payments(1000)
        except Exception: rows = []
        self._render_history(rows)
        if self.current_payment_key is None and rows:
            latest = rows[0]; self.current_payment_key = str(latest.get("event_key") or "") or None; self.current_currency = str(latest.get("currency") or "") or None; self.values["amount"].set(format_payment_amount(latest.get("amount"), self.current_currency)); self.amount_label.configure(fg=COLORS[amount_color(self.current_currency)]); self.values["payer"].set(str(latest.get("sender_name") or "UNKNOWN SENDER")); self.values["bank"].set(str(latest.get("bank") or "OTHER BANK")); self._set_announcement_state("SPOKEN")

    def _refresh_health(self) -> None:
        for name in ("telegram", "speaker", "source"):
            text, color = component_health(self.values[name].get(), name); self.health_labels[name].configure(text=text, fg=COLORS[color])
        connected = self.values["telegram"].get().lower().startswith("connected"); ready = connected and not self.muted and self.saved_sender_id is not None and not self.diagnostic_mode
        if ready: live_text, color = "● LIVE", "green"
        elif self.muted: live_text, color = "⊘ MUTED", "amber"
        elif self.diagnostic_mode: live_text, color = "● SETUP MODE", "amber"
        else: live_text, color = "● CONNECTING", "amber"
        self.values["live"].set(live_text); self.live_label.configure(fg=COLORS[color])

    def _tick_clock(self) -> None:
        now = datetime.now()
        if self._display_date is not None and self._display_date != now.date():
            self._refresh_operational_data()
        self._display_date = now.date()
        self.values["clock"].set(now.strftime("%I:%M:%S %p")); self.values["date"].set(now.strftime("%A, %d %B %Y")); self.root.after(1000, self._tick_clock)

    def publish(self, event: str, value: object) -> None: self.events.put((event, value))
    def _handle_auth_request(self, request: dict[str, object]) -> None:
        kind = str(request["kind"]); value = simpledialog.askstring("Telegram login", str(request["prompt"]), parent=self.root, show="*" if kind == "password" else None); request["responses"].put(value)

    def _drain_events(self) -> None:
        while True:
            try: event, value = self.events.get_nowait()
            except queue.Empty: break
            if event in {"telegram", "setup", "source"}: self.values[event].set(str(value))
            elif event == "auth_request": self._handle_auth_request(value)
            elif event == "speaker": self.values["speaker"].set(str(value))
            elif event == "payment": self._apply_payment(value)
            elif event == "announcement_status": self._apply_announcement_status(value)
            elif event == "diagnostic": self._apply_diagnostic(value)
            self._refresh_health()
        self.root.after(200, self._drain_events)

    def run(self) -> None: self.root.mainloop()
