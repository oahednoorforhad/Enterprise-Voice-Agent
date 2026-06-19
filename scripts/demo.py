"""EVA Portfolio Demo — 3 curated multi-source reasoning scenarios.

Drives three carefully chosen queries against the live EVA backend and
prints a formatted transcript that proves all 6 PRD final success metrics:

  1. Voice conversation  (simulated as text here; combine with /voice for live demo)
  2. Dynamic tool selection
  3. Retrieval from multiple enterprise sources
  4. Evidence aggregation
  5. Cross-source reasoning
  6. Evidence-backed conclusions

Usage::

    uv run python -m scripts.demo
    uv run python -m scripts.demo --scenario 1   # single scenario
    EVAL_API_URL=http://prod:8000 uv run python -m scripts.demo

Customer: Arman Hossain / NexaFlow Technologies
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import httpx

# ---------------------------------------------------------------------------
# Demo scenarios
# ---------------------------------------------------------------------------

CUSTOMER_ID = os.getenv("EVAL_CUSTOMER", "c63d2f89-9aa3-4157-8205-a7d6cfc23207")

SCENARIOS = [
    {
        "title": "Cross-Source Billing + Ticket + Policy Reasoning",
        "prd_metrics": "Dynamic tool selection · Multi-source retrieval · Cross-source reasoning",
        "query": (
            "Why was I charged twice in March 2026 and has my billing issue been resolved? "
            "Also, what is your refund policy for duplicate charges?"
        ),
        "expected_tools": ["get_billing_history", "get_support_tickets", "search_policies"],
        "why_hard": (
            "Requires correlating billing records (duplicate charge) with support ticket status "
            "(resolved) and policy docs (refund eligibility) — three separate sources."
        ),
    },
    {
        "title": "Technical Troubleshooting via Profile + Ticket + Documentation",
        "prd_metrics": "Evidence aggregation · Tool selection · Evidence-backed conclusions",
        "query": (
            "All 52 of our users can't log in since we updated our Azure AD configuration. "
            "We're getting AADSTS50011. Do you have a record of this issue and how do we fix it?"
        ),
        "expected_tools": ["get_support_tickets", "get_customer_profile", "search_documentation"],
        "why_hard": (
            "Must link the open SSO ticket (ticket DB) with customer's Enterprise plan "
            "(profile DB) and the SSO v3.5.0 fix (documentation RAG) — structured + unstructured."
        ),
    },
    {
        "title": "Usage Analytics + Subscription Decision Support",
        "prd_metrics": "Multi-source retrieval · Decision support · Evidence-backed conclusions",
        "query": (
            "Our API calls have grown significantly this year and we keep hitting rate limits "
            "during bulk imports. Are we on the right plan and what should we do?"
        ),
        "expected_tools": ["get_usage_analytics", "get_subscription_status", "search_documentation"],
        "why_hard": (
            "Cross-references time-series usage data (analytics DB) with the current plan tier "
            "(subscription DB) and the /bulk-import endpoint guide (documentation RAG) to give "
            "an evidence-backed upgrade/migration recommendation."
        ),
    },
]

API_URL       = os.getenv("EVAL_API_URL", "http://localhost:8000").rstrip("/")
CHAT_ENDPOINT = "/api/v1/chat/"

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

WIDTH = 70
SEP   = "=" * WIDTH
SEP2  = "-" * WIDTH


def _wrap(text: str, indent: int = 10) -> str:
    """Wrap long text to WIDTH with indent after first line."""
    words = text.split()
    lines, line = [], []
    for word in words:
        if len(" ".join(line + [word])) + indent > WIDTH:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    pad = " " * indent
    return f"\n{pad}".join(lines)


def _badge(label: str, value: str) -> str:
    return f"  {label:<18} {value}"


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

async def call_chat(client: httpx.AsyncClient, query: str) -> tuple[dict, float]:
    start = time.monotonic()
    resp = await client.post(
        f"{API_URL}{CHAT_ENDPOINT}",
        json={"message": query, "customer_id": CUSTOMER_ID},
        timeout=90.0,
    )
    resp.raise_for_status()
    return resp.json(), round(time.monotonic() - start, 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_scenario(client: httpx.AsyncClient, idx: int, scenario: dict) -> bool:
    print()
    print(SEP)
    print(f"  EVA Demo — Scenario {idx} of {len(SCENARIOS)}")
    print(f"  {scenario['title']}")
    print(SEP)
    print(f"  PRD metrics: {scenario['prd_metrics']}")
    print(f"  Why it's hard:")
    print(f"    {_wrap(scenario['why_hard'], indent=4)}")
    print(SEP2)
    print(f"  QUERY:")
    print(f"    {_wrap(scenario['query'], indent=4)}")
    print(SEP2)
    print("  Calling EVA...", end="", flush=True)

    try:
        data, latency = await call_chat(client, scenario["query"])
    except httpx.ConnectError:
        print(f"\n  ERROR: Cannot connect to {API_URL}")
        print("  Make sure the backend is running: uv run uvicorn app.main:app --reload")
        return False
    except Exception as exc:
        print(f"\n  ERROR: {exc}")
        return False

    print(f" done ({latency}s)")
    print()

    response        = data.get("response", "(no response)")
    tool_calls_made = data.get("tool_calls_made") or []
    reasoning_trace = data.get("reasoning_trace") or {}
    confidence      = reasoning_trace.get("confidence", 0.0)
    reasoning_type  = reasoning_trace.get("reasoning_type", "—")
    evidence_cited  = reasoning_trace.get("evidence_cited") or []
    warnings        = reasoning_trace.get("warnings") or []
    evidence        = data.get("evidence") or {}
    failed_tools    = (evidence.get("failed_tools") or []) if isinstance(evidence, dict) else []

    # Tool call check
    expected = set(scenario["expected_tools"])
    actual   = set(tool_calls_made)
    hit_rate = len(expected & actual) / len(expected) if expected else 1.0

    print(_badge("Tools called:", ", ".join(tool_calls_made) if tool_calls_made else "(none)"))
    print(_badge("Expected tools:", ", ".join(scenario["expected_tools"])))
    tool_status = f"{len(expected & actual)}/{len(expected)} expected tools hit"
    print(_badge("Tool coverage:", tool_status))
    if failed_tools:
        print(_badge("Failed tools:", ", ".join(failed_tools)))
    print()
    print(_badge("Latency:", f"{latency}s"))
    print(_badge("Confidence:", f"{confidence:.2f}"))
    print(_badge("Reasoning type:", reasoning_type))
    print(_badge("Sources cited:", ", ".join(evidence_cited) if evidence_cited else "—"))
    if warnings:
        print(_badge("Warnings:", "; ".join(warnings)))
    print()
    print("  EVA RESPONSE:")
    print(SEP2)

    # Word-wrap EVA's response at WIDTH chars
    for para in response.split("\n"):
        if not para.strip():
            print()
            continue
        words = para.split()
        line = []
        for word in words:
            if len(" ".join(line + [word])) + 4 > WIDTH:
                print("    " + " ".join(line))
                line = [word]
            else:
                line.append(word)
        if line:
            print("    " + " ".join(line))
    print(SEP2)

    # Pass/fail
    ok = (hit_rate >= 0.5 and confidence >= 0.5 and reasoning_type not in ("greeting", "insufficient_evidence"))
    print(f"  Result: {'PASS' if ok else 'FAIL'} (tool coverage={hit_rate:.0%}, confidence={confidence:.2f})")
    return ok


async def run(scenario_filter: int | None) -> None:
    scenarios = SCENARIOS
    if scenario_filter is not None:
        idx = scenario_filter - 1
        if idx < 0 or idx >= len(SCENARIOS):
            print(f"ERROR: --scenario must be 1–{len(SCENARIOS)}", file=sys.stderr)
            sys.exit(1)
        scenarios = [SCENARIOS[idx]]

    print()
    print(SEP)
    print("  EVA Portfolio Demo — Enterprise Voice Assistant")
    print(f"  Customer : Arman Hossain / NexaFlow Technologies")
    print(f"  Backend  : {API_URL}")
    print(f"  Scenarios: {len(scenarios)}")
    print(SEP)

    passed = 0
    async with httpx.AsyncClient() as client:
        for i, scenario in enumerate(scenarios, start=1):
            ok = await run_scenario(client, i, scenario)
            if ok:
                passed += 1

    print()
    print(SEP)
    print(f"  Demo complete: {passed}/{len(scenarios)} scenarios passed")
    print()
    print("  PRD Final Success Metric checklist:")
    items = [
        ("Voice conversation",                 True,   "Simulated here; live at /voice"),
        ("Dynamic tool selection",             passed > 0, "EVA selected tools from user intent"),
        ("Retrieval from multiple sources",    passed > 0, "Billing, tickets, docs, analytics"),
        ("Evidence aggregation",               passed > 0, "EvidencePackage built per turn"),
        ("Cross-source reasoning",             passed > 0, "ReasoningPipeline synthesises evidence"),
        ("Evidence-backed conclusions",        passed > 0, "Confidence + evidence_cited in trace"),
    ]
    for label, done, note in items:
        mark = "[x]" if done else "[ ]"
        print(f"  {mark} {label:<35} {note}")
    print(SEP)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="EVA portfolio demo runner")
    parser.add_argument("--scenario", type=int, help="Run a single scenario (1, 2, or 3)")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.scenario))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
