"""
Integration tests — hit the actual API endpoints and check responses.
These test the full request/response cycle through Flask.
"""
import os
import pytest
from database import init_db, save_transaction
from validators import PER_TXN_LIMIT, DAILY_LIMIT, VELOCITY_LIMIT


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Each test gets its own temporary database."""
    db_path = str(tmp_path / "test.db")
    os.environ["DB_PATH"] = db_path
    import database
    database.DB_PATH = db_path
    init_db()
    yield
    os.environ.pop("DB_PATH", None)


@pytest.fixture
def client():
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


VALID_TXN = {"amount": 500, "currency": "USD", "sender": "alice", "receiver": "bob"}


# --- Basic endpoints ---

def test_home_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"TransValidate" in resp.data


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "healthy"


def test_config_endpoint(client):
    resp = client.get("/config")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["per_transaction_limit"] == PER_TXN_LIMIT
    assert data["daily_limit"] == DAILY_LIMIT
    assert len(data["checks"]) >= 5


# --- Validation ---

def test_valid_transaction(client):
    resp = client.post("/validate", json=VALID_TXN)
    assert resp.status_code == 200
    assert resp.get_json()["valid"] is True
    assert "APPROVED" in resp.get_json()["flags"]


def test_negative_amount_rejected(client):
    resp = client.post("/validate", json={**VALID_TXN, "amount": -100})
    assert resp.status_code == 400
    assert any("NEGATIVE_AMOUNT" in f for f in resp.get_json()["flags"])


def test_exceeds_per_txn_limit(client):
    resp = client.post("/validate", json={**VALID_TXN, "amount": PER_TXN_LIMIT + 1})
    assert resp.status_code == 400
    assert any("PER_TXN_LIMIT_EXCEEDED" in f for f in resp.get_json()["flags"])


def test_missing_fields_rejected(client):
    resp = client.post("/validate", json={"amount": 100})
    assert resp.status_code == 400
    assert any("MISSING_FIELDS" in f for f in resp.get_json()["flags"])


def test_unsupported_currency(client):
    resp = client.post("/validate", json={**VALID_TXN, "currency": "XYZ"})
    assert resp.status_code == 400
    assert any("UNSUPPORTED_CURRENCY" in f for f in resp.get_json()["flags"])


def test_self_transfer_rejected(client):
    resp = client.post("/validate", json={**VALID_TXN, "receiver": "alice"})
    assert resp.status_code == 400
    assert any("SELF_TRANSFER" in f for f in resp.get_json()["flags"])


def test_empty_body_rejected(client):
    resp = client.post("/validate", content_type="application/json")
    assert resp.status_code == 400


# --- Daily Limit ---

def test_daily_limit_exceeded(client):
    """Pre-load approved transactions near the limit, then try one more."""
    from database import save_transaction as save_txn
    save_txn("alice", "vendor", DAILY_LIMIT - 100, "USD", True, ["APPROVED"])
    resp = client.post("/validate", json={**VALID_TXN, "amount": 200})
    assert resp.status_code == 400
    assert any("DAILY_LIMIT_EXCEEDED" in f for f in resp.get_json()["flags"])


# --- Transaction History ---

def test_transaction_history(client):
    client.post("/validate", json=VALID_TXN)
    resp = client.get("/transactions")
    assert resp.status_code == 200
    assert resp.get_json()["count"] >= 1


def test_transaction_history_limit(client):
    for _ in range(3):
        client.post("/validate", json=VALID_TXN)
    resp = client.get("/transactions?limit=1")
    assert resp.status_code == 200
    assert len(resp.get_json()["transactions"]) == 1


# --- Stats ---

def test_stats_endpoint(client):
    client.post("/validate", json=VALID_TXN)
    client.post("/validate", json={**VALID_TXN, "amount": -1})  # rejected
    resp = client.get("/stats")
    data = resp.get_json()
    assert data["total_transactions"] == 2
    assert data["approved"] == 1
    assert data["rejected"] == 1


# --- Blacklist CRUD ---

def test_add_and_view_blacklist(client):
    client.post("/blacklist", json={"entity": "badguy", "reason": "fraud"})
    resp = client.get("/blacklist")
    entities = [e["entity"] for e in resp.get_json()]
    assert "badguy" in entities


def test_blacklisted_sender_rejected(client):
    client.post("/blacklist", json={"entity": "alice", "reason": "compromised"})
    resp = client.post("/validate", json=VALID_TXN)
    assert resp.status_code == 400
    assert any("SENDER_BLACKLISTED" in f for f in resp.get_json()["flags"])


def test_remove_from_blacklist(client):
    client.post("/blacklist", json={"entity": "temp", "reason": "test"})
    resp = client.delete("/blacklist/temp")
    assert resp.status_code == 200
    resp = client.delete("/blacklist/temp")
    assert resp.status_code == 404


def test_blacklist_requires_entity(client):
    resp = client.post("/blacklist", json={"reason": "no entity"})
    assert resp.status_code == 400


# --- Duplicate Detection ---

def test_duplicate_transaction_caught(client):
    """Submit the exact same transaction twice — second should be flagged."""
    txn = {"amount": 777, "currency": "EUR", "sender": "dup_sender", "receiver": "dup_receiver"}
    resp1 = client.post("/validate", json=txn)
    assert resp1.status_code == 200
    resp2 = client.post("/validate", json=txn)
    assert resp2.status_code == 400
    assert any("DUPLICATE_TRANSACTION" in f for f in resp2.get_json()["flags"])