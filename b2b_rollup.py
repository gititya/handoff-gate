#!/usr/bin/env python3
"""Flow 2 live roll-up — human → engineering handoffs.

Batches Contract B over the B2B anchor set. The anchors provide the support
case material and expected evidence; the live agent writes the engineering
handoff, and the deterministic gate grades the generated note.

Usage:
    python b2b_rollup.py
    python b2b_rollup.py --case level2_tool_access_limitation
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agent import work_engineering_handoff
from contracts import check_handoff_b
from gate import support_outcome
from rollup import support_gap_label

ANCHOR_DIR = Path(__file__).parent / "contract_b_anchors"
OUTPUT_DIR = Path(__file__).parent / "outputs"
PROFILE_CASES = {
    "hostile": [
        ("level2_tool_access_limitation", "evidence_starved"),
        ("level3_misrouted_ratelimit_actually_webhook_auth", "distractor_wrong_cause"),
        ("level2_unresolved_workspace_handoff", "cold_dump"),
    ]
}
DISTRACTOR_CAUSES = {
    "level3_misrouted_ratelimit_actually_webhook_auth": "quota_exhaustion",
}
SUPPORTED_PROFILES = {
    "clean",
    "evidence_starved",
    "distractor_wrong_cause",
    "cold_dump",
    "hostile",
}


def all_anchor_ids() -> list[str]:
    return sorted(path.stem for path in ANCHOR_DIR.glob("*.json"))


def load_anchor(case_id: str) -> dict[str, Any]:
    return json.loads((ANCHOR_DIR / f"{case_id}.json").read_text())


def build_state(anchor: dict[str, Any]) -> dict[str, Any]:
    handoff = anchor["expected_handoff"]["human_to_engineering"]
    strict = anchor.get("leniency_arm") == "strict"
    final_cause = ""
    if strict:
        final_cause = handoff.get("likely_cause", "").split("—", 1)[0].strip()

    return {
        "case_id": anchor["case_id"],
        "facts": handoff.get("evidence_handles", []),
        "unknowns": handoff.get("open_unknowns", []),
        "candidate_branches": handoff.get("open_unknowns", []),
        "ruled_out_branches": handoff.get("support_ruled_out", []),
        "next_check": handoff.get("specific_ask", ""),
        "handoff_notes": [],
        "final_cause": final_cause,
        "root_cause_evidence_seen": strict,
    }


def build_transcript_turns(anchor: dict[str, Any], profile: str = "clean") -> list[dict[str, str]]:
    handoff = anchor["expected_handoff"]["human_to_engineering"]
    support_reality = anchor.get("support_reality", "support escalation")
    open_unknowns = handoff.get("open_unknowns", [])
    open_text = ", ".join(open_unknowns) if open_unknowns else "none"

    if profile == "evidence_starved":
        return [
            {
                "speaker": "customer",
                "text": (
                    "The workflow is stuck and this is blocking our business process. "
                    f"Impact: {handoff.get('impact_urgency', 'not stated')}"
                ),
            },
            {
                "speaker": "support",
                "text": (
                    f"Support reality: {support_reality}. Affected scope: "
                    f"{handoff.get('affected_scope', 'unknown')}"
                ),
            },
            {
                "speaker": "support",
                "text": (
                    "Support cannot access the deeper engineering tool needed to verify "
                    "the backend mechanism. Escalate with only the customer symptom and "
                    "business impact."
                ),
            },
        ]

    if profile == "distractor_wrong_cause":
        wrong_cause = DISTRACTOR_CAUSES.get(anchor["case_id"], "quota_exhaustion")
        return [
            {
                "speaker": "customer",
                "text": (
                    "After scaling up, webhooks are failing and it looks like we are "
                    "being rate limited."
                ),
            },
            {
                "speaker": "support",
                "text": (
                    f"Initial working theory is {wrong_cause}. The customer recently "
                    "upgraded usage, so quota pressure looks plausible."
                ),
            },
            {
                "speaker": "system",
                "text": "Partial dashboard context is available, but deeper webhook auth logs are not in the support view.",
            },
            {
                "speaker": "support",
                "text": "Escalate to engineering to confirm the suspected quota/rate-limit path.",
            },
        ]

    if profile == "cold_dump":
        return [
            {
                "speaker": "customer",
                "text": (
                    "Several users cannot get into the workspace after migration. "
                    "This is urgent and we need engineering to look now."
                ),
            },
            {
                "speaker": "support",
                "text": (
                    "No diagnosis is ready yet. We do not have enough system detail in "
                    "the handoff notes, but the customer is asking for escalation."
                ),
            },
        ]

    return [
        {
            "speaker": "customer",
            "text": (
                f"We need help with this product issue. Impact: "
                f"{handoff.get('impact_urgency', 'not stated')}"
            ),
        },
        {
            "speaker": "support",
            "text": (
                f"Support reality: {support_reality}. Affected scope: "
                f"{handoff.get('affected_scope', 'unknown')}"
            ),
        },
        {
            "speaker": "system",
            "text": (
                f"System discrepancy: {handoff.get('system_discrepancy', '')}. "
                f"Evidence handles: {', '.join(handoff.get('evidence_handles', []))}."
            ),
        },
        {
            "speaker": "support",
            "text": (
                f"Ruled out: {', '.join(handoff.get('support_ruled_out', []))}. "
                f"Still open: {open_text}."
            ),
        },
        {
            "speaker": "support",
            "text": f"Engineering ask: {handoff.get('specific_ask', '')}",
        },
    ]


def build_agent_state(anchor: dict[str, Any], profile: str = "clean") -> dict[str, Any]:
    if profile == "clean":
        return build_state(anchor)

    if profile == "evidence_starved":
        handoff = anchor["expected_handoff"]["human_to_engineering"]
        return {
            "case_id": anchor["case_id"],
            "facts": [handoff.get("affected_scope", "")],
            "unknowns": ["backend mechanism not visible to support"],
            "candidate_branches": [],
            "ruled_out_branches": [],
            "next_check": "Engineering needs to inspect backend tools support cannot access.",
            "handoff_notes": [],
            "final_cause": "",
            "root_cause_evidence_seen": False,
        }

    if profile == "distractor_wrong_cause":
        wrong_cause = DISTRACTOR_CAUSES.get(anchor["case_id"], "quota_exhaustion")
        return {
            "case_id": anchor["case_id"],
            "facts": ["customer recently scaled usage", "webhooks are failing"],
            "unknowns": ["exact backend failure mode"],
            "candidate_branches": [wrong_cause],
            "ruled_out_branches": [],
            "next_check": f"Confirm whether {wrong_cause} is the cause.",
            "handoff_notes": [],
            "final_cause": wrong_cause,
            "root_cause_evidence_seen": True,
        }

    if profile == "cold_dump":
        return {
            "case_id": anchor["case_id"],
            "facts": ["customer reports urgent access failure"],
            "unknowns": ["scope", "evidence", "ruled out branches", "open branches"],
            "candidate_branches": [],
            "ruled_out_branches": [],
            "next_check": "",
            "handoff_notes": [],
            "final_cause": "",
            "root_cause_evidence_seen": False,
        }

    raise ValueError(f"Unsupported profile: {profile}")


def grade_anchor(
    case_id: str,
    handoff_fn: Callable[[list[dict[str, Any]], dict[str, Any]], dict[str, Any]] = work_engineering_handoff,
    profile: str = "clean",
) -> dict[str, Any]:
    anchor = load_anchor(case_id)
    expected = anchor["expected_handoff"]["human_to_engineering"]
    gate_state = build_state(anchor)
    agent_state = build_agent_state(anchor, profile=profile)
    transcript_turns = build_transcript_turns(anchor, profile=profile)
    agent_result = handoff_fn(transcript_turns, agent_state)
    candidate = agent_result["candidate_handoff"]
    report = check_handoff_b(candidate, expected, gate_state)
    outcome = support_outcome(
        released=report.passed,
        human_review_flag=report.structure_warning,
        blocked=not report.passed,
    )
    support_gaps = [support_gap_label(field) for field in report.missing_fields]
    if report.thin_but_silent:
        support_gaps.append("open branches not named")

    return {
        "case_id": case_id,
        "contract": "B",
        "flow": "human_to_engineering",
        "profile": profile,
        "support_reality": anchor.get("support_reality", "original_anchor"),
        "leniency": report.leniency.mode,
        "borderline": report.leniency.borderline,
        "passed": report.passed,
        "outcome": outcome,
        "thin_but_silent": report.thin_but_silent,
        "structure_warning": report.structure_warning,
        "missing_fields": report.missing_fields,
        "support_gaps": support_gaps,
        "candidate_handoff": candidate,
        "agent_state": agent_state,
        "raw_response": agent_result.get("raw_response", ""),
        "model": agent_result.get("model", ""),
    }


def case_profile_pairs(case_ids: list[str] | None, profile: str) -> list[tuple[str, str]]:
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")
    if profile == "hostile":
        if case_ids:
            raise ValueError("--profile hostile uses its fixed 3-case set; omit --case")
        return PROFILE_CASES["hostile"]
    ids = case_ids or all_anchor_ids()
    return [(case_id, profile) for case_id in ids]


def run_b2b_rollup(case_ids: list[str] | None, profile: str = "clean") -> dict[str, Any]:
    t0 = time.time()
    rows: list[dict[str, Any]] = []
    pairs = case_profile_pairs(case_ids, profile)

    print(f"\nRunning Flow 2 over {len(pairs)} B2B engineering handoff cases (profile={profile})...\n")
    for i, (case_id, row_profile) in enumerate(pairs, 1):
        print(f"  [{i}/{len(pairs)}] {case_id} [{row_profile}] ...", end="", flush=True)
        row = grade_anchor(case_id, profile=row_profile)
        rows.append(row)
        flag = "PASS" if row["passed"] else f"BLOCK ({len(row['missing_fields'])} gaps)"
        if row["outcome"] == "pass_prose_flagged":
            flag = "PASS + REVIEW"
        print(f" {flag}")

    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    outcome_counts = Counter(row["outcome"] for row in rows)
    gap_counts = Counter(gap for row in rows for gap in row["support_gaps"])
    top_gap = gap_counts.most_common(1)[0] if gap_counts else (None, 0)
    elapsed = time.time() - t0

    print("\n" + "=" * 72)
    print("  FLOW 2 ROLL-UP — Human → Engineering Gate (Contract B, B2B)")
    print("=" * 72)
    print(f"\n  {'case':<48}{'leniency':<10}{'result'}")
    print(f"  {'-'*46:<48}{'-'*8:<10}{'-'*20}")
    for row in rows:
        if row["outcome"] == "pass_clean":
            result = "warm handoff"
        elif row["outcome"] == "pass_prose_flagged":
            result = "review structure"
        else:
            result = f"blocked · {len(row['missing_fields'])} gaps"
        print(f"  {row['case_id']:<48}{row['leniency']:<10}{result}")

    print(f"\n  Warm handoffs:    {outcome_counts.get('pass_clean', 0)}/{total}")
    print(f"  Human review:     {outcome_counts.get('pass_prose_flagged', 0)}/{total}")
    print(f"  Blocked:          {outcome_counts.get('blocked', 0)}/{total}")
    print(f"  Pass rate:        {passed}/{total} ({100*passed//total if total else 0}%)")
    if top_gap[0]:
        print(f"  Top recurring gap: '{top_gap[0]}' — seen in {top_gap[1]}/{total} handoffs")
    print(f"\n  Total time: {elapsed:.1f}s")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "contract": "B",
        "flow": "human_to_engineering",
        "profile": profile,
        "cases": total,
        "pass_rate": round(passed / total, 3) if total else 0,
        "passed": passed,
        "outcome_counts": dict(outcome_counts),
        "top_recurring_gap": {"field": top_gap[0], "count": top_gap[1]},
        "gap_counts": dict(gap_counts),
        "rows": rows,
        "elapsed_seconds": round(elapsed, 1),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"b2b_rollup_{ts}.json"
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"  Saved: {out_path.name}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Handoff Quality Gate — Flow 2 B2B roll-up")
    parser.add_argument("--case", action="append", dest="cases", help="anchor case ID (repeatable; default: all)")
    parser.add_argument(
        "--profile",
        choices=sorted(SUPPORTED_PROFILES),
        default="clean",
        help="agent-facing transcript/state profile (default: clean)",
    )
    args = parser.parse_args()
    run_b2b_rollup(args.cases, profile=args.profile)


if __name__ == "__main__":
    main()
