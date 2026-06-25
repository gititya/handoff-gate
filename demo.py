#!/usr/bin/env python3
"""Handoff Quality Gate — Hero Demo.

Orchestrates one B2C disputed-charge case end-to-end:
1. Replay fixture → authoritative reconstruction (free, deterministic)
2. Route → Contract A
3. Live Claude writes a thin handoff note
4. Local MLX judge grades it (free)
5. Gate: if incomplete → BLOCK, name gaps, write corrected note, release
6. Print side-by-side thin vs corrected handoff

Usage:
    python demo.py                              # default hero case
    python demo.py --case call_3835c4f220       # fraud contrast case
    python demo.py --skip-judge                 # skip local MLX judge (faster)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine import reconstruct
from router import route
from agent import work_case
from contracts import derive_leniency
from gate import run_gate

OUTPUT_DIR = Path(__file__).parent / "outputs"

HERO_CASE = "call_61772f4783"


def format_handoff(handoff: dict[str, Any], label: str) -> str:
    lines = [f"{'─' * 60}", f"  {label}", f"{'─' * 60}"]
    for key, val in handoff.items():
        if key.startswith("_"):
            continue
        if isinstance(val, (list, dict)):
            val_str = json.dumps(val, indent=4)
            lines.append(f"  {key}:")
            for vl in val_str.split("\n"):
                lines.append(f"    {vl}")
        else:
            lines.append(f"  {key}: {val}")
    lines.append(f"{'─' * 60}")
    return "\n".join(lines)


def run_demo(case_id: str, skip_judge: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"case_id": case_id, "timestamp": datetime.now(timezone.utc).isoformat()}
    t0 = time.time()

    # Step 1: Reconstruct
    print(f"\n[1/5] Reconstructing case {case_id}...")
    state = reconstruct(case_id)
    fixture = state["_fixture"]
    expected_handoff = fixture["expected_handoff"]["ai_to_human"]
    leniency = derive_leniency(state)

    print(f"      final_cause: {state['final_cause'] or '(none)'}")
    print(f"      evidence_seen: {state['root_cause_evidence_seen']}")
    print(f"      leniency: {leniency.mode}" + (" [BORDERLINE]" if leniency.borderline else ""))
    result["reconstruction"] = {
        "final_cause": state["final_cause"],
        "root_cause_evidence_seen": state["root_cause_evidence_seen"],
        "leniency": leniency.mode,
        "borderline": leniency.borderline,
        "facts": state["facts"],
        "candidate_branches": state["candidate_branches"],
        "ruled_out_branches": state["ruled_out_branches"],
    }

    # Step 2: Route
    print(f"\n[2/5] Routing...")
    routing = route(fixture)
    print(f"      destination: {routing['destination']} | contract: {routing['contract']}")
    result["routing"] = routing

    # Step 3: AI works the case
    print(f"\n[3/5] AI working the case (live Claude call)...")
    agent_result = work_case(fixture)
    candidate = agent_result["candidate_handoff"]
    if candidate.get("_parse_error"):
        print("      WARNING: Could not parse AI handoff as JSON")
        print(f"      Raw: {agent_result['raw_response'][:200]}...")
    else:
        field_count = len([k for k in candidate if not k.startswith("_")])
        print(f"      AI produced handoff with {field_count} fields")
    result["agent"] = agent_result

    # Step 4: Grade (optional — local MLX can be slow)
    judge_verdict = None
    if not skip_judge:
        print(f"\n[4/5] Grading handoff (local MLX judge)...")
        try:
            from grade import grade_handoff
            grade_result = grade_handoff(
                fixture["transcript_turns"], candidate, state
            )
            judge_verdict = grade_result.get("verdict")
            if judge_verdict:
                print(f"      judge pass: {judge_verdict.get('pass')}")
                if judge_verdict.get("missing_requirement"):
                    print(f"      missing: {judge_verdict['missing_requirement']}")
                if judge_verdict.get("evidence_gap"):
                    print(f"      evidence gap: {judge_verdict['evidence_gap']}")
            result["judge"] = grade_result
        except Exception as e:
            print(f"      Judge failed: {e}")
            print(f"      Continuing without judge verdict...")
            result["judge_error"] = str(e)
    else:
        print(f"\n[4/5] Skipping judge (--skip-judge)")

    # Step 5: Gate
    print(f"\n[5/5] Running gate...")
    package = run_gate(
        case_id, candidate, expected_handoff, state, judge_verdict
    )

    if package.blocked:
        print(f"\n  ╔══════════════════════════════════════════╗")
        print(f"  ║  BLOCKED — handoff intercepted and held  ║")
        print(f"  ╚══════════════════════════════════════════╝")
        gap = package.gap_report
        if gap:
            if gap.missing_always:
                print(f"\n  Always-required missing: {gap.missing_always}")
            if gap.missing_other:
                print(f"  Other missing fields:    {gap.missing_other}")
            if gap.thin_but_silent:
                print(f"  Thin-and-silent:         cause/confidence omitted entirely")
            print(f"  Leniency:                {gap.leniency.mode}" +
                  (" [BORDERLINE]" if gap.leniency.borderline else ""))
            if gap.leniency.reason:
                print(f"  Reason:                  {gap.leniency.reason}")

        print(f"\n  Generating corrected handoff note...")
        print(format_handoff(candidate, "ORIGINAL (thin) handoff"))
        print()
        if package.corrected and not package.corrected.get("_parse_error"):
            print(format_handoff(package.corrected, "CORRECTED handoff"))
        elif package.corrected:
            print(f"  [Corrected note parse error — raw below]")
            print(f"  {package.corrected.get('_raw', '')[:500]}")
    else:
        print(f"\n  ✓ PASSED — handoff released to co-pilot")

    if package.released:
        print(f"\n  → Handoff RELEASED (final version)")
    else:
        print(f"\n  ✗ Handoff NOT released")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s")
    result["gate"] = {
        "blocked": package.blocked,
        "released": package.released,
        "missing_fields": package.gap_report.missing_fields if package.gap_report else [],
        "thin_but_silent": package.gap_report.thin_but_silent if package.gap_report else False,
        "corrected": package.corrected is not None,
    }
    result["elapsed_seconds"] = round(elapsed, 1)

    # Save run
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"{case_id}_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  Run saved: {out_path.name}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Handoff Quality Gate — Hero Demo")
    parser.add_argument("--case", default=HERO_CASE, help=f"Case ID (default: {HERO_CASE})")
    parser.add_argument("--skip-judge", action="store_true", help="Skip local MLX judge (faster)")
    args = parser.parse_args()

    print("=" * 60)
    print("  HANDOFF QUALITY GATE — HERO DEMO")
    print("=" * 60)

    run_demo(args.case, skip_judge=args.skip_judge)


if __name__ == "__main__":
    main()
