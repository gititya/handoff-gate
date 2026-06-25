#!/usr/bin/env python3
"""Weekly roll-up — Phase 3.

Batches the gate over the B2C disputed-charge pack (Contract A) and reports
the two numbers a support lead actually wants: the handoff pass rate, and the
single gap the AI keeps dropping. A batch report over the gate — not a live
dashboard.

Usage:
    python rollup.py                 # all cases, grade-only (no MLX judge)
    python rollup.py --with-judge    # also run the local MLX judge per case
    python rollup.py --case call_x --case call_y   # subset
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import reconstruct, FIXTURE_BASE
from router import route
from agent import work_case
from contracts import check_handoff

OUTPUT_DIR = Path(__file__).parent / "outputs"


def all_case_ids() -> list[str]:
    return sorted(os.path.basename(p)[:-5] for p in glob.glob(str(FIXTURE_BASE / "*.json")))


def grade_case(case_id: str, with_judge: bool) -> dict[str, Any]:
    """Reconstruct → route → AI writes a thin handoff → grade it."""
    state = reconstruct(case_id)
    fixture = state["_fixture"]
    expected = fixture["expected_handoff"]["ai_to_human"]

    routing = route(fixture)
    candidate = work_case(fixture)["candidate_handoff"]
    report = check_handoff(candidate, expected, state)

    judge_pass = None
    if with_judge:
        from grade import grade_handoff
        verdict = grade_handoff(fixture["transcript_turns"], candidate, state).get("verdict")
        if verdict is not None:
            judge_pass = verdict.get("pass")

    return {
        "case_id": case_id,
        "resolution_type": fixture.get("resolution_type", ""),
        "contract": routing["contract"],
        "leniency": report.leniency.mode,
        "borderline": report.leniency.borderline,
        "passed": report.passed,
        "thin_but_silent": report.thin_but_silent,
        "missing_fields": report.missing_fields,
        "judge_pass": judge_pass,
    }


def run_rollup(case_ids: list[str], with_judge: bool) -> dict[str, Any]:
    t0 = time.time()
    rows: list[dict[str, Any]] = []

    print(f"\nRunning gate over {len(case_ids)} cases" + (" (with MLX judge)" if with_judge else "") + "...\n")
    for i, cid in enumerate(case_ids, 1):
        print(f"  [{i}/{len(case_ids)}] {cid} ...", end="", flush=True)
        row = grade_case(cid, with_judge)
        rows.append(row)
        flag = "PASS" if row["passed"] else f"BLOCK ({len(row['missing_fields'])} gaps)"
        print(f" {flag}")

    passed = sum(1 for r in rows if r["passed"])
    total = len(rows)
    gap_counts = Counter(f for r in rows for f in r["missing_fields"])
    top_gap = gap_counts.most_common(1)[0] if gap_counts else (None, 0)
    borderline = sum(1 for r in rows if r["borderline"])

    elapsed = time.time() - t0

    # --- report ---
    print("\n" + "=" * 64)
    print("  WEEKLY ROLL-UP — Handoff Quality Gate (Contract A, B2C)")
    print("=" * 64)
    print(f"\n  {'case':<18}{'resolution':<14}{'leniency':<12}{'result'}")
    print(f"  {'-'*16:<18}{'-'*12:<14}{'-'*10:<12}{'-'*20}")
    for r in rows:
        result = "PASS" if r["passed"] else f"BLOCK · {len(r['missing_fields'])} gaps"
        bl = " [borderline]" if r["borderline"] else ""
        print(f"  {r['case_id']:<18}{r['resolution_type']:<14}{r['leniency']:<12}{result}{bl}")

    print(f"\n  Pass rate:        {passed}/{total} ({100*passed//total if total else 0}%)")
    print(f"  Borderline:       {borderline}/{total} (lenient + flagged for human review)")
    if top_gap[0]:
        print(f"  Top recurring gap: '{top_gap[0]}' — missing in {top_gap[1]}/{total} handoffs")
    if len(gap_counts) > 1:
        runners = ", ".join(f"{f} ({n})" for f, n in gap_counts.most_common()[1:4])
        print(f"  Other gaps:        {runners}")
    print(f"\n  Total time: {elapsed:.1f}s")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contract": "A",
        "cases": total,
        "pass_rate": round(passed / total, 3) if total else 0,
        "passed": passed,
        "borderline": borderline,
        "top_recurring_gap": {"field": top_gap[0], "count": top_gap[1]},
        "gap_counts": dict(gap_counts),
        "rows": rows,
        "with_judge": with_judge,
        "elapsed_seconds": round(elapsed, 1),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"rollup_{ts}.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"  Saved: {out_path.name}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Handoff Quality Gate — weekly roll-up")
    parser.add_argument("--case", action="append", dest="cases", help="case ID (repeatable; default: all)")
    parser.add_argument("--with-judge", action="store_true", help="also run the local MLX judge per case (slower)")
    args = parser.parse_args()

    case_ids = args.cases or all_case_ids()
    run_rollup(case_ids, with_judge=args.with_judge)


if __name__ == "__main__":
    main()
