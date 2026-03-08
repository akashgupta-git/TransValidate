# TransValidate

**Transaction Validation & Fraud Detection API** — enforces the same financial rules used by Razorpay, Stripe, and mandated by RBI/NPCI for UPI payments.

5 layers of validation · 49 automated tests · CI/CD · Docker · Terraform on AWS

![Python](https://img.shields.io/badge/Python-3.9-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?logo=flask)
![Tests](https://img.shields.io/badge/Tests-49%20passed-brightgreen)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-AWS-purple?logo=terraform)

---

## The Problem

Every digital payment — UPI, cards, wallets — passes through a fraud detection layer before money moves. Without it:

- A frontend bug sends ₹10,00,000 when RBI caps UPI at ₹1,00,000
- A compromised account drains funds through hundreds of small transfers
- Network retries or double-clicks debit the user twice
- A sanctioned entity keeps transacting undetected

**TransValidate is that layer.** It validates transactions against RBI-mandated rules, rate-limits suspicious senders, detects duplicates, screens against blacklists, and logs every decision for audit compliance.

---

## Quick Start

```bash
# Clone & install
git clone https://github.com/akashgupta-git/TransValidate.git
cd TransValidate
pip install -r requirements.txt

# Run tests
make test            # 49 tests, ~0.4s

# Start the app
make run             # http://localhost:5002

# Or with Docker
make docker-up       # http://localhost:5002
```

Open **http://localhost:5002** in your browser for the dashboard UI.

---

## Dashboard

The web UI lets you validate transactions, view audit logs, monitor stats, and manage blacklists — all from the browser.

| Tab | What it shows |
|-----|---------------|
| **Validate** | Form to submit a transaction — shows APPROVED (green) or REJECTED (red) with specific flags |
| **Transactions** | Audit log of all past transactions with status, flags, and timestamps |
| **Stats** | Total / Approved / Rejected counts, approval rate, top senders |
| **Blacklist** | Add, view, and remove entities from the sanctions list |
| **Config** | All active rules and their current thresholds |

The API works independently — the UI is a demo layer on top. All endpoints accept and return JSON.

---

## How It Works — 5 Layers of Validation

Every transaction passes through all 5 layers. All triggered flags are collected and returned in one response (same pattern as Stripe Radar).

```
POST /validate
     │
     ▼
┌─────────────────────────────────────────────┐
│  Layer 1: Schema Validation                 │  → MISSING_FIELDS, INVALID_TYPE
│  Layer 2: Regulatory Limits (RBI/NPCI)      │  → PER_TXN_LIMIT_EXCEEDED, DAILY_LIMIT_EXCEEDED
│  Layer 3: Velocity Check (rate limiting)    │  → VELOCITY_EXCEEDED
│  Layer 4: Duplicate Detection (idempotency) │  → DUPLICATE_TRANSACTION
│  Layer 5: Blacklist Screening (AML)         │  → SENDER_BLACKLISTED, RECEIVER_BLACKLISTED
└─────────────────────────────────────────────┘
     │
     ▼
 { "valid": true/false, "flags": [...] }
```

### Rules & Sources

| Rule | Threshold | Source |
|------|-----------|--------|
| Per-transaction limit | ₹1,00,000 | [RBI Master Direction on Payment Aggregators (2020)](https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12156) |
| Daily cumulative limit | ₹5,00,000 per sender per currency | [NPCI UPI Procedural Guidelines, Section 5.5](https://www.npci.org.in/what-we-do/upi/upi-procedural-guidelines) |
| Velocity | Max 10 txns per sender in 10 min | [Stripe Radar Rules](https://stripe.com/docs/radar/rules), [NPCI RADAR](https://www.npci.org.in), Razorpay Shield |
| Duplicate detection | 60-second idempotency window | [Stripe Idempotent Requests](https://stripe.com/docs/api/idempotent_requests), UPI UTR |
| Blacklist screening | Both sender & receiver checked | [OFAC SDN List](https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists), [PMLA 2002](https://legislative.gov.in/sites/default/files/A2003-15.pdf), [RBI KYC Direction 2016](https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566) |
| Self-transfer block | sender ≠ receiver | Standard across Stripe, Razorpay, UPI apps |
| Currency whitelist | USD, EUR, GBP, INR, JPY | PCI DSS merchant configuration |

### Industry Comparison

| TransValidate | Stripe | Razorpay | NPCI/UPI |
|---|---|---|---|
| `check_per_txn_limit()` | Radar: `amount > threshold` | Shield amount check | UPI per-txn cap |
| `check_daily_limit()` | Custom Radar rule | Account daily limits | Bank-enforced daily cap |
| `check_velocity()` | Radar: "Block if > N in M hours" | Shield velocity engine | NPCI RADAR |
| `check_duplicate()` | Idempotency Key header | Order ID uniqueness | UTR deduplication |
| `check_blacklist()` | Radar blocklists | Risk assessment lists | RBI sanctions + OFAC |

---

## API Reference

### `POST /validate` — Validate a transaction

```bash
curl -X POST http://localhost:5002/validate \
  -H "Content-Type: application/json" \
  -d '{"amount": 500, "currency": "INR", "sender": "alice", "receiver": "bob"}'
```

**Approved:**
```json
{ "valid": true, "flags": ["APPROVED"] }
```

**Rejected** (all triggered rules returned at once):
```json
{ "valid": false, "flags": ["PER_TXN_LIMIT_EXCEEDED", "SELF_TRANSFER"] }
```

### Other Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard UI |
| `GET` | `/health` | Health check (used by Docker & load balancers) |
| `GET` | `/config` | Active rules and current thresholds |
| `GET` | `/transactions?limit=N` | Audit log — recent transactions |
| `GET` | `/stats` | Total, approved, rejected, approval rate, top senders |
| `GET` | `/blacklist` | View all blacklisted entities |
| `POST` | `/blacklist` | Add entity: `{"entity": "name", "reason": "why"}` |
| `DELETE` | `/blacklist/<entity>` | Remove entity from blacklist |
| `GET` | `/api` | JSON service info and endpoint list |

---

## Architecture

```
┌──────────────┐        ┌──────────────────┐
│  Payment App │  POST  │   TransValidate  │
│  (PhonePe,   │───────▶│   Flask API      │
│   GPay, etc) │◀───────│   + SQLite       │
└──────┬───────┘  JSON  └────────┬─────────┘
       │                         │ audit log
       │ (only if valid=true)    ▼
       ▼                  ┌──────────────┐
┌──────────────┐          │  SQLite DB   │
│ NPCI / Bank  │          │  (WAL mode)  │
│ (settlement) │          └──────────────┘
└──────────────┘
```

### DevOps Pipeline

```
git push
   │
   ├──▶ GitHub Actions ──▶ pytest (49 tests) ──▶ Docker build ──▶ Smoke test /health
   │
   └──▶ Jenkins ──▶ pytest ──▶ SSH deploy to EC2 ──▶ Docker rebuild + restart
                                    │
                                    ▼
                            AWS EC2 (Terraform)
                            ├── VPC + Subnet
                            ├── Security Group (22, 80, 5002)
                            └── t2.micro + Docker
```

---

## Testing

**49 tests** — 30 unit tests + 19 integration tests. Each test gets an isolated SQLite database via pytest's `tmp_path` fixture.

```bash
make test
```

```
tests/test_validators.py .... 30 passed    # Individual rule checks
tests/test_app.py .......... 19 passed     # Full API endpoint tests
========================= 49 passed in 0.36s =========================
```

| Test Category | Count | What It Covers |
|---|---|---|
| Schema validation | 5 | Required fields, type checks, float/int/string |
| Per-transaction limit | 5 | Valid, boundary (exactly ₹1L), exceeded, negative, zero |
| Daily limit | 3 | First txn, exceeded after pre-load, cross-currency isolation |
| Currency & self-transfer | 5 | Valid currencies, invalid currency, self-transfer (case-insensitive) |
| Velocity | 2 | Under limit, exceeded after 11 rapid transactions |
| Duplicate detection | 3 | Duplicate caught, different amount passes, different receiver passes |
| Blacklist | 3 | Sender blocked, receiver blocked, clean parties pass |
| Full pipeline | 3 | Valid end-to-end, multiple failures at once, early stop on schema error |
| API endpoints | 19 | Every endpoint tested including CRUD, limits, edge cases |

---

## Infrastructure

### Docker

```bash
make docker-up       # Build + start
make docker-down     # Stop
```

- Base image: `python:3.9-slim`
- SQLite persistence via named volume (`db_data:/app/data`)
- Health check: hits `/health` every 30s

### Terraform → AWS

```bash
make deploy          # Provision VPC + EC2 + Security Group
make destroy         # Tear down everything (billing stops instantly)
```

| Resource | Config |
|---|---|
| VPC | `10.0.0.0/16`, public subnet in `ap-south-1a` |
| Security Group | Inbound: 22 (SSH), 80 (HTTP), 5002 (API) |
| EC2 | `t2.micro` (free-tier), Ubuntu, Docker auto-installed via `user_data` |
| Variables | Region and instance type configurable in `terraform/variables.tf` |

---

## Project Structure

```
TransValidate/
├── app.py                        # Flask API — 9 endpoints + dashboard
├── validators.py                 # 5 validation layers with cited sources
├── database.py                   # SQLite (WAL mode), parameterized queries
├── templates/
│   └── index.html                # Dashboard UI (single-page, no framework)
├── tests/
│   ├── test_validators.py        # 30 unit tests — one per rule
│   └── test_app.py               # 19 integration tests — full API cycle
├── Dockerfile                    # python:3.9-slim, port 5002
├── docker-compose.yml            # Volume-backed SQLite, healthcheck
├── Makefile                      # run, test, docker-up, deploy, destroy
├── Jenkinsfile                   # CI/CD: test → SSH deploy to EC2
├── .github/workflows/ci.yml     # CI: test → Docker build → smoke test
├── requirements.txt              # flask, pytest
└── terraform/
    ├── main.tf                   # VPC, Subnet, IGW, SG, EC2
    ├── variables.tf              # region, instance_type
    └── outputs.tf                # public_ip, app_url
```

---

## Makefile

| Command | Description |
|---------|-------------|
| `make run` | Start Flask locally on port 5002 |
| `make test` | Run all 49 pytest tests |
| `make docker-up` | Build image + start container |
| `make docker-down` | Stop container |
| `make deploy` | `terraform apply` — provision AWS |
| `make destroy` | `terraform destroy` — tear down AWS |
| `make clean` | Remove containers, images, pycache |

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Language | Python 3.9 | Readable, rich stdlib, industry standard for scripting/automation |
| Framework | Flask | Lightweight, minimal boilerplate, serves both API and HTML |
| Database | SQLite (WAL mode) | Zero setup, built into Python, parameterized queries prevent SQL injection |
| Testing | pytest | Fixtures (`tmp_path` for DB isolation), clean assertion syntax |
| Containerization | Docker + Compose | Reproducible builds, volume persistence, healthcheck |
| CI | GitHub Actions | Free for public repos, runs on every push |
| CD | Jenkins | Industry standard, SSH deploy to EC2 |
| Infrastructure | Terraform | Declarative IaC, one-command deploy/destroy |
| Cloud | AWS (VPC, EC2) | Free-tier eligible, `ap-south-1` for low latency in India |

---

## Security

- **SQL Injection**: All database queries use parameterized statements (`?` placeholders) — user input never touches query strings
- **Input Validation**: 5 layers of validation before any data is persisted
- **Network**: Security Group restricts inbound to ports 22, 80, 5002 only
- **Audit Trail**: Every transaction (approved and rejected) is logged with flags and timestamp