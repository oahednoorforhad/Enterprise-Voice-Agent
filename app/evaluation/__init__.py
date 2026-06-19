"""Evaluation scoring utilities for the EVA evaluation harness.

Four pure functions — no DB or API dependencies — that score a single
scenario response against its expected values from scenarios.yaml.

Metrics (all return float 0.0–1.0):
  score_retrieval     — did EVA call the right tools?
  score_reasoning     — does the answer contain expected keywords?
  score_hallucination — are forbidden phrases absent?
  score_quality       — is confidence high enough and reasoning_type correct?
"""

from __future__ import annotations


def score_retrieval(expected_tools: list[str], actual_tools: list[str]) -> float:
    """Recall: fraction of expected tools that were actually called.

    Examples
    --------
    >>> score_retrieval(["get_billing_history"], ["get_billing_history", "search_policies"])
    1.0
    >>> score_retrieval(["get_billing_history", "get_support_tickets"], ["get_billing_history"])
    0.5
    >>> score_retrieval([], [])
    1.0
    """
    if not expected_tools:
        return 1.0
    actual_set = set(actual_tools)
    hit = sum(1 for t in expected_tools if t in actual_set)
    return hit / len(expected_tools)


def score_reasoning(answer_must_contain: list[str], response: str) -> float:
    """Keyword presence: 1.0 if ANY expected keyword appears (case-insensitive).

    An empty keyword list scores 1.0 (nothing required).

    Examples
    --------
    >>> score_reasoning(["duplicate", "credit"], "We found a duplicate charge.")
    1.0
    >>> score_reasoning(["refund"], "A credit was applied.")
    0.0
    """
    if not answer_must_contain:
        return 1.0
    lower = response.lower()
    return 1.0 if any(kw.lower() in lower for kw in answer_must_contain) else 0.0


def score_hallucination(answer_must_not_contain: list[str], response: str) -> float:
    """Absence check: 1.0 if NONE of the forbidden phrases appear (case-insensitive).

    An empty forbidden list scores 1.0.

    Examples
    --------
    >>> score_hallucination(["cash refund"], "A credit was applied to April.")
    1.0
    >>> score_hallucination(["cash refund"], "We issued a cash refund immediately.")
    0.0
    """
    if not answer_must_not_contain:
        return 1.0
    lower = response.lower()
    return 0.0 if any(phrase.lower() in lower for phrase in answer_must_not_contain) else 1.0


def score_quality(
    confidence: float,
    reasoning_type: str,
    min_confidence: float,
    expected_reasoning_type: str,
) -> float:
    """Mean of two sub-scores:
    - 1.0 if actual confidence >= min_confidence, else 0.0
    - 1.0 if reasoning_type matches expected, else 0.0

    Examples
    --------
    >>> score_quality(0.85, "root_cause_analysis", 0.7, "root_cause_analysis")
    1.0
    >>> score_quality(0.5, "root_cause_analysis", 0.7, "root_cause_analysis")
    0.5
    >>> score_quality(0.85, "greeting", 0.7, "root_cause_analysis")
    0.5
    """
    confidence_ok = 1.0 if confidence >= min_confidence else 0.0
    type_ok = 1.0 if reasoning_type == expected_reasoning_type else 0.0
    return (confidence_ok + type_ok) / 2.0


def score_scenario(
    scenario: dict,
    response: str,
    tool_calls_made: list[str],
    confidence: float,
    reasoning_type: str,
) -> dict[str, float]:
    """Score all 4 metrics for one scenario and return a dict.

    Parameters
    ----------
    scenario        : one entry from scenarios.yaml (already parsed)
    response        : EVA's text response
    tool_calls_made : list of tool names executed
    confidence      : reasoning_trace.confidence (0.0–1.0)
    reasoning_type  : reasoning_trace.reasoning_type string
    """
    return {
        "retrieval": score_retrieval(
            scenario.get("expected_tools", []),
            tool_calls_made,
        ),
        "reasoning": score_reasoning(
            scenario.get("answer_must_contain", []),
            response,
        ),
        "hallucination": score_hallucination(
            scenario.get("answer_must_not_contain", []),
            response,
        ),
        "quality": score_quality(
            confidence,
            reasoning_type,
            scenario.get("min_confidence", 0.7),
            scenario.get("expected_reasoning_type", ""),
        ),
    }
