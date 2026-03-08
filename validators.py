"""
Transaction validation and fraud detection rules.

These are standard checks used across the payments industry.
Sources cited in each rule below.

5 layers:
1. Schema validation — required fields, data types
2. Regulatory limits — RBI-mandated per-txn and daily caps
3. Velocity check — rate limiting per sender (anti-bot)
4. Duplicate detection — idempotency / replay protection
5. Blacklist screening — sanctions / fraud list check
"""

from database import (
    count_recent_by_sender, find_duplicate, is_blacklisted,
    get_sender_daily_total
)

# --- Configuration ---
# These would come from a config file or env vars in production.
# Values below are based on real-world standards.

SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "INR", "JPY"]

# RBI Master Direction on Payment Aggregators (March 2020, updated 2024):
# UPI per-transaction cap is ₹1,00,000. We use a generic default.
# Source: rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12156
PER_TXN_LIMIT = 100000

# RBI circular on UPI daily limits.
# Most banks enforce ₹1,00,000/day aggregate per account for UPI.
# Source: NPCI UPI Procedural Guidelines, Section 5.5
DAILY_LIMIT = 500000

# Velocity threshold: max N transactions per sender in a time window.
# Stripe uses similar rate limiting (docs.stripe.com/radar/rules).
# Razorpay's Thirdwatch/Shield does the same (razorpay.com/blog/fraud-detection).
VELOCITY_LIMIT = 10       # max transactions
VELOCITY_WINDOW_MIN = 10  # within this many minutes

# Duplicate detection window (seconds).
# Standard idempotency check — Stripe, Razorpay, PayPal all do this.
# Stripe: stripe.com/docs/api/idempotent_requests
DUPLICATE_WINDOW_SEC = 60


# --- Layer 1: Schema Validation ---

def check_required_fields(data):
    """
    Every transaction must include: amount, currency, sender, receiver.
    This is basic API contract validation — same as what any payment
    gateway enforces before processing.
    """
    required = ["amount", "currency", "sender", "receiver"]
    missing = [f for f in required if f not in data or not data[f]]
    if missing:
        return False, f"MISSING_FIELDS: {', '.join(missing)}"
    return True, None


def check_amount_type(amount):
    """Amount must be a number (int or float)."""
    if not isinstance(amount, (int, float)):
        return False, "INVALID_TYPE: amount must be a number"
    return True, None


def check_currency(currency):
    """
    Only process configured currencies.
    In production, this list comes from the payment processor's config.
    """
    if currency.upper() not in SUPPORTED_CURRENCIES:
        return False, "UNSUPPORTED_CURRENCY"
    return True, None


def check_self_transfer(sender, receiver):
    """
    Sender and receiver must differ.
    Self-transfers are a common fraud vector — used to test stolen credentials.
    Banks and UPI apps block these at the app layer.
    """
    if sender.strip().lower() == receiver.strip().lower():
        return False, "SELF_TRANSFER"
    return True, None


# --- Layer 2: Regulatory / Business Limits ---

def check_per_txn_limit(amount):
    """
    Per-transaction amount limit.

    RBI mandates caps on digital payments:
    - UPI: ₹1,00,000 per transaction (₹5,00,000 for some categories)
    - Wallets: ₹10,000 per month (for minimum KYC)
    Source: RBI Master Direction on Prepaid Payment Instruments, 2021
    Source: NPCI UPI Product Overview — npci.org.in/what-we-do/upi/product-overview
    """
    if amount <= 0:
        return False, "NEGATIVE_AMOUNT"
    if amount > PER_TXN_LIMIT:
        return False, "PER_TXN_LIMIT_EXCEEDED"
    return True, None


def check_daily_limit(sender, amount, currency):
    """
    Cumulative daily spending cap per sender.

    Banks enforce daily aggregate limits on UPI/NEFT/IMPS.
    NPCI UPI Procedural Guidelines Section 5.5 specify daily caps.
    This prevents a compromised account from being drained gradually.
    Source: npci.org.in/what-we-do/upi/upi-procedural-guidelines
    """
    today_total = get_sender_daily_total(sender, currency)
    if today_total + amount > DAILY_LIMIT:
        return False, "DAILY_LIMIT_EXCEEDED"
    return True, None


# --- Layer 3: Velocity Check (Rate Limiting) ---

def check_velocity(sender):
    """
    Rate limiting — flag if a sender exceeds N transactions in M minutes.

    Every payment processor does this:
    - Stripe Radar: "Block if > 5 payments in 1 hour" (configurable rule)
      Source: stripe.com/docs/radar/rules/reference
    - Razorpay Shield: Real-time velocity checks on all transactions
      Source: razorpay.com/docs/payments/shield
    - NPCI RADAR: NPCI's own system monitors UPI transaction velocity
      Source: npci.org.in (RADAR = Risk Assessment, Detection And Response)

    This catches bots, credential stuffing, and compromised accounts.
    """
    count = count_recent_by_sender(sender, minutes=VELOCITY_WINDOW_MIN)
    if count >= VELOCITY_LIMIT:
        return False, "VELOCITY_EXCEEDED"
    return True, None


# --- Layer 4: Duplicate / Replay Detection ---

def check_duplicate(sender, receiver, amount, currency):
    """
    Reject if the exact same transaction appeared within DUPLICATE_WINDOW_SEC.

    This is called an idempotency check. It prevents:
    - User double-clicking "Pay" button
    - Network retries sending the same request twice
    - Replay attacks (attacker captures and re-sends a valid request)

    Stripe uses idempotency keys for this (stripe.com/docs/api/idempotent_requests).
    Razorpay generates unique order IDs for the same reason.
    UPI uses unique transaction reference IDs (UTR) — NPCI rejects duplicate UTRs.
    """
    if find_duplicate(sender, receiver, amount, currency, seconds=DUPLICATE_WINDOW_SEC):
        return False, "DUPLICATE_TRANSACTION"
    return True, None


# --- Layer 5: Blacklist / Sanctions Screening ---

def check_blacklist(sender, receiver):
    """
    Check both parties against a blacklist.

    In production, this checks against:
    - OFAC SDN List (US sanctions) — treasury.gov/resource-center/sanctions
    - RBI's list of banned entities
    - Internal fraud database (accounts flagged by investigations)
    - PEP lists (Politically Exposed Persons) — for AML compliance

    AML (Anti-Money Laundering) regulations under PMLA 2002 (India)
    and BSA/AML (USA) require this for all financial transactions.
    Source: RBI Master Direction — Know Your Customer (KYC) Direction, 2016
    """
    if is_blacklisted(sender):
        return False, "SENDER_BLACKLISTED"
    if is_blacklisted(receiver):
        return False, "RECEIVER_BLACKLISTED"
    return True, None


# --- Main Entry Point ---

def validate_transaction(data):
    """
    Run all 5 layers of checks on a transaction.
    Returns (is_valid: bool, flags: list[str])

    We collect ALL flags (don't stop at first failure) so the caller
    gets the complete picture in one API call. This is standard practice —
    Stripe's response includes all triggered rules, not just the first.
    """
    flags = []

    # Layer 1: Schema — can't proceed without valid fields
    valid, flag = check_required_fields(data)
    if not valid:
        return False, [flag]

    valid, flag = check_amount_type(data["amount"])
    if not valid:
        return False, [flag]

    # Layer 2: Regulatory limits
    valid, flag = check_per_txn_limit(data["amount"])
    if not valid:
        flags.append(flag)

    valid, flag = check_currency(data["currency"])
    if not valid:
        flags.append(flag)

    valid, flag = check_self_transfer(data["sender"], data["receiver"])
    if not valid:
        flags.append(flag)

    # Daily limit check (only if currency is valid)
    if not any("UNSUPPORTED_CURRENCY" in f for f in flags):
        valid, flag = check_daily_limit(data["sender"], data["amount"], data["currency"])
        if not valid:
            flags.append(flag)

    # Layer 3: Velocity
    valid, flag = check_velocity(data["sender"])
    if not valid:
        flags.append(flag)

    # Layer 4: Duplicate detection
    valid, flag = check_duplicate(
        data["sender"], data["receiver"], data["amount"], data["currency"]
    )
    if not valid:
        flags.append(flag)

    # Layer 5: Blacklist
    valid, flag = check_blacklist(data["sender"], data["receiver"])
    if not valid:
        flags.append(flag)

    if flags:
        return False, flags

    return True, ["APPROVED"]