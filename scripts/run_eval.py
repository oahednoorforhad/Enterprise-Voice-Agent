"""EVA Evaluation Runner.

Loads data/eval/scenarios.yaml, sends each scenario to the live chat API,
scores responses on 4 PRD metrics, and writes a results JSON file.

Usage::

    uv run python -m scripts.run_eval                      # all 50 scenarios
    uv run python -m scripts.run_eval --category billing   # one category
    uv run python -m scripts.run_eval --dry-run            # validate YAML only
    uv run python -m scripts.run_eval --concurrency 5      # parallel requests

Environment::

    EVAL_API_URL   backend base URL (default: http://localhost:8000)
    EVAL_CUSTOMER  customer UUID  (default: c63d2f89-9aa3-4157-8205-a7d6cfc23207)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

from app.evaluation import score_scenario

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCENARIOS_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "scenarios.yaml"
RESULTS_DIR    = Path(__file__).resolve().parent.parent / "data" / "eval"

DEFAULT_API_URL    = "http://localhost:8000"
DEFAULT_CUSTOMER   = "c63d2f89-9aa3-4157-8205-a7d6cfc23207"
CHAT_ENDPOINT      = "/api/v1/chat/"

CATEGORIES = ["billing", "subscription", "refund_requests", "product_problems", "account_access"]

# ---------------------------------------------------------------------------
# YAML loading & validation
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {"id", "category", "query", "expected_tools",
                   "answer_must_contain", "answer_must_not_contain",
                   "min_confidence", "expected_reasoning_type"}


def load_scenarios(category: str | None = None) -> list[dict]:
    if not SCENARIOS_PATH.exists():
        print(f"ERROR: scenarios file not found: {SCENARIOS_PATH}", file=sys.stderr)
        sys.exit(1)

    with SCENARIOS_PATH.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, list):
        print("ERROR: scenarios.yaml must be a YAML list", file=sys.stderr)
        sys.exit(1)

    errors = []
    for s in raw:
        missing = REQUIRED_FIELDS - set(s.keys())
        if missing:
            errors.append(f"  {s.get('id', '?')} missing fields: {missing}")

    if errors:
        print("Schema errors in scenarios.yaml:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)

    if category:
        raw = [s for s in raw if s["category"] == category]

    return raw


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

async def call_chat(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    scenario: dict,
    api_url: str,
    customer_id: str,
    delay: float = 0.0,
) -> dict:
    payload = {"message": scenario["query"], "customer_id": customer_id}
    start = time.monotonic()

    async with sem:
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            resp = await client.post(
                f"{api_url}{CHAT_ENDPOINT}",
                json=payload,
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return {
                "id": scenario["id"],
                "category": scenario["category"],
                "query": scenario["query"],
                "error": str(exc),
                "latency_s": round(time.monotonic() - start, 2),
                "passed": False,
                "scores": {"retrieval": 0.0, "reasoning": 0.0, "hallucination": 0.0, "quality": 0.0},
            }

    latency = round(time.monotonic() - start, 2)

    response_text    = data.get("response", "")
    tool_calls_made  = data.get("tool_calls_made") or []
    reasoning_trace  = data.get("reasoning_trace") or {}
    confidence       = float(reasoning_trace.get("confidence", 0.0))
    reasoning_type   = reasoning_trace.get("reasoning_type", "")

    scores = score_scenario(
        scenario=scenario,
        response=response_text,
        tool_calls_made=tool_calls_made,
        confidence=confidence,
        reasoning_type=reasoning_type,
    )

    passed = all([
        scores["retrieval"] >= 0.5,
        scores["reasoning"] >= 1.0,
        scores["hallucination"] >= 1.0,
        scores["quality"] >= 0.5,
    ])

    return {
        "id": scenario["id"],
        "category": scenario["category"],
        "query": scenario["query"],
        "response": response_text,
        "tool_calls_made": tool_calls_made,
        "confidence": confidence,
        "reasoning_type": reasoning_type,
        "latency_s": latency,
        "passed": passed,
        "scores": scores,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def aggregate(results: list[dict]) -> dict:
    ok = [r for r in results if "error" not in r]

    overall = {
        metric: _mean([r["scores"][metric] for r in ok])
        for metric in ("retrieval", "reasoning", "hallucination", "quality")
    }
    overall["pass_rate"] = _mean([1.0 if r["passed"] else 0.0 for r in results])

    by_category: dict[str, dict] = {}
    for cat in CATEGORIES:
        cat_rows = [r for r in ok if r["category"] == cat]
        if not cat_rows:
            continue
        by_category[cat] = {
            metric: _mean([r["scores"][metric] for r in cat_rows])
            for metric in ("retrieval", "reasoning", "hallucination", "quality")
        }
        by_category[cat]["count"] = len(cat_rows)
        by_category[cat]["pass_rate"] = _mean(
            [1.0 if r["passed"] else 0.0 for r in cat_rows]
        )

    return {"overall": overall, "by_category": by_category}


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

COL = 20
SEP = "-" * 85


def _pct(v: float) -> str:
    return f"{v * 100:5.1f}%"


def print_summary(agg: dict, total: int, errors: int, error_details: list[dict]) -> None:
    header = f"{'Category':<{COL}}  {'Retrieval':>10}  {'Reasoning':>10}  {'No-Halluc':>10}  {'Quality':>10}  {'Pass':>7}  {'N':>4}"
    print()
    print("EVA Evaluation Results")
    print(SEP)
    print(header)
    print(SEP)
    for cat, m in agg["by_category"].items():
        print(
            f"{cat:<{COL}}  "
            f"{_pct(m['retrieval']):>10}  "
            f"{_pct(m['reasoning']):>10}  "
            f"{_pct(m['hallucination']):>10}  "
            f"{_pct(m['quality']):>10}  "
            f"{_pct(m['pass_rate']):>7}  "
            f"{m['count']:>4}"
        )
    print(SEP)
    ov = agg["overall"]
    print(
        f"{'OVERALL':<{COL}}  "
        f"{_pct(ov['retrieval']):>10}  "
        f"{_pct(ov['reasoning']):>10}  "
        f"{_pct(ov['hallucination']):>10}  "
        f"{_pct(ov['quality']):>10}  "
        f"{_pct(ov['pass_rate']):>7}  "
        f"{total:>4}"
    )
    print(SEP)
    if errors:
        print(f"  {errors} scenario(s) errored (excluded from metric averages):")
        for r in error_details:
            print(f"    {r['id']}: {r.get('error', '?')[:120]}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    scenarios = load_scenarios(args.category or None)

    if args.dry_run:
        by_cat = {c: sum(1 for s in scenarios if s["category"] == c) for c in CATEGORIES}
        print(f"Dry run: {len(scenarios)} scenarios loaded across {len([v for v in by_cat.values() if v])} categories. 0 schema errors.")
        for cat, n in by_cat.items():
            if n:
                print(f"  {cat}: {n}")
        return

    api_url     = os.getenv("EVAL_API_URL", DEFAULT_API_URL).rstrip("/")
    customer_id = os.getenv("EVAL_CUSTOMER", DEFAULT_CUSTOMER)

    print(f"Running {len(scenarios)} scenario(s) against {api_url} ...")
    print(f"Customer   : {customer_id}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Delay      : {args.delay}s between requests")
    est = len(scenarios) * (args.delay + 8)
    print(f"Est. time  : ~{int(est)}s ({int(est/60)}m {int(est%60)}s)")
    print()

    sem = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient() as client:
        tasks = [
            call_chat(client, sem, s, api_url, customer_id, delay=args.delay)
            for s in scenarios
        ]
        results = []
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            r = await coro
            if "error" in r:
                status = "ERR "
                detail = f"  <- {r['error'][:80]}"
            elif r.get("passed"):
                status = "PASS"
                detail = ""
            else:
                status = "FAIL"
                detail = ""
            print(f"  [{i:3}/{len(scenarios)}] {r['id']:<10} {status}  latency={r.get('latency_s', 0):.1f}s{detail}")
            results.append(r)

    error_details = [r for r in results if "error" in r]
    errors = len(error_details)
    agg    = aggregate(results)

    print_summary(agg, len(results), errors, error_details)

    # Save results
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    out_path = RESULTS_DIR / f"results_{ts}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": ts,
        "total": len(results),
        "errors": errors,
        "customer_id": customer_id,
        "category_filter": args.category,
        "metrics": agg,
        "scenarios": results,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Results saved -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="EVA evaluation runner")
    parser.add_argument("--category", choices=CATEGORIES, help="Run one category only")
    parser.add_argument("--dry-run", action="store_true", help="Validate YAML, no API calls")
    parser.add_argument("--concurrency", type=int, default=1, help="Parallel requests (default 1)")
    parser.add_argument("--delay", type=float, default=5.0, help="Seconds to wait between requests to avoid Gemini rate limits (default 5)")
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
