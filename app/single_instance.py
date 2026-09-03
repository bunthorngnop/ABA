import ctypes
import os
from typing import Callable, Optional


ERROR_ALREADY_EXISTS = 183


class SingleInstanceLock:
    """Process-lifetime Windows mutex acquired before any Telegram work starts."""

    def __init__(
        self,
        name: str = r"Local\ABA_Payment_Speaker_Authoritative_Instance",
        create_mutex: Optional[Callable[..., int]] = None,
        get_last_error: Optional[Callable[[], int]] = None,
        close_handle: Optional[Callable[[int], int]] = None,
    ) -> None:
        self.name = name
        self._handle: Optional[int] = None
        if create_mutex is None and os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            create_mutex = kernel32.CreateMutexW
            get_last_error = kernel32.GetLastError
            close_handle = kernel32.CloseHandle
        self._create_mutex = create_mutex
        self._get_last_error = get_last_error
        self._close_handle = close_handle

    def acquire(self) -> bool:
        if self._handle is not None:
            return True
        if os.name != "nt" and self._create_mutex is None:
            return True
        if not self._create_mutex or not self._get_last_error:
            return False
        handle = self._create_mutex(None, False, self.name)
        if not handle:
            return False
        if self._get_last_error() == ERROR_ALREADY_EXISTS:
            if self._close_handle:
                self._close_handle(handle)
            return False
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle is not None and self._close_handle:
            self._close_handle(self._handle)
        self._handle = None

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("ABA Payment Speaker is already running.")
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        self.release()
