import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse


logger = logging.getLogger(__name__)


class IntegrationRuntimeStatus:
    def __init__(self, production_ready: bool) -> None:
        self._lock = threading.Lock()
        self._data = {
            "schema_version": 1,
            "service": "ABA Payment Speaker",
            "monitoring_status": "STARTING",
            "production_ready": production_ready,
            "speaker_status": "STARTING",
            "last_verified_event_at": None,
        }

    def update(self, topic: str, value: object) -> None:
        with self._lock:
            if topic == "telegram":
                text = str(value).upper()
                self._data["monitoring_status"] = "ONLINE" if text.startswith("CONNECTED") else text
            elif topic == "setup" and value == "Production ready":
                self._data["monitoring_status"] = "ONLINE"
            elif topic == "speaker":
                self._data["speaker_status"] = str(value).upper()
            elif topic == "payment" and isinstance(value, dict):
                self._data["last_verified_event_at"] = value.get("occurred_at")

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return dict(self._data)


def token_matches(provided: str, expected: str) -> bool:
    return bool(provided and expected and hmac.compare_digest(provided, expected))


class _QuietThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


class IntegrationServer:
    def __init__(self, host: str, port: int, token: str, store, status: IntegrationRuntimeStatus,
                 server_factory: Callable = _QuietThreadingHTTPServer) -> None:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("ABA integration API must bind to loopback only")
        self.host, self.port, self.token = host, port, token
        self.store, self.status, self.server_factory = store, status, server_factory
        self._server = None
        self._thread = None

    def _handler(self):
        token, store, status = self.token, self.store, self.status

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def _json(self, status_code: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.send_response(status_code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                authorization = self.headers.get("Authorization", "")
                supplied = authorization[7:] if authorization.startswith("Bearer ") else ""
                if not token_matches(supplied, token):
                    self._json(401, {"error": "unauthorized"})
                    return
                parsed = urlparse(self.path)
                if parsed.path in {"/integration/v1/status", "/integration/v1/health"}:
                    self._json(200, status.snapshot())
                    return
                if parsed.path == "/integration/v1/events":
                    query = parse_qs(parsed.query)
                    after = query.get("after", [""])[0]
                    try:
                        limit = max(1, min(int(query.get("limit", ["50"])[0]), 100))
                        events, cursor = store.get_integration_events(after, limit)
                    except ValueError:
                        self._json(400, {"error": "invalid_cursor_or_limit"})
                        return
                    self._json(200, {"schema_version": 1, "events": events, "next_cursor": cursor})
                    return
                self._json(404, {"error": "not_found"})

        return Handler

    def start(self) -> bool:
        try:
            self._server = self.server_factory((self.host, self.port), self._handler())
            self.port = int(self._server.server_address[1])
            self._thread = threading.Thread(target=self._server.serve_forever, name="aba-integration-api", daemon=True)
            self._thread.start()
            return True
        except OSError as exc:
            logger.warning("ABA integration API unavailable: %s", type(exc).__name__)
            self._server = None
            return False

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)
        self._server = self._thread = None
