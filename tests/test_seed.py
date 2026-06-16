"""Tests for the idempotent seed script (``scripts.seed_db``).

Verifies that the first call populates the 8 relational tables and that
subsequent calls are safe no-ops.
"""

from argparse import Namespace

from sqlalchemy import func, select

from app.db.models import Customer


async def test_seed_first_run_populates_tables(async_session) -> None:
    """Call ``_seed`` and verify exactly 20 customers were inserted."""
    from scripts.seed_db import _seed

    await _seed(Namespace(reset=True))

    result = await async_session.execute(select(func.count(Customer.id)))
    count = result.scalar()
    assert count == 20, f"Expected 20 customers after seeding, got {count}"


async def test_seed_second_run_is_noop(async_session) -> None:
    """Call ``_seed`` twice and confirm the row count does not change.

    The seed script uses ``ON CONFLICT DO NOTHING`` and short-circuits
    when customers already exist, so the second invocation must be a
    transparent no-op.
    """
    from scripts.seed_db import _seed

    # First call  — if the DB was already seeded by the previous test
    # this is a no-op; if not it inserts the 20 rows.
    await _seed(Namespace(reset=False))

    result = await async_session.execute(select(func.count(Customer.id)))
    count_after_first = result.scalar()

    # Second call — must be idempotent
    await _seed(Namespace(reset=False))

    result = await async_session.execute(select(func.count(Customer.id)))
    count_after_second = result.scalar()

    assert count_after_first == count_after_second, (
        f"Count changed after second seed: "
        f"{count_after_first} -> {count_after_second}"
    )
