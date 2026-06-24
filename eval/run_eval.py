"""
SHRED TECH — LLM-as-a-Judge evaluation harness.

Usage:
    python -m eval.run_eval              # run full suite
    python -m eval.run_eval --delay 10   # custom seconds between cases (default 8)
    python -m eval.run_eval --ids setup-01 trouble-elec-02  # run specific cases

A case FAILS if:
  - any dimension score ≤ 2
  - actual specialist ≠ expected specialist
    (exception: 'ambiguous' category passes if the coordinator responded directly)
"""

import argparse
import asyncio
import io
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

# Force UTF-8 stdout so Unicode characters work on Windows terminals
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to path so agent/ and eval/ are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent.runner_utils import run_query
from eval.judge import judge_response
from eval.test_set import TEST_CASES

PASS_THRESHOLD = 2  # score must be ABOVE this to pass


def routing_correct(expected: str, actual: str, category: str) -> bool:
    if category == "ambiguous":
        # Coordinator asking a clarifying question (author == coordinator name) is correct.
        # A direct specialist transfer on an ambiguous query is a routing miss.
        return actual == "shred_tech"
    return actual == expected


def is_pass(scores: dict, expected: str, actual: str, category: str) -> bool:
    dims_ok = all(scores[d] > PASS_THRESHOLD for d in ("accuracy", "tone", "safety"))
    route_ok = routing_correct(expected, actual, category)
    return dims_ok and route_ok


async def run_case(case: dict) -> dict:
    """Run one test case through the agent and judge. Returns a result dict."""
    query = case["query"]
    expected = case["expected_specialist"]
    category = case["category"]

    try:
        response_text, actual_specialist = await run_query(
            message=query, user_id="eval"
        )
    except Exception as e:
        err = str(e)[:120]
        return {
            "id": case["id"],
            "category": category,
            "query": query,
            "expected_specialist": expected,
            "actual_specialist": "error",
            "routing_correct": False,
            "scores": {"accuracy": 0, "tone": 0, "safety": 0, "reasoning": f"Agent error: {err}"},
            "passed": False,
            "response_preview": "",
            "error": err,
        }

    if not response_text:
        scores = {
            "accuracy": 1,
            "tone": 1,
            "safety": 1,
            "reasoning": "No response returned from agent.",
        }
    else:
        try:
            scores = judge_response(
                query=query,
                response=response_text,
                specialist=actual_specialist,
                category=category,
            )
        except Exception as e:
            scores = {
                "accuracy": 1,
                "tone": 1,
                "safety": 1,
                "reasoning": f"Judge error: {str(e)[:80]}",
            }

    passed = is_pass(scores, expected, actual_specialist, category)
    route_ok = routing_correct(expected, actual_specialist, category)

    return {
        "id": case["id"],
        "category": category,
        "query": query,
        "expected_specialist": expected,
        "actual_specialist": actual_specialist,
        "routing_correct": route_ok,
        "scores": scores,
        "passed": passed,
        "response_preview": response_text[:200] if response_text else "",
    }


def print_result(result: dict) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    s = result["scores"]
    route_arrow = (
        result["actual_specialist"]
        if result["routing_correct"]
        else f"{result['actual_specialist']} != {result['expected_specialist']}"
    )
    print(
        f"[{status}] {result['id']:20s} | {route_arrow:30s} | "
        f"acc={s['accuracy']} tone={s['tone']} safety={s['safety']} | "
        f"{s['reasoning'][:80]}"
    )


def compute_aggregates(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    routing_hits = sum(1 for r in results if r["routing_correct"])

    dim_sums = defaultdict(float)
    cat_sums = defaultdict(lambda: defaultdict(float))
    cat_counts = defaultdict(int)

    for r in results:
        for d in ("accuracy", "tone", "safety"):
            dim_sums[d] += r["scores"][d]
            cat_sums[r["category"]][d] += r["scores"][d]
        cat_counts[r["category"]] += 1

    avg_dims = {d: round(dim_sums[d] / total, 2) for d in ("accuracy", "tone", "safety")}

    avg_by_category = {}
    for cat, counts in cat_counts.items():
        avg_by_category[cat] = {
            d: round(cat_sums[cat][d] / counts, 2) for d in ("accuracy", "tone", "safety")
        }
        avg_by_category[cat]["n"] = counts

    return {
        "total_cases": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate_pct": round(passed / total * 100, 1),
        "routing_accuracy_pct": round(routing_hits / total * 100, 1),
        "avg_scores": avg_dims,
        "avg_scores_by_category": avg_by_category,
    }


def print_aggregates(agg: dict) -> None:
    print("\n" + "=" * 80)
    print("AGGREGATE RESULTS")
    print("=" * 80)
    print(f"  Total cases   : {agg['total_cases']}")
    print(f"  Passed        : {agg['passed']}  ({agg['pass_rate_pct']}%)")
    print(f"  Failed        : {agg['failed']}")
    print(f"  Routing acc.  : {agg['routing_accuracy_pct']}%")
    print()
    a = agg["avg_scores"]
    print(f"  Avg accuracy  : {a['accuracy']}/5")
    print(f"  Avg tone      : {a['tone']}/5")
    print(f"  Avg safety    : {a['safety']}/5")
    print()
    print("  By category:")
    for cat, stats in agg["avg_scores_by_category"].items():
        print(
            f"    {cat:30s} (n={stats['n']})  "
            f"acc={stats['accuracy']} tone={stats['tone']} safety={stats['safety']}"
        )
    print("=" * 80)


def save_scorecard(results: list[dict], agg: dict) -> str:
    os.makedirs(
        os.path.join(os.path.dirname(__file__), "results"), exist_ok=True
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(
        os.path.dirname(__file__), "results", f"scorecard_{timestamp}.json"
    )
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": timestamp, "aggregate": agg, "results": results},
            f,
            indent=2,
            ensure_ascii=False,
        )
    return filename


async def main(case_ids: list[str] | None, delay: int) -> None:
    cases = TEST_CASES
    if case_ids:
        cases = [c for c in cases if c["id"] in case_ids]
        if not cases:
            print(f"No cases matched ids: {case_ids}")
            sys.exit(1)

    print(f"\nSHRED TECH eval harness — {len(cases)} case(s), {delay}s delay between cases\n")
    print(
        f"{'STATUS':<7} {'ID':<22} {'ROUTING':<32} "
        f"{'ACC':<4} {'TONE':<5} {'SAFE':<5} REASONING"
    )
    print("-" * 120)

    results = []
    for i, case in enumerate(cases):
        if i > 0:
            time.sleep(delay)

        print(f"  running {case['id']} ...", end="\r", flush=True)
        result = await run_case(case)
        results.append(result)
        print_result(result)

    agg = compute_aggregates(results)
    print_aggregates(agg)

    path = save_scorecard(results, agg)
    print(f"\nFull scorecard saved to: {path}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SHRED TECH eval harness")
    parser.add_argument(
        "--delay",
        type=int,
        default=8,
        help="Seconds to sleep between test cases (default 8, manages free-tier RPM)",
    )
    parser.add_argument(
        "--ids",
        nargs="*",
        help="Run only specific case ids (e.g. --ids setup-01 gear-02)",
    )
    args = parser.parse_args()
    asyncio.run(main(case_ids=args.ids, delay=args.delay))
