"""Idempotent seed script for the EVA database.

Inserts synthetic data into 8 relational tables using Faker.
All inserts use ``ON CONFLICT DO NOTHING`` so the script is safe to re-run.
Use ``--reset`` to truncate all tables first.

Usage::

    uv run python -m scripts.seed_db
    uv run python -m scripts.seed_db --reset
"""

import argparse as _argparse
import asyncio as _asyncio
import sys as _sys
import uuid as _uuid
from datetime import UTC
from datetime import datetime as _datetime
from decimal import Decimal as _Decimal

from faker import Faker as _Faker
from sqlalchemy import func as _func
from sqlalchemy import select as _select
from sqlalchemy import text as _text
from sqlalchemy.dialects.postgresql import insert as _pg_insert

from app.db.models import (
    BillingRecord,
    ConversationMessage,
    ConversationSession,
    CRMNote,
    Customer,
    Subscription,
    SupportTicket,
    UsageAnalytic,
)
from app.db.session import get_session_factory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRUNCATE_ORDER = [
    "conversation_messages",
    "billing_records",
    "support_tickets",
    "usage_analytics",
    "crm_notes",
    "conversation_sessions",
    "subscriptions",
    "customers",
]

PLAN_TIERS = ["free", "basic", "premium", "enterprise"]
SUBSCRIPTION_STATUSES = ["active", "trial", "cancelled", "inactive"]
BILLING_STATUSES = ["paid", "pending", "overdue"]
TICKET_STATUSES = ["open", "in_progress", "resolved", "closed"]
TICKET_PRIORITIES = ["low", "medium", "high", "critical"]
TICKET_CATEGORIES = ["billing", "technical", "account", "general"]
NOTE_TYPES = ["general", "complaint", "feature_request"]
SESSION_STATUSES = ["active", "completed"]
LANGUAGES = ["en", "bn"]
MESSAGE_ROLES = ["user", "assistant", "system"]

METRIC_NAMES = [
    "api_calls", "storage_used_mb", "active_users", "bandwidth_gb",
    "requests_per_min", "error_rate", "response_time_ms", "concurrent_sessions",
    "data_exported_mb", "login_attempts",
]

PLAN_NAMES = [
    "Free", "Basic Monthly", "Basic Annual", "Professional Monthly",
    "Professional Annual", "Enterprise Monthly", "Enterprise Annual",
]

# Row counts
NUM_CUSTOMERS = 20
NUM_SUBSCRIPTIONS = 30
NUM_BILLING_RECORDS = 90
NUM_SUPPORT_TICKETS = 40
NUM_USAGE_ANALYTICS = 200
NUM_CRM_NOTES = 30
NUM_CONVERSATION_SESSIONS = 25
NUM_CONVERSATION_MESSAGES = 100

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> _datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return _datetime.now(UTC)


def _date_between(fake: _Faker, start: str = "-2y", end: str = "now") -> _datetime:
    """Return a timezone-aware datetime between *start* and *end*."""
    dt = fake.date_time_between(start_date=start, end_date=end)
    return dt.replace(tzinfo=UTC)


def _pick_n(fake: _Faker, population: list, n: int) -> list:
    """Pick *n* items from *population* with replacement."""
    return [fake.random.choice(population) for _ in range(n)]


# ---------------------------------------------------------------------------
# Data generators (each returns a list of dicts suitable for ``.values()``)
# ---------------------------------------------------------------------------


def _make_customers(fake: _Faker) -> list[dict]:
    """Generate 20 customers."""
    rows: list[dict] = []
    for _ in range(NUM_CUSTOMERS):
        rows.append({
            "id": _uuid.uuid4(),
            "name": fake.name(),
            "email": fake.unique.email(),
            "phone": fake.phone_number(),
            "company": fake.company(),
            "plan_tier": fake.random.choice(PLAN_TIERS),
            "is_active": fake.random.random() > 0.2,  # 80% active
            "created_at": _date_between(fake, "-2y", "-1M"),
            "updated_at": _date_between(fake, "-1M", "now"),
        })
    return rows


def _make_subscriptions(fake: _Faker, customer_ids: list[_uuid.UUID]) -> list[dict]:
    """Generate 30 subscriptions linked to customers."""
    rows: list[dict] = []
    for _ in range(NUM_SUBSCRIPTIONS):
        start = _date_between(fake, "-18M", "now")
        status = fake.random.choice(SUBSCRIPTION_STATUSES)
        end = None
        if status == "cancelled":
            end = _date_between(fake, start, "now")
        elif status == "active":
            end = _date_between(fake, "now", "+1y")

        rows.append({
            "id": _uuid.uuid4(),
            "customer_id": fake.random.choice(customer_ids),
            "plan_name": fake.random.choice(PLAN_NAMES),
            "status": status,
            "start_date": start,
            "end_date": end,
            "monthly_amount": _Decimal(str(round(fake.random.uniform(9.99, 299.99), 2))),
            "created_at": start,
            "updated_at": _date_between(fake, start, "now"),
        })
    return rows


def _make_billing_records(
    fake: _Faker,
    customer_ids: list[_uuid.UUID],
    subscription_ids: list[_uuid.UUID],
) -> list[dict]:
    """Generate 90 billing records linked to customers and subscriptions."""
    rows: list[dict] = []
    for _ in range(NUM_BILLING_RECORDS):
        status = fake.random.choice(BILLING_STATUSES)
        due = _date_between(fake, "-1y", "+1M")
        paid_at = None
        if status == "paid":
            paid_at = _date_between(fake, "-1y", due)

        rows.append({
            "id": _uuid.uuid4(),
            "customer_id": fake.random.choice(customer_ids),
            "subscription_id": fake.random.choice(subscription_ids + [None]),
            "currency": "USD",
            "amount": _Decimal(str(round(fake.random.uniform(10.0, 500.0), 2))),
            "due_date": due,
            "status": status,
            "paid_at": paid_at,
            "description": fake.sentence(nb_words=10),
            "created_at": _date_between(fake, "-14M", "-1M"),
            "updated_at": _date_between(fake, "-1M", "now"),
        })
    return rows


def _make_support_tickets(fake: _Faker, customer_ids: list[_uuid.UUID]) -> list[dict]:
    """Generate 40 support tickets linked to customers."""
    rows: list[dict] = []
    for _ in range(NUM_SUPPORT_TICKETS):
        status = fake.random.choice(TICKET_STATUSES)
        resolved_at = None
        if status == "resolved":
            resolved_at = _date_between(fake, "-6M", "now")

        rows.append({
            "id": _uuid.uuid4(),
            "customer_id": fake.random.choice(customer_ids),
            "title": fake.sentence(nb_words=8),
            "status": status,
            "description": fake.paragraph(nb_sentences=4),
            "category": fake.random.choice(TICKET_CATEGORIES),
            "priority": fake.random.choice(TICKET_PRIORITIES),
            "assigned_to": fake.name(),
            "resolved_at": resolved_at,
            "created_at": _date_between(fake, "-12M", "-7d"),
            "updated_at": _date_between(fake, "-7d", "now"),
        })
    return rows


def _make_usage_analytics(fake: _Faker, customer_ids: list[_uuid.UUID]) -> list[dict]:
    """Generate 200 usage analytics rows linked to customers."""
    rows: list[dict] = []
    for _ in range(NUM_USAGE_ANALYTICS):
        period_start = _date_between(fake, "-3M", "now")
        rows.append({
            "id": _uuid.uuid4(),
            "customer_id": fake.random.choice(customer_ids),
            "metric_name": fake.random.choice(METRIC_NAMES),
            "metric_value": round(fake.random.uniform(0.1, 99999.9), 2),
            "period_start": period_start,
            "period_end": _date_between(fake, period_start, "now")
            if fake.random.random() > 0.2
            else None,
            "created_at": period_start,
            "updated_at": _date_between(fake, period_start, "now"),
        })
    return rows


def _make_crm_notes(fake: _Faker, customer_ids: list[_uuid.UUID]) -> list[dict]:
    """Generate 30 CRM notes linked to customers."""
    rows: list[dict] = []
    for _ in range(NUM_CRM_NOTES):
        rows.append({
            "id": _uuid.uuid4(),
            "customer_id": fake.random.choice(customer_ids),
            "content": fake.paragraph(nb_sentences=5),
            "note_type": fake.random.choice(NOTE_TYPES),
            "author": fake.name(),
            "created_at": _date_between(fake, "-12M", "now"),
            "updated_at": _date_between(fake, "-1M", "now"),
        })
    return rows


def _make_conversation_sessions(
    fake: _Faker,
    customer_ids: list[_uuid.UUID],
) -> list[dict]:
    """Generate 25 conversation sessions linked to customers."""
    rows: list[dict] = []
    for _ in range(NUM_CONVERSATION_SESSIONS):
        started = _date_between(fake, "-6M", "now")
        status = fake.random.choice(SESSION_STATUSES)
        ended = None
        if status == "completed":
            ended = _date_between(fake, started, "now")

        rows.append({
            "id": _uuid.uuid4(),
            "customer_id": fake.random.choice(customer_ids),
            "title": fake.sentence(nb_words=6),
            "session_status": status,
            "started_at": started,
            "ended_at": ended,
            "language": fake.random.choice(LANGUAGES),
            "summary": fake.paragraph(nb_sentences=3) if fake.random.random() > 0.3 else None,
            "tools_used": {"tools": _pick_n(fake, ["billing", "customer", "ticket", "knowledge", "analytics"], 2)},
            "created_at": started,
            "updated_at": ended or _date_between(fake, started, "now"),
        })
    return rows


def _make_conversation_messages(
    fake: _Faker,
    session_ids: list[_uuid.UUID],
) -> list[dict]:
    """Generate 100 conversation messages linked to sessions."""
    rows: list[dict] = []
    for _ in range(NUM_CONVERSATION_MESSAGES):
        role = fake.random.choice(MESSAGE_ROLES)
        token_ct = fake.random.randint(10, 500) if role != "system" else fake.random.randint(30, 200)
        tool_calls_val = None
        if role == "assistant" and fake.random.random() > 0.7:
            tool_calls_val = {"tools_called": _pick_n(fake, ["lookup_customer", "get_invoice", "search_knowledge"], 1)}

        rows.append({
            "id": _uuid.uuid4(),
            "session_id": fake.random.choice(session_ids),
            "role": role,
            "content": fake.paragraph(nb_sentences=4),
            "metadata_": {"source": "web", "browser": fake.random.choice(["chrome", "firefox", "safari"])},
            "tool_calls": tool_calls_val,
            "token_count": token_ct,
            "created_at": _date_between(fake, "-6M", "now"),
            "updated_at": _date_between(fake, "-1M", "now"),
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _seed(args: _argparse.Namespace) -> None:
    """Run the seed logic."""
    factory = get_session_factory()

    async with factory() as session:
        # -- Check if already seeded ------------------------------------------
        result = await session.execute(_select(_func.count(Customer.id)))
        existing = result.scalar() or 0

        if existing > 0 and not args.reset:
            print(
                f"Database already seeded ({existing} customers found). "
                "Use --reset to re-seed."
            )
            return

        # -- Truncate if --reset ----------------------------------------------
        if args.reset:
            for table_name in TRUNCATE_ORDER:
                await session.execute(_text(f'TRUNCATE TABLE "{table_name}" CASCADE'))
            print("Truncated all tables (CASCADE).")

        # -- Generate data ----------------------------------------------------
        fake = _Faker(locale="en_US")
        fake.seed_instance(42)

        print("Generating synthetic data...")

        customers = _make_customers(fake)
        customer_ids = [c["id"] for c in customers]

        subscriptions = _make_subscriptions(fake, customer_ids)
        subscription_ids = [s["id"] for s in subscriptions]

        billing_records = _make_billing_records(fake, customer_ids, subscription_ids)
        support_tickets = _make_support_tickets(fake, customer_ids)
        usage_analytics = _make_usage_analytics(fake, customer_ids)
        crm_notes = _make_crm_notes(fake, customer_ids)
        conversation_sessions = _make_conversation_sessions(fake, customer_ids)
        session_ids = [s["id"] for s in conversation_sessions]
        conversation_messages = _make_conversation_messages(fake, session_ids)

        # -- Insert (FK-safe order) -------------------------------------------
        print("Inserting customers...")
        await session.execute(
            _pg_insert(Customer)
            .values(customers)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting subscriptions...")
        await session.execute(
            _pg_insert(Subscription)
            .values(subscriptions)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting billing records...")
        await session.execute(
            _pg_insert(BillingRecord)
            .values(billing_records)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting support tickets...")
        await session.execute(
            _pg_insert(SupportTicket)
            .values(support_tickets)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting usage analytics...")
        await session.execute(
            _pg_insert(UsageAnalytic)
            .values(usage_analytics)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting CRM notes...")
        await session.execute(
            _pg_insert(CRMNote)
            .values(crm_notes)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting conversation sessions...")
        await session.execute(
            _pg_insert(ConversationSession)
            .values(conversation_sessions)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting conversation messages...")
        await session.execute(
            _pg_insert(ConversationMessage)
            .values(conversation_messages)
            .on_conflict_do_nothing(index_elements=["id"])
        )

        # -- Commit -----------------------------------------------------------
        await session.commit()
        print("Commit successful.")

        # -- Final row counts -------------------------------------------------
        print("\nFinal row counts:")
        table_info = [
            ("customers", Customer),
            ("subscriptions", Subscription),
            ("billing_records", BillingRecord),
            ("support_tickets", SupportTicket),
            ("usage_analytics", UsageAnalytic),
            ("crm_notes", CRMNote),
            ("conversation_sessions", ConversationSession),
            ("conversation_messages", ConversationMessage),
        ]
        for name, model in table_info:
            cnt = (await session.execute(_select(_func.count(model.id)))).scalar() or 0
            print(f"  {name}: {cnt}")


def _main() -> None:
    parser = _argparse.ArgumentParser(
        description="Seed the EVA database with synthetic Faker data.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate all tables before seeding.",
    )
    args = parser.parse_args()

    try:
        _asyncio.run(_seed(args))
    except KeyboardInterrupt:
        _sys.exit(130)


if __name__ == "__main__":
    _main()
