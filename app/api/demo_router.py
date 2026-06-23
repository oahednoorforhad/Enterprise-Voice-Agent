"""Demo router — scenario cloning for demo mode.

Mounted at ``/api/v1/demo``.
"""

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db_session
from app.db.models import (
    BillingRecord,
    ConversationSession,
    CRMNote,
    Customer,
    Subscription,
    SupportTicket,
    UsageAnalytic,
)

demo_router = APIRouter(prefix="/api/v1/demo", tags=["Demo"])

# Path anchored to this file so it works regardless of CWD
_SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "scenarios"

VALID_SCENARIOS = {
    "billing_dispute",
    "technical_bug",
    "happy_upgrade",
    "churn_risk",
    "new_onboarding",
}


class ApplyScenarioRequest(BaseModel):
    scenario_id: str


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO datetime string, return None if falsy."""
    if not value:
        return None
    # Handle both Z suffix and +00:00
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@demo_router.post("/apply-scenario")
async def apply_scenario(
    body: ApplyScenarioRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Clone a scenario's data into the authenticated demo user's account.

    1. Validates user is a demo account (is_demo=True).
    2. Deletes all existing child records in safe order.
    3. Reads the scenario JSON from disk.
    4. Inserts subscription → captures new UUID → inserts billing_records with it.
    5. Inserts tickets, analytics, CRM notes.
    6. Updates Customer.active_scenario.
    """
    if body.scenario_id not in VALID_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario_id {body.scenario_id!r}. Valid: {sorted(VALID_SCENARIOS)}",
        )

    customer_id = uuid.UUID(current_user["customer_id"])

    # Fetch customer and check demo status
    result = await session.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if not customer.is_demo:
        raise HTTPException(status_code=403, detail="Only demo accounts can apply scenarios")

    # Load scenario JSON
    scenario_path = _SCENARIOS_DIR / f"{body.scenario_id}.json"
    if not scenario_path.exists():
        raise HTTPException(status_code=500, detail=f"Scenario file not found: {scenario_path}")

    with scenario_path.open() as f:
        scenario = json.load(f)

    # --- Delete existing data in safe order ---
    await session.execute(delete(BillingRecord).where(BillingRecord.customer_id == customer_id))
    await session.execute(delete(SupportTicket).where(SupportTicket.customer_id == customer_id))
    await session.execute(delete(UsageAnalytic).where(UsageAnalytic.customer_id == customer_id))
    await session.execute(delete(CRMNote).where(CRMNote.customer_id == customer_id))
    await session.execute(delete(ConversationSession).where(ConversationSession.customer_id == customer_id))
    await session.execute(delete(Subscription).where(Subscription.customer_id == customer_id))

    # --- Insert subscription first, capture new UUID ---
    sub_data = scenario["subscription"]
    new_subscription = Subscription(
        customer_id=customer_id,
        plan_name=sub_data["plan_name"],
        status=sub_data["status"],
        start_date=_parse_dt(sub_data["start_date"]),
        end_date=_parse_dt(sub_data.get("end_date")),
        monthly_amount=sub_data["monthly_amount"],
    )
    session.add(new_subscription)
    await session.flush()  # populate new_subscription.id

    new_sub_id = new_subscription.id

    # --- Insert billing records, wiring subscription_id ---
    for rec in scenario.get("billing_records", []):
        session.add(BillingRecord(
            customer_id=customer_id,
            subscription_id=new_sub_id,
            amount=rec["amount"],
            currency=rec.get("currency", "USD"),
            status=rec["status"],
            description=rec.get("description"),
            due_date=_parse_dt(rec["due_date"]),
            paid_at=_parse_dt(rec.get("paid_at")),
        ))

    # --- Insert support tickets ---
    for ticket in scenario.get("support_tickets", []):
        session.add(SupportTicket(
            customer_id=customer_id,
            title=ticket["title"],
            status=ticket["status"],
            description=ticket.get("description"),
            category=ticket.get("category"),
            priority=ticket["priority"],
            assigned_to=ticket.get("assigned_to"),
            resolved_at=_parse_dt(ticket.get("resolved_at")),
        ))

    # --- Insert usage analytics ---
    for analytic in scenario.get("usage_analytics", []):
        session.add(UsageAnalytic(
            customer_id=customer_id,
            metric_name=analytic["metric_name"],
            metric_value=analytic["metric_value"],
            period_start=_parse_dt(analytic["period_start"]),
            period_end=_parse_dt(analytic.get("period_end")),
        ))

    # --- Insert CRM notes ---
    for note in scenario.get("crm_notes", []):
        session.add(CRMNote(
            customer_id=customer_id,
            content=note["content"],
            note_type=note.get("note_type"),
            author=note.get("author"),
        ))

    # --- Update Customer.active_scenario ---
    customer.active_scenario = body.scenario_id
    session.add(customer)

    await session.commit()

    return {
        "success": True,
        "scenario_id": body.scenario_id,
        "active_scenario": body.scenario_id,
        "customer_id": str(customer_id),
    }
