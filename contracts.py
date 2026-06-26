"""Contract A — AI → human (billing agent).

Encodes the locked Phase 0 definition of 'complete' for a B2C
disputed-charge handoff. The leniency rule derives from reconstructed
evidence, not a metadata label.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALWAYS_REQUIRED_KEYS = [
    "customer_account_identity",
    "account_id",
    "subscription_id",
    "charge",
    "customer_claim",
]

ALL_REQUIRED_KEYS = ALWAYS_REQUIRED_KEYS + [
    "desired_outcome",
    "checks_with_results",
    "ruled_out_branches",
    "likely_cause",
    "confidence",
    "risk_urgency",
    "next_step",
    "what_not_to_promise",
]


@dataclass
class LeniencyRule:
    mode: str  # "strict" | "lenient" | "borderline"
    borderline: bool = False
    reason: str = ""


def derive_leniency(state: dict[str, Any]) -> LeniencyRule:
    """Derive field-6 leniency from the reconstructed evidence state.

    strict:     root_cause_evidence_seen and final_cause set
    lenient:    neither set (fraud, cut-short, evidence open)
    borderline: ambiguous — default lenient but flag for human review
    """
    has_cause = bool(state.get("final_cause"))
    evidence_seen = bool(state.get("root_cause_evidence_seen"))

    if evidence_seen and has_cause:
        return LeniencyRule(mode="strict", reason="Evidence pinned the cause")

    if not evidence_seen and not has_cause:
        branches = state.get("candidate_branches", [])
        if len(branches) <= 1 and branches:
            return LeniencyRule(
                mode="lenient",
                borderline=True,
                reason=(
                    "Single open branch but no evidence confirmation — "
                    "default lenient, flagged for review"
                ),
            )
        return LeniencyRule(
            mode="lenient",
            reason="Evidence did not pin a cause (fraud/open/cut-short)",
        )

    # Mismatch: one set without the other
    return LeniencyRule(
        mode="lenient",
        borderline=True,
        reason=(
            f"Ambiguous evidence state (cause={'set' if has_cause else 'empty'}, "
            f"evidence_seen={evidence_seen}) — default lenient, flagged"
        ),
    )


# --- Contract B — human → engineering (B2B product-bug escalation) ---
#
# Added under the integration stance (see SKILL.md SUPERSEDED note): the copilot
# (real-time_support_Updated) works a B2B product-bug case and the human escalates
# to engineering. The leniency rule is the SAME derive_leniency() as Contract A —
# strict when reconstructed evidence pinned the cause, lenient (but explicit about
# the open state) when it did not.

ALWAYS_REQUIRED_KEYS_B = [
    "customer_account_identity",
    "affected_scope",
    "system_discrepancy",
    "evidence_handles",
    "specific_ask",
]

ALL_REQUIRED_KEYS_B = ALWAYS_REQUIRED_KEYS_B + [
    "support_ruled_out",
    "impact_urgency",
    "likely_cause",
    "confidence",
    # open_unknowns is conditionally required (lenient arm only) — see check_handoff_b
]


@dataclass
class GapReport:
    missing_always: list[str] = field(default_factory=list)
    missing_other: list[str] = field(default_factory=list)
    thin_but_silent: bool = False
    leniency: LeniencyRule = field(default_factory=lambda: LeniencyRule(mode="strict"))
    # Soft signal — does NOT affect `passed`. Set when the substance is present
    # but in a less-structured place than preferred (e.g. open branches named in
    # prose rather than the dedicated open_unknowns list). Routes to human review.
    structure_warning: bool = False
    structure_warning_reason: str = ""

    @property
    def passed(self) -> bool:
        return not self.missing_always and not self.missing_other and not self.thin_but_silent

    @property
    def missing_fields(self) -> list[str]:
        return self.missing_always + self.missing_other


def check_handoff(
    candidate: dict[str, Any],
    expected: dict[str, Any],
    state: dict[str, Any],
) -> GapReport:
    """Check a candidate handoff against Contract A + evidence-derived leniency."""
    leniency = derive_leniency(state)
    report = GapReport(leniency=leniency)

    for key in ALWAYS_REQUIRED_KEYS:
        val = candidate.get(key)
        if not val or (isinstance(val, str) and not val.strip()):
            report.missing_always.append(key)

    cause_keys = ["likely_cause", "confidence"]
    other_keys = [k for k in ALL_REQUIRED_KEYS if k not in ALWAYS_REQUIRED_KEYS and k not in cause_keys]

    for key in other_keys:
        val = candidate.get(key)
        if not val or (isinstance(val, str) and not val.strip()):
            report.missing_other.append(key)

    if leniency.mode == "strict":
        for key in cause_keys:
            val = candidate.get(key)
            if not val or (isinstance(val, str) and not val.strip()):
                report.missing_other.append(key)
    else:
        # Lenient: cause can be "unexplained" / low — but must be explicit, not silent
        cause_val = candidate.get("likely_cause", "")
        conf_val = candidate.get("confidence", "")
        if not cause_val and not conf_val:
            report.thin_but_silent = True

    return report


def _is_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    if isinstance(val, (list, dict)):
        return len(val) == 0
    return False


# STOPGAP — deterministic prose check until the LLM-extractor seam lands
# (see handoff-engine/docs/llm-extractor-deferral.md). When an honest open
# escalation names its remaining branches inside `likely_cause` instead of the
# dedicated `open_unknowns` list, we want to ACCEPT it (the substance is there)
# but flag it for structure. This token scan is the cheap deterministic stand-in
# for "did the agent state what's still open?" — the extractor replaces it once
# the analytics show prose-only passes are frequent enough to justify the build.
_OPEN_STATE_MARKERS = (
    "undetermined", "unresolved", "unknown", "not determined",
    "open", "either", " vs ", "pending", "tbd",
)


def _names_open_state_in_prose(likely_cause: Any) -> bool:
    if not isinstance(likely_cause, str) or not likely_cause.strip():
        return False
    low = likely_cause.lower()
    return any(marker in low for marker in _OPEN_STATE_MARKERS)


def check_handoff_b(
    candidate: dict[str, Any],
    expected: dict[str, Any],
    state: dict[str, Any],
) -> GapReport:
    """Check a human→engineering handoff against Contract B + evidence-derived leniency.

    Strict (evidence pinned the cause): likely_cause + confidence required.
    Lenient (cause genuinely open): the cause may be 'undetermined', but the note
    must (a) not be silent about it and (b) name the open unknowns — an honest
    open handoff lists what engineering still has to resolve.
    """
    leniency = derive_leniency(state)
    report = GapReport(leniency=leniency)

    for key in ALWAYS_REQUIRED_KEYS_B:
        if _is_empty(candidate.get(key)):
            report.missing_always.append(key)

    for key in ["support_ruled_out", "impact_urgency"]:
        if _is_empty(candidate.get(key)):
            report.missing_other.append(key)

    cause_keys = ["likely_cause", "confidence"]
    if leniency.mode == "strict":
        for key in cause_keys:
            if _is_empty(candidate.get(key)):
                report.missing_other.append(key)
    else:
        # Lenient arm — cause is genuinely open. An honest WARM escalation must
        # still name what is still open; a COLD one (no work, says nothing about
        # the open state) is what we block. Middle path: accept the open branches
        # whether they're in the dedicated `open_unknowns` list OR named in the
        # `likely_cause` prose — but soft-flag prose-only for structure.
        cause_val = candidate.get("likely_cause", "")
        conf_val = candidate.get("confidence", "")
        if _is_empty(cause_val) and _is_empty(conf_val):
            report.thin_but_silent = True  # silent → block
        elif not _is_empty(candidate.get("open_unknowns")):
            pass  # clean warm escalation — open branches in the dedicated list
        elif _names_open_state_in_prose(cause_val):
            # Substance is there, structure isn't — pass, but route to human review.
            report.structure_warning = True
            report.structure_warning_reason = (
                "Open branches named in likely_cause prose, not the dedicated "
                "open_unknowns list — accepted; structure them as a list."
            )
        else:
            # Cold: no open_unknowns and prose doesn't state what's still open.
            report.thin_but_silent = True

    return report
