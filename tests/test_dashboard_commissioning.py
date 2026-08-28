from app.dashboard import Dashboard


class FakeButton:
    def __init__(self):
        self.state = None

    def configure(self, **values):
        self.state = values.get("state", self.state)


def bare_dashboard():
    dashboard = Dashboard.__new__(Dashboard)
    dashboard.observed = {"chat_id": -1001, "sender_id": 166792174, "username": "Operator"}
    dashboard.source_candidate = None
    dashboard.diagnostic_mode = True
    dashboard.saved_chat_ids = set()
    dashboard.saved_sender_id = None
    dashboard.copy_chat_button = FakeButton()
    dashboard.save_group_button = FakeButton()
    dashboard.copy_sender_button = FakeButton()
    dashboard.verify_source_button = FakeButton()
    dashboard.production_button = FakeButton()
    return dashboard


def test_ordinary_personal_sender_id_cannot_be_copied_or_verified():
    dashboard = bare_dashboard()
    dashboard._refresh_commissioning_controls()
    assert dashboard.copy_chat_button.state == "normal"
    assert dashboard.copy_sender_button.state == "disabled"
    assert dashboard.verify_source_button.state == "disabled"


def test_matching_source_candidate_enables_source_controls():
    dashboard = bare_dashboard()
    dashboard.source_candidate = {
        "chat_id": -1001,
        "sender_id": 987654,
        "username": "PayWayByABA_bot",
        "expected_source_detected": True,
    }
    dashboard._refresh_commissioning_controls()
    assert dashboard.copy_sender_button.state == "normal"
    assert dashboard.verify_source_button.state == "normal"
