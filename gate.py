"""Gate — Step 4, the intercept-and-hold.

Combines judge verdict + contract field-presence check + leniency rule.
On fail: blocks the handoff, names missing fields, generates corrected
note via live Claude call, then releases.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

import anthropic


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        key = subprocess.check_output(
            ["security", "find-generic-password", "-s", "ANTHROPIC_API_KEY", "-w"],
            text=True,
        ).strip()
        if key:
            return key
    except subprocess.CalledProcessError:
        pass
    raise RuntimeError(
        "ANTHROPIC_API_KEY not found in env or macOS keychain."
    )

from contracts import check_handoff, GapReport

MODEL = "claude-haiku-4-5-20251001"


def _generate_corrected_note(
    candidate: dict[str, Any],
    expected: dict[str, Any],
    gap_report: GapReport,
    judge_verdict: dict[str, Any] | None,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Generate a corrected handoff note via live Claude call."""
    missing = gap_report.missing_fields
    judge_gaps = []
    if judge_verdict:
        if judge_verdict.get("missing_requirement"):
            judge_gaps.append(f"Missing: {judge_verdict['missing_requirement']}")
        if judge_verdict.get("evidence_gap"):
            judge_gaps.append(f"Evidence gap: {judge_verdict['evidence_gap']}")

    state_summary = {
        "facts": state.get("facts", []),
        "unknowns": state.get("unknowns", []),
        "candidate_branches": state.get("candidate_branches", []),
        "ruled_out_branches": state.get("ruled_out_branches", []),
        "final_cause": state.get("final_cause", ""),
    }

    prompt = (
        "You are correcting an incomplete support handoff note. "
        "The original note was missing critical fields.\n\n"
        f"ORIGINAL HANDOFF NOTE:\n{json.dumps(candidate, indent=2)}\n\n"
        f"MISSING FIELDS: {missing}\n"
    )
    if judge_gaps:
        prompt += f"JUDGE FINDINGS: {'; '.join(judge_gaps)}\n"
    if gap_report.thin_but_silent:
        prompt += (
            "CRITICAL: The original note was SILENT about the open state. "
            "The cause is not yet determined — state this explicitly with "
            "the reason (e.g. fraud-flagged, evidence inconclusive).\n"
        )
    prompt += (
        f"\nRECONSTRUCTED CASE STATE:\n{json.dumps(state_summary, indent=2)}\n\n"
        f"EXPECTED COMPLETE HANDOFF (answer key):\n{json.dumps(expected, indent=2)}\n\n"
        "Write the CORRECTED handoff note as a complete JSON object with ALL "
        "required fields filled in from the reconstructed state and answer key. "
        "Return ONLY the JSON object."
    )

    client = anthropic.Anthropic(api_key=_get_api_key())
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        return {"_raw": raw, "_parse_error": True}


class HandoffPackage:
    def __init__(self, case_id: str, candidate: dict[str, Any]):
        self.case_id = case_id
        self.candidate = candidate
        self.corrected: dict[str, Any] | None = None
        self.released = False
        self.blocked = False
        self.gap_report: GapReport | None = None
        self.judge_verdict: dict[str, Any] | None = None

    def release(self) -> None:
        self.released = True

    @property
    def final_handoff(self) -> dict[str, Any]:
        return self.corrected if self.corrected else self.candidate


def release_to_copilot(package: HandoffPackage) -> None:
    """Simulated workflow boundary — refuses to release on fail."""
    if not package.released:
        raise RuntimeError(
            f"BLOCKED: Handoff for {package.case_id} cannot be released. "
            f"Missing fields: {package.gap_report.missing_fields if package.gap_report else 'unknown'}"
        )


def run_gate(
    case_id: str,
    candidate: dict[str, Any],
    expected: dict[str, Any],
    state: dict[str, Any],
    judge_verdict: dict[str, Any] | None,
) -> HandoffPackage:
    """Run the gate: check, block if needed, correct, release."""
    package = HandoffPackage(case_id, candidate)
    package.judge_verdict = judge_verdict

    gap_report = check_handoff(candidate, expected, state)
    package.gap_report = gap_report

    judge_failed = judge_verdict and not judge_verdict.get("pass", True)

    if gap_report.passed and not judge_failed:
        package.release()
        return package

    # BLOCKED — intercept and hold
    package.blocked = True

    corrected = _generate_corrected_note(
        candidate, expected, gap_report, judge_verdict, state
    )
    package.corrected = corrected
    package.release()

    return package
