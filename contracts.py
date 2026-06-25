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


@dataclass
class GapReport:
    missing_always: list[str] = field(default_factory=list)
    missing_other: list[str] = field(default_factory=list)
    thin_but_silent: bool = False
    leniency: LeniencyRule = field(default_factory=lambda: LeniencyRule(mode="strict"))

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
