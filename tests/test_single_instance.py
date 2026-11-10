import faulthandler

import main

from app.single_instance import ERROR_ALREADY_EXISTS, SingleInstanceLock


def test_first_instance_obtains_and_releases_lock():
    closed = []
    lock = SingleInstanceLock(
        create_mutex=lambda *_args: 41,
        get_last_error=lambda: 0,
        close_handle=lambda handle: closed.append(handle) or 1,
    )
    assert lock.acquire() is True
    lock.release()
    assert closed == [41]


def test_second_instance_is_rejected_and_handle_is_closed():
    closed = []
    lock = SingleInstanceLock(
        create_mutex=lambda *_args: 42,
        get_last_error=lambda: ERROR_ALREADY_EXISTS,
        close_handle=lambda handle: closed.append(handle) or 1,
    )
    assert lock.acquire() is False
    assert closed == [42]


def test_rejected_second_instance_never_initializes_application(monkeypatch, capsys):
    class RejectedLock:
        def acquire(self): return False
        def release(self): raise AssertionError("unacquired lock must not be released")

    monkeypatch.setattr(main, "SingleInstanceLock", RejectedLock)
    monkeypatch.setattr(main, "_run_application", lambda: (_ for _ in ()).throw(AssertionError("must not start")))
    assert main.main() == 1
    assert "already running" in capsys.readouterr().out


def test_normal_shutdown_releases_lock(monkeypatch, tmp_path):
    calls = []
    crash_logs = []

    class AcceptedLock:
        def acquire(self): calls.append("acquire"); return True
        def release(self): calls.append("release")

    real_enable_crash_log = main.enable_crash_log

    def crash_log_in_temp_folder(directory="logs"):
        # Never write to the real logs/faulthandler.log of the folder the tests run from.
        handle = real_enable_crash_log(str(tmp_path / "logs"))
        crash_logs.append(handle)
        return handle

    monkeypatch.setattr(main, "SingleInstanceLock", AcceptedLock)
    monkeypatch.setattr(main, "enable_crash_log", crash_log_in_temp_folder)
    monkeypatch.setattr(main, "_run_application", lambda: calls.append("run") or 0)
    try:
        assert main.main() == 0
    finally:
        faulthandler.disable()
        for handle in crash_logs:
            handle.close()
    assert calls == ["acquire", "run", "release"]
    assert (tmp_path / "logs" / "faulthandler.log").is_file()
