from flask import Flask, request, jsonify, render_template
from datetime import datetime, timezone
import logging

from database import init_db, save_transaction, get_recent_transactions, get_stats
from database import add_to_blacklist, remove_from_blacklist, get_blacklist
from validators import (
    validate_transaction,
    SUPPORTED_CURRENCIES, PER_TXN_LIMIT, DAILY_LIMIT,
    VELOCITY_LIMIT, VELOCITY_WINDOW_MIN, DUPLICATE_WINDOW_SEC
)

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Create tables on startup
init_db()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api")
def api_info():
    return jsonify({
        "service": "TransValidate",
        "version": "3.0.0",
        "description": "Transaction validation and fraud detection API",
        "endpoints": {
            "GET /": "Dashboard UI",
            "POST /validate": "Validate a transaction",
            "GET /transactions": "View transaction history (?limit=N)",
            "GET /stats": "Dashboard — approval rate, top senders",
            "GET /config": "View active validation rules and limits",
            "GET /blacklist": "View blacklisted entities",
            "POST /blacklist": "Add to blacklist",
            "DELETE /blacklist/<entity>": "Remove from blacklist",
            "GET /health": "Health check",
        }
    })


@app.route("/health")
def health():
    return jsonify(status="healthy", timestamp=datetime.now(timezone.utc).isoformat()), 200


@app.route("/config")
def config():
    """Show active validation rules. Useful for debugging and transparency."""
    return jsonify({
        "per_transaction_limit": PER_TXN_LIMIT,
        "daily_limit": DAILY_LIMIT,
        "supported_currencies": SUPPORTED_CURRENCIES,
        "velocity_limit": f"{VELOCITY_LIMIT} transactions per {VELOCITY_WINDOW_MIN} minutes",
        "duplicate_window": f"{DUPLICATE_WINDOW_SEC} seconds",
        "checks": [
            "Schema validation (required fields, data types)",
            "Per-transaction amount limit (RBI mandate)",
            "Daily cumulative limit per sender (RBI/NPCI guidelines)",
            "Currency whitelist",
            "Self-transfer prevention",
            "Velocity / rate limiting (anti-bot)",
            "Duplicate / replay detection (idempotency)",
            "Blacklist / sanctions screening (AML compliance)",
        ]
    })


@app.route("/validate", methods=["POST"])
def validate():
    """Run all fraud checks on a transaction."""
    data = request.get_json()

    if not data:
        return jsonify(valid=False, flags=["Request body must be JSON"]), 400

    is_valid, flags = validate_transaction(data)

    # Save to database for history and future velocity checks
    if "sender" in data and "receiver" in data:
        save_transaction(
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            amount=data.get("amount", 0),
            currency=data.get("currency", ""),
            valid=is_valid,
            flags=flags
        )

    logger.info(
        "Transaction: sender=%s receiver=%s amount=%s valid=%s flags=%s",
        data.get("sender"), data.get("receiver"), data.get("amount"), is_valid, flags
    )

    status_code = 200 if is_valid else 400
    return jsonify(valid=is_valid, flags=flags), status_code


@app.route("/transactions")
def transactions():
    """View recent transactions. Use ?limit=N to control count."""
    limit = request.args.get("limit", 50, type=int)
    rows = get_recent_transactions(limit)
    return jsonify(count=len(rows), transactions=rows)


@app.route("/stats")
def stats():
    """Dashboard stats — total, approved, rejected, approval rate, top senders."""
    return jsonify(get_stats())


@app.route("/blacklist", methods=["GET"])
def list_blacklist():
    """View all blacklisted entities."""
    return jsonify(get_blacklist())


@app.route("/blacklist", methods=["POST"])
def add_blacklist():
    """Add an entity to the blacklist. Body: {"entity": "name", "reason": "why"}"""
    data = request.get_json()
    if not data or "entity" not in data:
        return jsonify(error="entity is required"), 400
    add_to_blacklist(data["entity"], data.get("reason", ""))
    logger.info("Blacklisted: %s", data["entity"])
    return jsonify(message=f"{data['entity']} added to blacklist"), 201


@app.route("/blacklist/<entity>", methods=["DELETE"])
def delete_blacklist(entity):
    """Remove an entity from the blacklist."""
    removed = remove_from_blacklist(entity)
    if removed:
        return jsonify(message=f"{entity} removed from blacklist")
    return jsonify(error=f"{entity} not found in blacklist"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)