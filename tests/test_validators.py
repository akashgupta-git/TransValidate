"""
Unit tests for individual validation and fraud detection rules.
Each test targets one specific check function.
"""
import os
import pytest
from database import init_db, add_to_blacklist, save_transaction
from validators import (
    check_required_fields, check_amount_type, check_per_txn_limit,
    check_daily_limit, check_currency, check_self_transfer,
    check_velocity, check_duplicate, check_blacklist, validate_transaction,
    PER_TXN_LIMIT, DAILY_LIMIT, VELOCITY_LIMIT
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Use a temporary database for every test so tests don't affect each other."""
    os.environ["DB_PATH"] = str(tmp_path / "test.db")
    import database
    database.DB_PATH = str(tmp_path / "test.db")
    init_db()
    yield
    os.environ.pop("DB_PATH", None)


# --- Layer 1: Schema ---

def test_required_fields_all_present():
    valid, _ = check_required_fields({"amount": 1, "currency": "INR", "sender": "a", "receiver": "b"})
    assert valid is True


def test_required_fields_missing():
    valid, flag = check_required_fields({"amount": 100})
    assert valid is False
    assert "MISSING_FIELDS" in flag


def test_amount_type_valid():
    valid, _ = check_amount_type(100)
    assert valid is True


def test_amount_type_float():
    valid, _ = check_amount_type(99.50)
    assert valid is True


def test_amount_type_string():
    valid, flag = check_amount_type("abc")
    assert valid is False
    assert "INVALID_TYPE" in flag


# --- Layer 2: Regulatory / Business Limits ---

def test_per_txn_limit_valid():
    valid, _ = check_per_txn_limit(500)
    assert valid is True


def test_per_txn_limit_at_boundary():
    """Exactly at the limit should pass."""
    valid, _ = check_per_txn_limit(PER_TXN_LIMIT)
    assert valid is True


def test_per_txn_limit_exceeded():
    valid, flag = check_per_txn_limit(PER_TXN_LIMIT + 1)
    assert valid is False
    assert flag == "PER_TXN_LIMIT_EXCEEDED"


def test_per_txn_limit_negative():
    valid, flag = check_per_txn_limit(-10)
    assert valid is False
    assert flag == "NEGATIVE_AMOUNT"


def test_per_txn_limit_zero():
    valid, flag = check_per_txn_limit(0)
    assert valid is False
    assert flag == "NEGATIVE_AMOUNT"


def test_daily_limit_first_txn():
    """First transaction of the day — should always pass."""
    valid, _ = check_daily_limit("alice", 1000, "USD")
    assert valid is True


def test_daily_limit_exceeded():
    """Simulate previous approved transactions that push total over daily limit."""
    # Save enough approved transactions to nearly exhaust the limit
    save_transaction("bigspender", "vendor", DAILY_LIMIT - 100, "USD", True, ["APPROVED"])
    # Now try to send 200 more — should exceed
    valid, flag = check_daily_limit("bigspender", 200, "USD")
    assert valid is False
    assert flag == "DAILY_LIMIT_EXCEEDED"


def test_daily_limit_different_currency_not_counted():
    """Daily totals are per-currency — USD spending shouldn't affect INR limit."""
    save_transaction("multicurrency", "vendor", DAILY_LIMIT - 100, "USD", True, ["APPROVED"])
    valid, _ = check_daily_limit("multicurrency", 1000, "INR")
    assert valid is True


def test_currency_valid():
    valid, _ = check_currency("USD")
    assert valid is True


def test_currency_inr():
    valid, _ = check_currency("INR")
    assert valid is True


def test_currency_invalid():
    valid, flag = check_currency("XYZ")
    assert valid is False
    assert flag == "UNSUPPORTED_CURRENCY"


def test_self_transfer_caught():
    valid, flag = check_self_transfer("alice", "alice")
    assert valid is False
    assert flag == "SELF_TRANSFER"


def test_self_transfer_case_insensitive():
    valid, flag = check_self_transfer("Alice", "ALICE")
    assert valid is False
    assert flag == "SELF_TRANSFER"


def test_different_sender_receiver():
    valid, _ = check_self_transfer("alice", "bob")
    assert valid is True


# --- Layer 3: Velocity ---

def test_velocity_under_limit():
    valid, _ = check_velocity("new_user")
    assert valid is True


def test_velocity_exceeded():
    """Simulate 10+ transactions from same sender, then check if velocity catches it."""
    for i in range(VELOCITY_LIMIT + 1):
        save_transaction("spammer", f"receiver_{i}", 100, "USD", True, ["APPROVED"])
    valid, flag = check_velocity("spammer")
    assert valid is False
    assert flag == "VELOCITY_EXCEEDED"


# --- Layer 4: Duplicate / Replay Detection ---

def test_duplicate_detection():
    save_transaction("alice", "bob", 500, "USD", True, ["APPROVED"])
    valid, flag = check_duplicate("alice", "bob", 500, "USD")
    assert valid is False
    assert flag == "DUPLICATE_TRANSACTION"


def test_no_duplicate_different_amount():
    save_transaction("alice", "bob", 500, "USD", True, ["APPROVED"])
    valid, _ = check_duplicate("alice", "bob", 999, "USD")
    assert valid is True


def test_no_duplicate_different_receiver():
    save_transaction("alice", "bob", 500, "USD", True, ["APPROVED"])
    valid, _ = check_duplicate("alice", "charlie", 500, "USD")
    assert valid is True


# --- Layer 5: Blacklist / Sanctions ---

def test_blacklisted_sender():
    add_to_blacklist("fraudster", "known scammer")
    valid, flag = check_blacklist("fraudster", "bob")
    assert valid is False
    assert flag == "SENDER_BLACKLISTED"


def test_blacklisted_receiver():
    add_to_blacklist("criminal", "money laundering")
    valid, flag = check_blacklist("alice", "criminal")
    assert valid is False
    assert flag == "RECEIVER_BLACKLISTED"


def test_not_blacklisted():
    valid, _ = check_blacklist("alice", "bob")
    assert valid is True


# --- Full Pipeline ---

def test_full_valid_transaction():
    valid, flags = validate_transaction({
        "amount": 1000, "currency": "INR", "sender": "alice", "receiver": "bob"
    })
    assert valid is True
    assert "APPROVED" in flags


def test_full_multiple_failures():
    """Negative amount + unsupported currency + self-transfer = 3 flags."""
    valid, flags = validate_transaction({
        "amount": -100, "currency": "XYZ", "sender": "alice", "receiver": "alice"
    })
    assert valid is False
    assert any("NEGATIVE_AMOUNT" in f for f in flags)
    assert any("UNSUPPORTED_CURRENCY" in f for f in flags)
    assert any("SELF_TRANSFER" in f for f in flags)


def test_full_missing_fields_stops_early():
    """Missing fields should return immediately without running other checks."""
    valid, flags = validate_transaction({"amount": 100})
    assert valid is False
    assert len(flags) == 1
    assert "MISSING_FIELDS" in flags[0]