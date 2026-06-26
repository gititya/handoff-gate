"""Gate — Step 4, the intercept-and-hold.

Combines judge verdict + contract field-presence check + leniency rule.
On fail: blocks the handoff, names missing fields, generates corrected
note via live Claude call, then releases.
"""
from __future__ import annotations

import json
from typing import Any

from _api import get_api_key
from contracts import check_handoff, GapReport

MODEL = "claude-haiku-4-5-20251001"

ALLOWED_OVERRIDE_REASONS = {
    "sla_risk",
    "vip_customer",
    "active_incident",
    "missing_tool_access",
    "engineering_owned_diagnostic",
    "customer_impact",
}


def support_outcome(*, released: bool, human_review_flag: bool, blocked: bool, override_reason: str = "") -> str:
    if override_reason:
        return "override_required"
    if blocked and not released:
        return "blocked"
    if human_review_flag:
        return "pass_prose_flagged"
    if released:
        return "pass_clean"
    return "blocked"


def _generate_corrected_note(
    candidate: dict[str, Any],
    expected: dict[str, Any],
    gap_report: GapReport,
    judge_verdict: dict[str, Any] | None,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Generate a corrected handoff note via live Claude call.

    ORACLE-ASSISTED (eval-lab assumption): the correction prompt is handed the
    `expected` answer key directly (see below). That is legitimate for an
    evaluation lab where ground truth exists, but it does NOT prove a production
    gate could self-correct from operational evidence (reconstruction + transcript)
    alone. Production-grade correction would drop `expected` and rely only on the
    reconstructed state. Kept here to demonstrate the intercept-and-hold mechanics.
    """
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

    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key())
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




# A blocked note may only be auto-completed from the SYSTEM OF RECORD — the
# mechanical identity/billing facts a CRM/billing lookup legitimately returns.
# Judgment fields (likely_cause, confidence, evidence, ruled-out, open branches)
# are the human's work product: the gate NEVER invents them. If they're missing,
# the handoff stays held. This is the honesty line — correction fills facts, not
# diagnoses.
SYSTEM_OF_RECORD_FIELDS = {
    "account_id",
    "subscription_id",
    "customer_account_identity",
    "charge",
    "customer_claim",
}


def _records_view(state: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    fixture = state.get("_fixture", {})
    sources = fixture.get("trusted_sources", {})
    if "ai_to_human" in sources:
        base = dict(sources["ai_to_human"])
    elif "contract_a" in sources:
        base = dict(sources["contract_a"])
    elif "system_records" in fixture:
        base = dict(fixture["system_records"])
    else:
        # Lab stand-in for a CRM/billing lookup: the mechanical fields only.
        base = dict(expected or {})
    return {k: v for k, v in base.items() if k in SYSTEM_OF_RECORD_FIELDS}


def _generate_trusted_source_correction(
    candidate: dict[str, Any],
    gap_report: GapReport,
    state: dict[str, Any],
    expected: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    corrected = dict(candidate)
    records = _records_view(state, expected)
    unfillable: list[str] = []

    for field in gap_report.missing_fields:
        if field in records and records[field] not in (None, "", [], {}):
            corrected[field] = records[field]
        else:
            # Judgment field, or the system of record simply lacks it → hold.
            unfillable.append(field)

    return corrected, unfillable

class HandoffPackage:
    def __init__(self, case_id: str, candidate: dict[str, Any]):
        self.case_id = case_id
        self.candidate = candidate
        self.corrected: dict[str, Any] | None = None
        self.released = False
        self.blocked = False
        self.gap_report: GapReport | None = None
        self.judge_verdict: dict[str, Any] | None = None
        # Soft signal: the judge disagreed (or couldn't run). Does NOT block
        # release — it routes the released handoff to a human for review.
        self.human_review_flag = False
        self.human_review_reason = ""
        self.override_reason = ""
        self.unfillable_missing_fields: list[str] = []

    def release(self) -> None:
        self.released = True

    @property
    def final_handoff(self) -> dict[str, Any]:
        return self.corrected if self.corrected else self.candidate

    @property
    def outcome(self) -> str:
        return support_outcome(
            released=self.released,
            human_review_flag=self.human_review_flag,
            blocked=self.blocked,
            override_reason=self.override_reason,
        )


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
    check_fn=check_handoff,
    correction_mode: str = "trusted_sources",
    override_reason: str = "",
) -> HandoffPackage:
    """Run the gate: check, block if needed, correct, release.

    The HARD blocker is the mechanical contract check (`check_fn`) — deterministic,
    always available. The judge is EVIDENCE, not a release condition: if it
    disagrees (or couldn't run), the handoff still releases when mechanically
    complete, but carries a human_review_flag. This keeps local-MLX availability,
    latency, and parse errors out of the release path. Pass check_handoff_b for
    Contract B (human→engineering).
    """
    package = HandoffPackage(case_id, candidate)
    package.judge_verdict = judge_verdict

    gap_report = check_fn(candidate, expected, state)
    package.gap_report = gap_report

    if override_reason:
        if override_reason not in ALLOWED_OVERRIDE_REASONS:
            raise ValueError(f"Unsupported override reason: {override_reason}")
        package.override_reason = override_reason

    # Judge = soft signal. A disagreement routes to a human; it does not block.
    if judge_verdict is not None and not judge_verdict.get("pass", True):
        package.human_review_flag = True
        package.human_review_reason = (
            judge_verdict.get("missing_requirement")
            or judge_verdict.get("evidence_gap")
            or "judge disagreed with completeness"
        )

    # Contract soft-flag (e.g. open branches named in prose, not the dedicated
    # list). Releases, but routes to a human — never blocks.
    if gap_report.structure_warning and not package.human_review_flag:
        package.human_review_flag = True
        package.human_review_reason = gap_report.structure_warning_reason

    if gap_report.passed:
        # Mechanically complete → release (flagged for human review if the judge dissented).
        package.release()
        return package

    # BLOCKED on mechanical gaps — intercept and hold. Release only after a verified correction
    # or an explicit support override. Override is not a pass; it records why the risk moved.
    package.blocked = True

    if override_reason:
        package.release()
        return package

    if correction_mode == "trusted_sources":
        corrected, unfillable = _generate_trusted_source_correction(candidate, gap_report, state, expected)
        package.corrected = corrected
        package.unfillable_missing_fields = unfillable
    elif correction_mode == "oracle":
        # Reads the sealed answer key — EVAL-LAB ONLY, never a production claim.
        # Must be requested explicitly; it is not the default.
        corrected = _generate_corrected_note(
            candidate, expected, gap_report, judge_verdict, state
        )
        package.corrected = corrected
    else:
        raise ValueError(f"Unsupported correction mode: {correction_mode}")

    # Re-check the corrected note before releasing — the hold stands until the
    # gaps are actually filled.
    corrected = package.corrected or {}
    if not corrected.get("_parse_error"):
        recheck = check_fn(corrected, expected, state)
        if recheck.passed:
            package.release()

    return package
