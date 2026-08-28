import json
import queue
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
from typing import Callable, Optional

from .models import ParserStatus
from .payment_parser import build_announcement, parse_payment

SPEAKER_TEST = "ប្រព័ន្ធប្រកាសការទូទាត់កំពុងដំណើរការ។"
SAMPLE_A = "៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253."
SAMPLE_B = "$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850."


class Dashboard:
    def __init__(
        self,
        announce_test: Callable[[str], None],
        set_muted: Callable[[bool], None],
        count_today: Callable[[], int],
        save_settings: Optional[Callable[[dict[str, str]], None]] = None,
        expected_username: str = "PayWayByABA_bot",
        configured_chat_ids: tuple[int, ...] = (),
        configured_sender_id: Optional[int] = None,
        diagnostic_mode: bool = True,
    ):
        self.root = tk.Tk()
        self.root.title("ABA Payment Speaker")
        self.root.geometry("840x780")
        self.root.minsize(760, 680)
        self.announce_test = announce_test
        self.set_muted = set_muted
        self.count_today = count_today
        self.save_settings = save_settings
        self.expected_username = expected_username.lstrip("@")
        self.saved_chat_ids = set(configured_chat_ids)
        self.saved_sender_id = configured_sender_id
        self.diagnostic_mode = diagnostic_mode
        self.observed: dict[str, object] = {}
        self.source_candidate: Optional[dict[str, object]] = None
        self.events: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self.values = {name: tk.StringVar(value=value) for name, value in {
            "telegram": "Disconnected", "setup": "Starting", "speaker": "Ready", "source": "Waiting", "amount": "—",
            "payer": "—", "bank": "—", "announcement": "—", "today": "0",
            "expected_source": f"@{self.expected_username}", "group_title": "Waiting for a group message",
            "chat_id": ", ".join(str(value) for value in configured_chat_ids) or "—",
            "sender_username": "—", "sender_id": str(configured_sender_id) if configured_sender_id is not None else "—",
            "source_match": "Waiting", "commissioning": "Diagnostic mode is active; production speech is disabled."
        }.items()}
        self.muted = False
        self.last_test_announcement = ""
        self._build()
        self.root.after(200, self._drain_events)

    def _build(self) -> None:
        root = ttk.Frame(self.root, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="ABA PAYMENT SPEAKER", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        status = ttk.LabelFrame(root, text="Status", padding=10)
        status.pack(fill="x", pady=10)
        for label, name in (("Telegram", "telegram"), ("Setup", "setup"), ("Speaker", "speaker"), ("ABA Source", "source")):
            row = ttk.Frame(status); row.pack(fill="x")
            ttk.Label(row, text=f"{label}:", width=18).pack(side="left")
            ttk.Label(row, textvariable=self.values[name]).pack(side="left")
        commissioning = ttk.LabelFrame(root, text="Telegram commissioning", padding=10)
        commissioning.pack(fill="x", pady=(0, 10))
        for label, name in (("Expected source", "expected_source"), ("Observed group", "group_title"),
                            ("Observed chat ID", "chat_id"), ("Sender username", "sender_username"),
                            ("Sender numeric ID", "sender_id"), ("Matches expected source", "source_match")):
            row = ttk.Frame(commissioning); row.pack(fill="x")
            ttk.Label(row, text=f"{label}:", width=24).pack(side="left")
            ttk.Label(row, textvariable=self.values[name], wraplength=570, justify="left").pack(side="left")
        commissioning_buttons = ttk.Frame(commissioning)
        commissioning_buttons.pack(fill="x", pady=(8, 4))
        self.copy_chat_button = ttk.Button(commissioning_buttons, text="Copy Chat ID", command=self._copy_chat_id, state="disabled")
        self.copy_chat_button.pack(side="left")
        self.save_group_button = ttk.Button(commissioning_buttons, text="Add Group ID", command=self._save_group, state="disabled")
        self.save_group_button.pack(side="left", padx=5)
        self.copy_sender_button = ttk.Button(commissioning_buttons, text="Copy Sender ID", command=self._copy_sender_id, state="disabled")
        self.copy_sender_button.pack(side="left")
        self.verify_source_button = ttk.Button(commissioning_buttons, text="Verify & Save ABA IDs", command=self._verify_source, state="disabled")
        self.verify_source_button.pack(side="left", padx=5)
        self.production_button = ttk.Button(commissioning_buttons, text="Switch to Production", command=self._switch_to_production, state="disabled")
        self.production_button.pack(side="left")
        ttk.Label(commissioning, textvariable=self.values["commissioning"], wraplength=770, justify="left").pack(fill="x")
        self._refresh_commissioning_controls()
        payment = ttk.LabelFrame(root, text="Last payment", padding=10)
        payment.pack(fill="x")
        for label, name in (("Amount", "amount"), ("Payer", "payer"), ("Bank", "bank"),
                            ("Last spoken", "announcement"), ("Announced today", "today")):
            row = ttk.Frame(payment); row.pack(fill="x")
            ttk.Label(row, text=f"{label}:", width=18).pack(side="left")
            ttk.Label(row, textvariable=self.values[name], wraplength=560).pack(side="left")
        controls = ttk.Frame(root); controls.pack(fill="x", pady=10)
        ttk.Button(controls, text="Test Speaker", command=lambda: self.announce_test(SPEAKER_TEST)).pack(side="left")
        self.mute_button = ttk.Button(controls, text="Mute", command=self._toggle_mute)
        self.mute_button.pack(side="left", padx=8)
        tests = ttk.LabelFrame(root, text="Safe parser test (never treated as a production payment)", padding=10)
        tests.pack(fill="both", expand=True)
        buttons = ttk.Frame(tests); buttons.pack(fill="x")
        ttk.Button(buttons, text="Load KHR sample", command=lambda: self._load(SAMPLE_A)).pack(side="left")
        ttk.Button(buttons, text="Load USD sample", command=lambda: self._load(SAMPLE_B)).pack(side="left", padx=6)
        ttk.Button(buttons, text="Parse", command=self._parse_test).pack(side="left")
        ttk.Button(buttons, text="Speak parsed test", command=self._speak_parsed).pack(side="left", padx=6)
        self.test_input = scrolledtext.ScrolledText(tests, height=4, wrap="word")
        self.test_input.pack(fill="x", pady=6)
        self.test_output = scrolledtext.ScrolledText(tests, height=8, wrap="word", state="disabled")
        self.test_output.pack(fill="both", expand=True)

    def _load(self, text: str) -> None:
        self.test_input.delete("1.0", "end"); self.test_input.insert("1.0", text)

    def _parse_test(self) -> None:
        result = parse_payment(self.test_input.get("1.0", "end").strip())
        announcement = build_announcement(result) if result.status == ParserStatus.VALID else ""
        self.last_test_announcement = announcement
        payload = {"amount": str(result.amount) if result.amount is not None else None, "currency": result.currency,
                   "sender_name": result.sender_name, "bank": result.bank, "payment_channel": result.payment_channel,
                   "valid_incoming_payment": result.valid_incoming_payment, "status": result.status.value,
                   "reason": result.reason_if_rejected, "announcement": announcement}
        self.test_output.configure(state="normal"); self.test_output.delete("1.0", "end")
        self.test_output.insert("1.0", json.dumps(payload, ensure_ascii=False, indent=2)); self.test_output.configure(state="disabled")

    def _speak_parsed(self) -> None:
        if not self.last_test_announcement:
            messagebox.showwarning("No valid test", "Parse a valid confirmed sample first.")
            return
        self.announce_test(self.last_test_announcement)

    def _toggle_mute(self) -> None:
        self.muted = not self.muted; self.set_muted(self.muted)
        self.values["speaker"].set("Muted" if self.muted else "Ready")
        self.mute_button.configure(text="Unmute" if self.muted else "Mute")

    def _copy(self, value: object, label: str) -> None:
        if value is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(value))
        self.root.update_idletasks()
        self.values["commissioning"].set(f"{label} copied to the clipboard.")

    def _copy_chat_id(self) -> None:
        self._copy(self.observed.get("chat_id"), "Chat ID")

    def _copy_sender_id(self) -> None:
        if not self.source_candidate:
            return
        self._copy(self.source_candidate.get("sender_id"), "Verified source candidate ID")

    def _save(self, updates: dict[str, str]) -> bool:
        if not self.save_settings:
            messagebox.showerror("Cannot save", "No configuration save handler is available.")
            return False
        try:
            self.save_settings(updates)
            return True
        except Exception as exc:
            messagebox.showerror("Could not save", f"The .env settings could not be saved: {exc}")
            return False

    def _save_group(self) -> None:
        chat_id = self.observed.get("chat_id")
        if chat_id is None:
            return
        updated = self.saved_chat_ids | {int(chat_id)}
        value = ",".join(str(group_id) for group_id in sorted(updated))
        if self._save({"ALLOWED_CHAT_IDS": value}):
            self.saved_chat_ids = updated
            self.values["commissioning"].set(
                f"Group ID added safely. {len(updated)} allowed group(s) are configured. Diagnostic mode remains active."
            )
            self._refresh_commissioning_controls()

    def _verify_source(self) -> None:
        candidate = self.source_candidate
        if not candidate or not candidate.get("expected_source_detected"):
            messagebox.showwarning("Source not verified", "Wait for a genuine @PayWayByABA_bot message.")
            return
        chat_id, sender_id = candidate.get("chat_id"), candidate.get("sender_id")
        if chat_id is None or sender_id is None:
            return
        updated = self.saved_chat_ids | {int(chat_id)}
        groups = ",".join(str(group_id) for group_id in sorted(updated))
        if self._save({"ALLOWED_CHAT_IDS": groups, "ALLOWED_ABA_SENDER_ID": str(sender_id)}):
            self.saved_chat_ids, self.saved_sender_id = updated, int(sender_id)
            self.values["commissioning"].set(
                "Verified numeric group and ABA sender IDs saved to .env. Production remains disabled until you switch modes and restart."
            )
            self._refresh_commissioning_controls()

    def _switch_to_production(self) -> None:
        if not self.saved_chat_ids or self.saved_sender_id is None:
            messagebox.showwarning("Setup incomplete", "Verify and save both numeric IDs first.")
            return
        if self._save({"DIAGNOSTIC_MODE": "false"}):
            self.values["commissioning"].set("Production mode saved. Close and restart the application to activate it.")
            self.production_button.configure(state="disabled")
            messagebox.showinfo("Restart required", "Production mode is saved. Close and restart the application.")

    def _refresh_commissioning_controls(self) -> None:
        has_chat = self.observed.get("chat_id") is not None
        # Never offer an ordinary user's numeric ID as the ABA source ID.
        has_sender = bool(self.source_candidate and self.source_candidate.get("sender_id") is not None)
        has_verified_candidate = bool(self.source_candidate and self.source_candidate.get("expected_source_detected"))
        self.copy_chat_button.configure(state="normal" if has_chat else "disabled")
        self.save_group_button.configure(state="normal" if has_chat else "disabled")
        self.copy_sender_button.configure(state="normal" if has_sender else "disabled")
        self.verify_source_button.configure(state="normal" if has_verified_candidate else "disabled")
        can_produce = self.diagnostic_mode and bool(self.saved_chat_ids) and self.saved_sender_id is not None
        self.production_button.configure(state="normal" if can_produce else "disabled")

    def _apply_diagnostic(self, data: dict[str, object]) -> None:
        self.observed = dict(data)
        if data.get("expected_source_detected"):
            self.source_candidate = dict(data)
        display = self.source_candidate or self.observed
        username = display.get("username")
        self.values["group_title"].set(str(display.get("chat_title") or "(untitled chat)"))
        self.values["chat_id"].set(str(display.get("chat_id") or "—"))
        self.values["sender_username"].set(f"@{username}" if username else "(none)")
        self.values["sender_id"].set(str(display.get("sender_id") or "—"))
        self.values["source_match"].set("YES — ready for operator verification" if display.get("expected_source_detected") else "NO — ordinary/other sender")
        self.values["commissioning"].set(
            "Expected source detected. Review the group and username, then click Verify & Save ABA IDs."
            if display.get("expected_source_detected")
            else "Group discovered. You may save its chat ID; now wait for @PayWayByABA_bot."
        )
        self._refresh_commissioning_controls()

    def publish(self, event: str, value: object) -> None:
        self.events.put((event, value))

    def _handle_auth_request(self, request: dict[str, object]) -> None:
        kind = str(request["kind"])
        value = simpledialog.askstring(
            "Telegram login",
            str(request["prompt"]),
            parent=self.root,
            show="*" if kind == "password" else None,
        )
        request["responses"].put(value)

    def _drain_events(self) -> None:
        while True:
            try: event, value = self.events.get_nowait()
            except queue.Empty: break
            if event in {"telegram", "setup", "source"}: self.values[event].set(str(value))
            elif event == "auth_request": self._handle_auth_request(value)
            elif event == "speaker": self.values["speaker"].set(str(value))
            elif event == "payment":
                data = value; self.values["amount"].set(f"{data['amount']} {data['currency']}")
                self.values["payer"].set(data["payer"]); self.values["bank"].set(data["bank"])
                self.values["announcement"].set(data["announcement"]); self.values["today"].set(str(self.count_today()))
            elif event == "diagnostic":
                self._apply_diagnostic(value)
        self.root.after(200, self._drain_events)

    def run(self) -> None:
        self.root.mainloop()
