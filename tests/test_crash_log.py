import faulthandler

import main


def test_crash_log_enables_faulthandler_in_logs_folder(tmp_path):
    log_file = main.enable_crash_log(str(tmp_path / "logs"))
    try:
        assert faulthandler.is_enabled()
        assert (tmp_path / "logs" / "faulthandler.log").is_file()
        header = (tmp_path / "logs" / "faulthandler.log").read_text(encoding="utf-8")
        assert header.startswith("--- ABA started ")
        assert "pid=" in header
    finally:
        faulthandler.disable()
        log_file.close()
