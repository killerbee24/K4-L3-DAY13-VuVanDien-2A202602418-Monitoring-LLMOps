from app.logging_config import scrub_event
from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    cccd = "079203001234"
    out = scrub_text(f"CCCD: {cccd}")
    assert cccd not in out
    assert "REDACTED_CCCD" in out


def test_scrub_common_credit_card_formats() -> None:
    card_numbers = (
        "4111111111111111",
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
    )

    for card_number in card_numbers:
        out = scrub_text(f"Card: {card_number}")
        assert card_number not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_log_processor_scrubs_nested_values() -> None:
    event = {
        "event": "request_failed",
        "session_id": "student@vinuni.edu.vn",
        "payload": {
            "message": "Call 090 123 4567",
            "items": ["CCCD 079203001234", {"card": "4111 1111 1111 1111"}],
        },
    }

    scrubbed = scrub_event(None, "error", event)
    rendered = str(scrubbed)

    assert "student@vinuni.edu.vn" not in rendered
    assert "090 123 4567" not in rendered
    assert "079203001234" not in rendered
    assert "4111 1111 1111 1111" not in rendered
