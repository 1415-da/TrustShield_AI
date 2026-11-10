"""PII detection: Presidio + TrustShield custom recognizers."""

from app.guardrails.pii import get_pii_detector, luhn_valid
from app.guardrails.types import mask_value


def types(text: str) -> set[str]:
    return {e.entity_type for e in get_pii_detector().analyze(text) if e.score >= 0.5}


def test_detects_email_and_phone():
    found = types("Reach me at jane.doe@example.test or +91 98765 43210.")
    assert {"EMAIL_ADDRESS", "PHONE_NUMBER"} <= found


def test_detects_luhn_valid_card_only():
    assert luhn_valid("4111 1111 1111 1111")
    assert not luhn_valid("4111 1111 1111 1112")
    assert "CREDIT_CARD" in types("My card 4111 1111 1111 1111 was charged")
    assert "CREDIT_CARD" not in types("Order number 4111 1111 1111 1112 shipped")


def test_bank_account_requires_context():
    assert "BANK_ACCOUNT" in types("Transfer to bank account 123456789012 please")
    assert "BANK_ACCOUNT" not in types("Ticket 123456789 was closed")


def test_detects_ifsc_and_employee_id():
    found = types("IFSC HDFC0001234 for employee NC-10482")
    assert {"BANK_ACCOUNT", "EMPLOYEE_ID"} <= found


def test_test_national_id_with_context():
    assert "TEST_NATIONAL_ID" in types("My Aadhaar test ID is 9999 1234 5678")


def test_salary_amount_needs_salary_context():
    detector = get_pii_detector()
    salary = [e for e in detector.analyze("Her salary is INR 24 LPA") if e.entity_type == "SALARY_AMOUNT"]
    assert salary and salary[0].score >= 0.7
    expense = [e for e in detector.analyze("The dinner limit is USD 75 per attendee") if e.entity_type == "SALARY_AMOUNT"]
    assert all(e.score < 0.7 for e in expense)


def test_detects_inline_credentials():
    assert "CREDENTIAL" in types("the password is Hunter2Secret!")
    assert "CREDENTIAL" in types("use key sk-abcdefghijklmnopqrstuvwxyz123456")


def test_anonymize_replaces_spans():
    d = get_pii_detector()
    text = "Email jane.doe@example.test now"
    out = d.anonymize(text, d.analyze(text))
    assert "jane.doe" not in out and "<EMAIL_ADDRESS>" in out


def test_mask_value_never_reveals_full_value():
    assert mask_value("CREDIT_CARD", "4111 1111 1111 1111") == "•••• 1111"
    assert "secret" not in mask_value("CREDENTIAL", "password: secret")
    assert mask_value("EMAIL_ADDRESS", "jane@example.test").startswith("j•••@")


def test_clean_text_has_no_entities():
    assert types("What is the international vendor refund policy?") == set()
