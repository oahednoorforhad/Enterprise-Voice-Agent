"""Seed the EVA database with one realistic customer and all related data.

Customer story
--------------
  Arman Hossain, CTO at NexaFlow Technologies Ltd.
  Enterprise Annual plan — active since Jan 2025.
  18 months of billing, 5 support tickets, monthly usage analytics,
  4 CRM notes, and 3 completed voice/chat sessions.

  The customer UUID matches the hardcoded ID in VoiceInterface.tsx and
  voice_router.py, so a live voice call works right after seeding.

Usage::

    uv run python -m scripts.seed_single_user
    uv run python -m scripts.seed_single_user --with-knowledge
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

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
# Fixed IDs  (customer UUID must match VoiceInterface.tsx / voice_router.py)
# ---------------------------------------------------------------------------

CUSTOMER_ID   = uuid.UUID("c63d2f89-9aa3-4157-8205-a7d6cfc23207")
SUBSCRIPTION_ID = uuid.uuid4()

TICKET_IDS = [uuid.uuid4() for _ in range(5)]
SESSION_IDS = [uuid.uuid4() for _ in range(3)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def dt(*args: int, **kw) -> datetime:
    """Return a UTC-aware datetime. Positional: year, month, day[, h, m, s]."""
    return datetime(*args, **kw, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def _customer() -> dict:
    return {
        "id": CUSTOMER_ID,
        "name": "Arman Hossain",
        "email": "arman.hossain@nexaflow.io",
        "phone": "+880 1812-345678",
        "company": "NexaFlow Technologies Ltd.",
        "plan_tier": "enterprise",
        "is_active": True,
        "created_at": dt(2024, 12, 10),
        "updated_at": dt(2026, 6, 1),
    }


def _subscription() -> dict:
    return {
        "id": SUBSCRIPTION_ID,
        "customer_id": CUSTOMER_ID,
        "plan_name": "Enterprise Annual",
        "status": "active",
        "start_date": dt(2025, 1, 1),
        "end_date": dt(2027, 1, 1),
        "monthly_amount": Decimal("299.00"),
        "created_at": dt(2025, 1, 1),
        "updated_at": dt(2026, 1, 1),
    }


def _billing_records() -> list[dict]:
    """18 monthly invoices (Jan 2025 – Jun 2026).

    17 paid + 1 pending.  March 2026 includes a note about the duplicate
    charge that was credited on the April invoice.
    """
    rows = []

    schedule = [
        # (year, month, day_due, day_paid, description_extra)
        (2025,  1,  1,  3,  "Monthly Enterprise invoice — January 2025"),
        (2025,  2,  1,  4,  "Monthly Enterprise invoice — February 2025"),
        (2025,  3,  1,  2,  "Monthly Enterprise invoice — March 2025"),
        (2025,  4,  1,  3,  "Monthly Enterprise invoice — April 2025"),
        (2025,  5,  1,  5,  "Monthly Enterprise invoice — May 2025"),
        (2025,  6,  1,  2,  "Monthly Enterprise invoice — June 2025"),
        (2025,  7,  1,  4,  "Monthly Enterprise invoice — July 2025"),
        (2025,  8,  1,  3,  "Monthly Enterprise invoice — August 2025"),
        (2025,  9,  1,  2,  "Monthly Enterprise invoice — September 2025"),
        (2025, 10,  1,  3,  "Monthly Enterprise invoice — October 2025"),
        (2025, 11,  1,  4,  "Monthly Enterprise invoice — November 2025"),
        (2025, 12,  1,  3,  "Monthly Enterprise invoice — December 2025"),
        (2026,  1,  1,  2,  "Monthly Enterprise invoice — January 2026"),
        (2026,  2,  1,  3,  "Monthly Enterprise invoice — February 2026"),
        (2026,  3,  1,  4,  "Monthly Enterprise invoice — March 2026 "
                            "(duplicate charge issued in error; $299 credit applied to April invoice)"),
        (2026,  4,  1,  2,  "Monthly Enterprise invoice — April 2026 "
                            "(includes $299 credit for March duplicate charge; net $0.00 billed)"),
        (2026,  5,  1,  3,  "Monthly Enterprise invoice — May 2026"),
        (2026,  6,  1,  None, "Monthly Enterprise invoice — June 2026"),  # pending
    ]

    for year, month, due_day, paid_day, desc in schedule:
        due = dt(year, month, due_day)
        is_pending = paid_day is None
        # April 2026: net $0.00 due to credit
        amount = Decimal("0.00") if (year == 2026 and month == 4) else Decimal("299.00")
        rows.append({
            "id": uuid.uuid4(),
            "customer_id": CUSTOMER_ID,
            "subscription_id": SUBSCRIPTION_ID,
            "currency": "USD",
            "amount": amount,
            "due_date": due,
            "status": "pending" if is_pending else "paid",
            "paid_at": dt(year, month, paid_day) if paid_day else None,
            "description": desc,
            "created_at": due,
            "updated_at": dt(2026, 6, 10) if is_pending else dt(year, month, paid_day or 1),
        })

    return rows


def _support_tickets() -> list[dict]:
    return [
        {
            "id": TICKET_IDS[0],
            "customer_id": CUSTOMER_ID,
            "title": "Double charge on March 2026 invoice — $299 billed twice",
            "status": "resolved",
            "description": (
                "Customer reported being charged $299 twice on 4 Mar and 6 Mar 2026 for the same "
                "monthly invoice period.  Finance confirmed a billing system glitch during the "
                "batch processing window.  A credit of $299 was applied to the April 2026 invoice, "
                "resulting in a $0.00 net charge for April.  Customer confirmed satisfaction."
            ),
            "category": "billing",
            "priority": "high",
            "assigned_to": "Ritu Sharma (Billing Support)",
            "resolved_at": dt(2026, 4, 2),
            "created_at": dt(2026, 3, 18),
            "updated_at": dt(2026, 4, 2),
        },
        {
            "id": TICKET_IDS[1],
            "customer_id": CUSTOMER_ID,
            "title": "Cannot export contacts list to CSV format",
            "status": "closed",
            "description": (
                "User attempted to export ~12,000 contacts to CSV via the 'Data Export' panel. "
                "The export job started but completed with a partial file (only 3,200 rows). "
                "Root cause: export worker timeout at 30 s for large datasets.  Fix deployed in "
                "v3.4.2 — export timeout raised to 120 s and chunked streaming enabled.  "
                "Customer re-exported successfully."
            ),
            "category": "technical",
            "priority": "medium",
            "assigned_to": "Dev Ops Team",
            "resolved_at": dt(2026, 2, 20),
            "created_at": dt(2026, 2, 10),
            "updated_at": dt(2026, 2, 20),
        },
        {
            "id": TICKET_IDS[2],
            "customer_id": CUSTOMER_ID,
            "title": "SSO login fails for all users after Azure AD app registration update",
            "status": "open",
            "description": (
                "Following an Azure AD app registration update on 29 Apr 2026, all 52 team members "
                "are unable to log in via SSO.  Error shown: 'AADSTS50011: The reply URL specified "
                "in the request does not match the reply URLs configured for the application'.  "
                "The team updated their Azure AD redirect URIs but did not include the new "
                "CloudDesk callback endpoint introduced in v3.5.0.  Awaiting customer confirmation "
                "that the correct callback URL has been added."
            ),
            "category": "technical",
            "priority": "high",
            "assigned_to": "Karim Uddin (Enterprise Support)",
            "resolved_at": None,
            "created_at": dt(2026, 5, 1),
            "updated_at": dt(2026, 6, 15),
        },
        {
            "id": TICKET_IDS[3],
            "customer_id": CUSTOMER_ID,
            "title": "API rate limit exceeded during bulk contact import — 50k records",
            "status": "in_progress",
            "description": (
                "Customer's automated import pipeline sends 50,000 contact records as a single "
                "POST batch to /api/v1/contacts/import.  The request triggers the 500 req/min "
                "rate limiter and fails with HTTP 429 after ~300 records.  Recommended fix: "
                "migrate to the /api/v1/bulk-import endpoint (2,000 records/request, no per-minute "
                "cap on Enterprise plan) and implement exponential backoff.  API team scheduled "
                "a walkthrough call for 25 Jun 2026."
            ),
            "category": "technical",
            "priority": "medium",
            "assigned_to": "API Integration Team",
            "resolved_at": None,
            "created_at": dt(2026, 6, 8),
            "updated_at": dt(2026, 6, 18),
        },
        {
            "id": TICKET_IDS[4],
            "customer_id": CUSTOMER_ID,
            "title": "Request to add 5 additional team member seats to Enterprise plan",
            "status": "closed",
            "description": (
                "Customer requested 5 additional seats (from 45 to 50 seats).  Enterprise plan "
                "allows unlimited seats at no extra per-seat charge.  Seats provisioned by account "
                "team on 15 Jan 2026.  Customer confirmed all 5 new users have logged in."
            ),
            "category": "account",
            "priority": "low",
            "assigned_to": "Account Management",
            "resolved_at": dt(2026, 1, 15),
            "created_at": dt(2026, 1, 5),
            "updated_at": dt(2026, 1, 15),
        },
    ]


def _usage_analytics() -> list[dict]:
    """48 rows: 8 metrics across 6 months (Jan – Jun 2026).

    Values show realistic growth trends for a 50-user enterprise team.
    """
    # (metric_name, [jan, feb, mar, apr, may, jun])
    metrics = [
        ("api_calls",            [350_000, 382_000, 411_000, 395_000, 428_000, 452_000]),
        ("active_users",         [43,      45,      47,      46,      49,      52     ]),
        ("storage_used_mb",      [7_200,   7_680,   8_140,   8_310,   8_760,   9_120  ]),
        ("bandwidth_gb",         [11.2,    12.1,    13.4,    12.8,    14.2,    15.1   ]),
        ("error_rate",           [0.012,   0.009,   0.015,   0.011,   0.008,   0.007  ]),
        ("response_time_ms",     [245,     238,     251,     242,     235,     228    ]),
        ("concurrent_sessions",  [18,      21,      24,      22,      26,      29     ]),
        ("data_exported_mb",     [1_200,   980,     1_450,   1_100,   1_350,   1_680  ]),
    ]

    months = [
        (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6),
    ]

    rows = []
    for metric_name, values in metrics:
        for i, (year, month) in enumerate(months):
            period_start = dt(year, month, 1)
            # period_end = first day of next month (or None for current)
            if month < 12:
                period_end = dt(year, month + 1, 1)
            else:
                period_end = dt(year + 1, 1, 1)
            if year == 2026 and month == 6:
                period_end = None  # still in progress

            rows.append({
                "id": uuid.uuid4(),
                "customer_id": CUSTOMER_ID,
                "metric_name": metric_name,
                "metric_value": float(values[i]),
                "period_start": period_start,
                "period_end": period_end,
                "created_at": period_start,
                "updated_at": dt(2026, 6, 18),
            })

    return rows


def _crm_notes() -> list[dict]:
    return [
        {
            "id": uuid.uuid4(),
            "customer_id": CUSTOMER_ID,
            "content": (
                "Onboarding call completed with Arman Hossain (CTO) and his IT lead, Nadia Islam. "
                "43 users successfully provisioned on Enterprise plan.  Walked through the dashboard, "
                "pipeline stage configuration, API integration guide, and the bulk-import endpoint. "
                "The team is technically capable and plans to integrate CloudDesk with their internal "
                "ERP system within Q1 2025.  Action: schedule 30-day check-in for January 2025."
            ),
            "note_type": "general",
            "author": "Priya Menon (Customer Success)",
            "created_at": dt(2024, 12, 12),
            "updated_at": dt(2024, 12, 12),
        },
        {
            "id": uuid.uuid4(),
            "customer_id": CUSTOMER_ID,
            "content": (
                "Quarterly Business Review with Arman Hossain.  Usage is up 35% since onboarding — "
                "now at 45 active users with ~350k API calls/month.  Team expanded and ERP integration "
                "is live.  Discussed the Advanced Analytics add-on ($89/month) — Arman is interested "
                "but needs board sign-off.  Also mentioned a desire for custom webhook triggers in the "
                "automation builder.  Follow up Q3 2025 on analytics add-on decision.  "
                "NPS score given: 9/10."
            ),
            "note_type": "general",
            "author": "Priya Menon (Customer Success)",
            "created_at": dt(2025, 6, 15),
            "updated_at": dt(2025, 6, 15),
        },
        {
            "id": uuid.uuid4(),
            "customer_id": CUSTOMER_ID,
            "content": (
                "ESCALATION — Billing dispute.  Arman contacted support reporting two $299 charges "
                "on his March 2026 statement (4 Mar and 6 Mar).  Finance confirmed a billing engine "
                "bug during the monthly batch run caused duplicate authorisation.  Issued a $299 "
                "credit to be applied against the April 2026 invoice, resulting in a net $0 charge "
                "for April.  Ticket raised and resolved within 15 days.  Customer was frustrated "
                "initially but satisfied with the resolution.  No churn risk at this time."
            ),
            "note_type": "complaint",
            "author": "Karim Uddin (Enterprise Support)",
            "created_at": dt(2026, 3, 22),
            "updated_at": dt(2026, 4, 2),
        },
        {
            "id": uuid.uuid4(),
            "customer_id": CUSTOMER_ID,
            "content": (
                "Renewal discussion initiated for January 2027 contract expiry.  Arman expressed "
                "strong intent to renew, requesting a 2-year term at a discounted rate.  Current "
                "MRR: $299.  Proposed 2-year deal at $259/month (13% discount).  Also raised the "
                "ongoing API rate-limit issue affecting their bulk import pipeline — escalated to "
                "the API Integration team (ticket open).  Renewal call scheduled for August 2026.  "
                "Upsell opportunity: Advanced Analytics add-on still open from last QBR."
            ),
            "note_type": "general",
            "author": "Priya Menon (Customer Success)",
            "created_at": dt(2026, 6, 5),
            "updated_at": dt(2026, 6, 5),
        },
    ]


def _conversation_sessions() -> list[dict]:
    sessions = [
        {
            "id": SESSION_IDS[0],
            "customer_id": CUSTOMER_ID,
            "title": "Billing dispute — double charge on March invoice",
            "session_status": "completed",
            "started_at": dt(2026, 3, 20, 10, 15, 0),
            "ended_at":   dt(2026, 3, 20, 10, 28, 0),
            "language": "en",
            "summary": (
                "Customer reported a duplicate $299 charge on the March 2026 invoice. "
                "EVA retrieved billing history, confirmed the duplicate, and informed the customer "
                "a $299 credit would be applied to the April invoice.  A support ticket was raised. "
                "Customer expressed satisfaction with the resolution."
            ),
            "tools_used": {"tools": ["get_billing_history", "get_customer_profile"]},
            "created_at": dt(2026, 3, 20, 10, 15, 0),
            "updated_at": dt(2026, 3, 20, 10, 28, 0),
        },
        {
            "id": SESSION_IDS[1],
            "customer_id": CUSTOMER_ID,
            "title": "SSO failure after Azure AD configuration update",
            "session_status": "completed",
            "started_at": dt(2026, 5, 8, 14, 30, 0),
            "ended_at":   dt(2026, 5, 8, 14, 47, 0),
            "language": "en",
            "summary": (
                "Customer reported that all 52 users were locked out of SSO after an Azure AD "
                "app-registration update.  EVA retrieved account details, identified the mismatch "
                "between Azure AD reply URLs and the new CloudDesk SSO callback URL (v3.5.0), "
                "provided the correct callback URL, and opened a follow-up support ticket."
            ),
            "tools_used": {"tools": ["get_customer_profile", "search_documentation", "get_support_tickets"]},
            "created_at": dt(2026, 5, 8, 14, 30, 0),
            "updated_at": dt(2026, 5, 8, 14, 47, 0),
        },
        {
            "id": SESSION_IDS[2],
            "customer_id": CUSTOMER_ID,
            "title": "API rate limit issues during bulk contact import",
            "session_status": "completed",
            "started_at": dt(2026, 6, 12, 9, 45, 0),
            "ended_at":   dt(2026, 6, 12, 10, 3, 0),
            "language": "en",
            "summary": (
                "Customer described bulk import failures caused by the 500 req/min rate limit. "
                "EVA retrieved usage analytics showing 452k API calls/month (up 28% QoQ) and "
                "the active subscription tier.  Recommended migrating to the /bulk-import endpoint "
                "and implementing backoff.  API Integration team walkthrough scheduled for 25 Jun 2026."
            ),
            "tools_used": {
                "tools": ["get_usage_analytics", "get_subscription_status", "search_documentation"]
            },
            "created_at": dt(2026, 6, 12, 9, 45, 0),
            "updated_at": dt(2026, 6, 12, 10, 3, 0),
        },
    ]
    return sessions


def _conversation_messages() -> list[dict]:
    rows = []

    # -- Session 0: billing dispute -------------------------------------------
    s0 = SESSION_IDS[0]
    msgs_s0 = [
        ("user",      dt(2026, 3, 20, 10, 15, 5),
         "Hi, I just noticed I was charged twice this month — two payments of $299 on my March "
         "invoice. Can you look into that for me?"),
        ("assistant", dt(2026, 3, 20, 10, 15, 20),
         "Hi Arman! Of course, let me pull up your billing history right away and see what happened."),
        ("assistant", dt(2026, 3, 20, 10, 15, 45),
         "I can see it — there are two $299 charges on March 4th and March 6th for the same "
         "invoice period. That was a billing system error on our end, and I'm really sorry about "
         "that. A credit of $299 will be applied to your April invoice, so you'll see a net $0 "
         "charge next month. I've also opened a support ticket so our finance team has a record."),
        ("user",      dt(2026, 3, 20, 10, 16, 30),
         "Okay, that's good to hear. When exactly will the credit appear?"),
        ("assistant", dt(2026, 3, 20, 10, 16, 50),
         "The credit will show up on your April 1st invoice, labelled 'Credit: March 2026 duplicate "
         "charge — $299.00'. You won't be charged anything for April as a result. Is there anything "
         "else I can help you with today?"),
        ("user",      dt(2026, 3, 20, 10, 17, 20),
         "No, that covers it. Thanks for sorting it out so quickly."),
        ("assistant", dt(2026, 3, 20, 10, 17, 35),
         "You're very welcome, Arman! The support ticket number is #BL-2026-0318. Feel free to "
         "reach out anytime. Have a great day!"),
    ]

    # -- Session 1: SSO issue -------------------------------------------------
    s1 = SESSION_IDS[1]
    msgs_s1 = [
        ("user",      dt(2026, 5, 8, 14, 30, 10),
         "Hey, we just updated our Azure AD configuration and now none of our 52 users can log in "
         "through SSO. We're getting an error about a reply URL mismatch."),
        ("assistant", dt(2026, 5, 8, 14, 30, 30),
         "That sounds stressful — let me check your account details and figure out what's going on."),
        ("assistant", dt(2026, 5, 8, 14, 31, 5),
         "Okay, I can see you're on our Enterprise plan which includes full SSO support. The error "
         "you're describing — 'AADSTS50011: reply URL does not match' — almost always means the "
         "redirect URI in your Azure AD app registration doesn't include the CloudDesk callback "
         "URL. Can you tell me exactly what error message your users are seeing?"),
        ("user",      dt(2026, 5, 8, 14, 32, 0),
         "It says: AADSTS50011: The reply URL specified in the request does not match the reply "
         "URLs configured for the application."),
        ("assistant", dt(2026, 5, 8, 14, 32, 30),
         "That confirms it. We updated the SSO callback URL in CloudDesk version 3.5.0 last month "
         "and the new endpoint isn't in your Azure AD app registration yet. Let me find the exact "
         "URL you need to add."),
        ("assistant", dt(2026, 5, 8, 14, 33, 15),
         "Here's what to do: in your Azure AD app registration, go to Authentication, and add "
         "this exact URL under Reply URLs: https://app.clouddesk.io/auth/sso/callback — make "
         "sure there's no trailing slash. Once you save, SSO should be restored within a few "
         "minutes. I'm also attaching a link to our SSO configuration guide in the support ticket "
         "I've just opened."),
        ("user",      dt(2026, 5, 8, 14, 35, 0),
         "Adding it now... okay, saved. Let me ask one of the team to test."),
        ("assistant", dt(2026, 5, 8, 14, 35, 20),
         "Great! Let me know how it goes. If it still doesn't work after 5 minutes, there might "
         "be a token cache issue and a logout + re-login should clear it."),
        ("user",      dt(2026, 5, 8, 14, 46, 0),
         "It's working! Everyone can log in again. Thank you so much."),
        ("assistant", dt(2026, 5, 8, 14, 46, 20),
         "Brilliant! Really glad we got that sorted. I've updated the support ticket as resolved. "
         "Is there anything else on your mind today?"),
        ("user",      dt(2026, 5, 8, 14, 46, 50),
         "Nope, that's all. Thanks again."),
        ("assistant", dt(2026, 5, 8, 14, 47, 0),
         "Anytime, Arman! Take care."),
    ]

    # -- Session 2: API rate limits -------------------------------------------
    s2 = SESSION_IDS[2]
    msgs_s2 = [
        ("user",      dt(2026, 6, 12, 9, 45, 10),
         "We're hitting API rate limits when we try to import our contact lists in bulk. "
         "Our script fails with a 429 after a few hundred records out of 50,000."),
        ("assistant", dt(2026, 6, 12, 9, 45, 30),
         "Ouch, that's frustrating when you've got 50k records to move. Let me check your "
         "usage stats and subscription details to get a clearer picture."),
        ("assistant", dt(2026, 6, 12, 9, 46, 10),
         "So your API calls have been climbing nicely — you're at about 452,000 calls this month, "
         "up around 28% from March. That growth is great, but you're getting close to the "
         "500 requests-per-minute ceiling on the standard API endpoint. "
         "When you send 50,000 contacts in a single batch, the system interprets each record "
         "as a separate API call internally, which trips the rate limiter pretty fast. "
         "Is your import script hitting the /contacts/import endpoint?"),
        ("user",      dt(2026, 6, 12, 9, 47, 15),
         "Yes, it posts to /api/v1/contacts/import — we built it about a year ago."),
        ("assistant", dt(2026, 6, 12, 9, 47, 40),
         "That explains it. There's actually a dedicated /bulk-import endpoint designed exactly "
         "for this — it accepts up to 2,000 records per request and has no per-minute rate cap "
         "on Enterprise plans. Let me pull up the documentation for it."),
        ("assistant", dt(2026, 6, 12, 9, 48, 30),
         "Here's the short version: switch your script to POST batches of 1,000–2,000 contacts "
         "to /api/v1/bulk-import with exponential backoff on any 429 responses. A 50,000-contact "
         "import should complete in 25–50 requests rather than 50,000 individual calls. "
         "I can arrange for our API Integration team to walk your engineer through the migration "
         "if that would help?"),
        ("user",      dt(2026, 6, 12, 9, 49, 30),
         "Yes please, that would be really useful."),
        ("assistant", dt(2026, 6, 12, 9, 49, 50),
         "Done — I've opened a ticket and assigned it to the API Integration team. They'll reach "
         "out to schedule a walkthrough within one business day. Expect a call around June 25th "
         "based on their current queue. Is there anything else I can help with today?"),
        ("user",      dt(2026, 6, 12, 9, 50, 20),
         "No, that's everything. Appreciate the quick help."),
        ("assistant", dt(2026, 6, 12, 9, 50, 35),
         "Happy to help! Talk soon, Arman."),
    ]

    tool_calls_map = {
        # session 0
        (s0, 1): {"tools_called": ["get_billing_history"]},
        (s0, 2): {"tools_called": ["get_customer_profile"]},
        # session 1
        (s1, 1): {"tools_called": ["get_customer_profile"]},
        (s1, 4): {"tools_called": ["search_documentation"]},
        # session 2
        (s2, 1): {"tools_called": ["get_usage_analytics", "get_subscription_status"]},
        (s2, 4): {"tools_called": ["search_documentation"]},
    }

    for session_id, raw_msgs in [(s0, msgs_s0), (s1, msgs_s1), (s2, msgs_s2)]:
        for idx, (role, ts, content) in enumerate(raw_msgs):
            tc = tool_calls_map.get((session_id, idx))
            rows.append({
                "id": uuid.uuid4(),
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata_": {"source": "voice", "session_index": idx},
                "tool_calls": tc,
                "token_count": len(content.split()) * 2,  # rough estimate
                "created_at": ts,
                "updated_at": ts,
            })

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _seed(with_knowledge: bool) -> None:
    factory = get_session_factory()

    async with factory() as session:
        print("Clearing existing data...")
        for table in [
            "conversation_messages", "billing_records", "support_tickets",
            "usage_analytics", "crm_notes", "conversation_sessions",
            "subscriptions", "customers",
        ]:
            await session.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))

        print("Inserting customer (Arman Hossain / NexaFlow Technologies)...")
        await session.execute(
            pg_insert(Customer).values([_customer()]).on_conflict_do_nothing(index_elements=["id"])
        )

        print("Inserting subscription (Enterprise Annual)...")
        await session.execute(
            pg_insert(Subscription).values([_subscription()]).on_conflict_do_nothing(index_elements=["id"])
        )

        billing = _billing_records()
        print(f"Inserting {len(billing)} billing records (Jan 2025 - Jun 2026)...")
        await session.execute(
            pg_insert(BillingRecord).values(billing).on_conflict_do_nothing(index_elements=["id"])
        )

        tickets = _support_tickets()
        print(f"Inserting {len(tickets)} support tickets...")
        await session.execute(
            pg_insert(SupportTicket).values(tickets).on_conflict_do_nothing(index_elements=["id"])
        )

        analytics = _usage_analytics()
        print(f"Inserting {len(analytics)} usage analytics rows (8 metrics x 6 months)...")
        await session.execute(
            pg_insert(UsageAnalytic).values(analytics).on_conflict_do_nothing(index_elements=["id"])
        )

        notes = _crm_notes()
        print(f"Inserting {len(notes)} CRM notes...")
        await session.execute(
            pg_insert(CRMNote).values(notes).on_conflict_do_nothing(index_elements=["id"])
        )

        sessions = _conversation_sessions()
        print(f"Inserting {len(sessions)} conversation sessions...")
        await session.execute(
            pg_insert(ConversationSession).values(sessions).on_conflict_do_nothing(index_elements=["id"])
        )

        messages = _conversation_messages()
        print(f"Inserting {len(messages)} conversation messages...")
        await session.execute(
            pg_insert(ConversationMessage).values(messages).on_conflict_do_nothing(index_elements=["id"])
        )

        await session.commit()

    print("\nRelational data committed.")
    print("\nRow counts:")
    async with factory() as session:
        for tbl in [
            "customers", "subscriptions", "billing_records", "support_tickets",
            "usage_analytics", "crm_notes", "conversation_sessions",
            "conversation_messages",
        ]:
            n = (await session.execute(text(f'SELECT COUNT(*) FROM "{tbl}"'))).scalar()
            print(f"  {tbl}: {n}")

    if with_knowledge:
        print("\nSeeding knowledge_documents (calls Gemini embedding API)...")
        from scripts.seed_knowledge import _seed as seed_knowledge
        await seed_knowledge()
    else:
        print("\nSkipped knowledge_documents.")
        print("Run:  uv run python -m scripts.seed_single_user --with-knowledge")
        print("  or: uv run python -m scripts.seed_knowledge")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed EVA with one realistic customer (Arman Hossain / NexaFlow)."
    )
    parser.add_argument(
        "--with-knowledge",
        action="store_true",
        help="Also seed knowledge_documents via the Gemini embedding API.",
    )
    args = parser.parse_args()
    try:
        asyncio.run(_seed(args.with_knowledge))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
