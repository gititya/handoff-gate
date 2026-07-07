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
    evidence_gaps: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            not self.missing_always
            and not self.missing_other
            and not self.thin_but_silent
            and not self.evidence_gaps
        )

    @property
    def missing_fields(self) -> list[str]:
        return self.missing_always + self.missing_other + self.evidence_gaps


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


def _note_dump(note: Any) -> dict[str, Any]:
    if hasattr(note, "model_dump"):
        return note.model_dump(mode="python")
    return dict(note)


def _claim_lookup(note: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in note.get("confirmed_facts", []):
        if isinstance(item, dict) and item.get("claim"):
            out[item["claim"]] = item.get("value")
    return out


def _branch_summaries(items: Any) -> list[str]:
    summaries: list[str] = []
    rows = items if isinstance(items, list) else _as_list(items)
    for item in rows:
        if isinstance(item, dict):
            summary = item.get("summary")
        else:
            summary = item
        if summary not in (None, "", [], {}):
            summaries.append(str(summary))
    return summaries


def from_handoff_note(note: Any, *, contract: str = "A") -> dict[str, Any]:
    """Adapt support_ontology.HandoffNote to an existing gate contract.

    This is deliberately a shape adapter only. Contract A/B checks remain unchanged.
    """
    data = _note_dump(note)
    facts = _claim_lookup(data)
    identity = data.get("identity", {})
    claim = data.get("claim", {})
    charge_ref = data.get("charge_ref") or {}

    if contract.upper() == "A":
        return {
            "customer_account_identity": identity.get("value"),
            "account_id": facts.get("account_id"),
            "subscription_id": facts.get("subscription_id"),
            "charge": charge_ref.get("value") or facts.get("charge"),
            "customer_claim": claim.get("value"),
            "desired_outcome": facts.get("desired_outcome"),
            "checks_with_results": facts.get("checks_with_results"),
            "ruled_out_branches": facts.get("ruled_out_branches") or _branch_summaries(data.get("ruled_out", [])),
            "likely_cause": data.get("likely_cause"),
            "confidence": data.get("confidence"),
            "risk_urgency": facts.get("risk_urgency") or data.get("risk", {}).get("level"),
            "next_step": facts.get("next_step") or data.get("handoff_reason"),
            "what_not_to_promise": facts.get("what_not_to_promise") or "No refund, cause, fix, or timeline promise.",
        }

    if contract.upper() == "B":
        return {
            "customer_account_identity": identity.get("value"),
            "affected_scope": facts.get("affected_scope"),
            "system_discrepancy": claim.get("value") or facts.get("system_discrepancy"),
            "evidence_handles": facts.get("evidence_handles"),
            "specific_ask": facts.get("specific_ask") or data.get("handoff_reason"),
            "support_ruled_out": facts.get("support_ruled_out") or _branch_summaries(data.get("ruled_out", [])),
            "impact_urgency": facts.get("impact_urgency") or data.get("risk", {}).get("level"),
            "likely_cause": data.get("likely_cause"),
            "confidence": data.get("confidence"),
            "open_unknowns": data.get("open_unknowns", []),
            "candidate_branches": _branch_summaries(data.get("candidate_branches", [])),
        }

    raise ValueError(f"Unsupported handoff contract: {contract}")


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
    "open", "either", " vs ", " or ", "pending", "tbd",
)


def _names_open_state_in_prose(likely_cause: Any) -> bool:
    if not isinstance(likely_cause, str) or not likely_cause.strip():
        return False
    low = likely_cause.lower()
    return any(marker in low for marker in _OPEN_STATE_MARKERS)




def _as_list(val: Any) -> list[str]:
    if _is_empty(val):
        return []
    if isinstance(val, list):
        return [str(item).strip() for item in val if str(item).strip()]
    return [str(val).strip()]


def _norm_token(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


_TOKEN_STOPWORDS = {
    "a", "an", "and", "as", "at", "both", "but", "by", "case", "either",
    "for", "from", "in", "is", "issue", "of", "or", "path", "state", "the",
    "to", "vs", "with",
}


def _word_tokens(value: Any) -> set[str]:
    raw = str(value).lower().replace("_", " ").replace("-", " ")
    token = ""
    tokens: set[str] = set()
    for ch in raw:
        if ch.isalnum():
            token += ch
        elif token:
            if len(token) > 1 and token not in _TOKEN_STOPWORDS:
                tokens.add(token)
            token = ""
    if token and len(token) > 1 and token not in _TOKEN_STOPWORDS:
        tokens.add(token)
    return tokens


def _has_named_overlap(candidate_values: Any, evidence_values: Any) -> bool:
    candidate_tokens = [_norm_token(v) for v in _as_list(candidate_values)]
    evidence_tokens = [_norm_token(v) for v in _as_list(evidence_values)]
    candidate_tokens = [v for v in candidate_tokens if v]
    evidence_tokens = [v for v in evidence_tokens if v]
    if any(c in e or e in c for c in candidate_tokens for e in evidence_tokens):
        return True

    for candidate in _as_list(candidate_values):
        candidate_words = _word_tokens(candidate)
        if not candidate_words:
            continue
        for evidence in _as_list(evidence_values):
            evidence_words = _word_tokens(evidence)
            if len(candidate_words & evidence_words) >= 2:
                return True
    return False


def _likely_cause_has_evidence(candidate: dict[str, Any], expected: dict[str, Any], state: dict[str, Any]) -> bool:
    likely_cause = candidate.get("likely_cause")
    if _is_empty(likely_cause):
        return False
    expected_cause = expected.get("likely_cause")
    final_cause = state.get("final_cause")
    return _has_named_overlap(likely_cause, [expected_cause, final_cause])

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

    if not _is_empty(candidate.get("evidence_handles")):
        evidence_pool = state.get("facts", []) + expected.get("evidence_handles", [])
        if not _has_named_overlap(candidate.get("evidence_handles"), evidence_pool):
            report.evidence_gaps.append("evidence_handles_not_supported")

    if not _is_empty(candidate.get("support_ruled_out")):
        ruled_out_pool = state.get("ruled_out_branches", []) + expected.get("support_ruled_out", [])
        if not _has_named_overlap(candidate.get("support_ruled_out"), ruled_out_pool):
            report.evidence_gaps.append("support_ruled_out_not_supported")

    cause_keys = ["likely_cause", "confidence"]
    if leniency.mode == "strict":
        for key in cause_keys:
            if _is_empty(candidate.get(key)):
                report.missing_other.append(key)
        if not _is_empty(candidate.get("likely_cause")) and not _likely_cause_has_evidence(candidate, expected, state):
            report.evidence_gaps.append("likely_cause_not_supported")
    else:
        # Lenient arm — cause is genuinely open. An honest WARM escalation must
        # still name what is still open; a COLD one (no work, says nothing about
        # the open state) is what we block. Middle path: accept the open branches
        # whether they're in the dedicated `open_unknowns` list OR named in the
        # `likely_cause` prose — but soft-flag prose-only for structure.
        cause_val = candidate.get("likely_cause", "")
        conf_val = candidate.get("confidence", "")
        candidate_branch_alias = candidate.get("candidate_branches")
        if not _is_empty(candidate.get("open_unknowns")):
            open_pool = state.get("candidate_branches", []) + expected.get("open_unknowns", [])
            if not _has_named_overlap(candidate.get("open_unknowns"), open_pool):
                report.evidence_gaps.append("open_unknowns_not_supported")
        elif not _is_empty(candidate_branch_alias):
            open_pool = state.get("candidate_branches", []) + expected.get("open_unknowns", [])
            if not _has_named_overlap(candidate_branch_alias, open_pool):
                report.evidence_gaps.append("open_unknowns_not_supported")
            else:
                report.structure_warning = True
                report.structure_warning_reason = (
                    "Open branches named in candidate_branches, not the dedicated "
                    "open_unknowns list — accepted; structure them as open_unknowns."
                )
        elif _is_empty(cause_val) and _is_empty(conf_val):
            report.thin_but_silent = True  # silent → block
        elif _names_open_state_in_prose(cause_val):
            open_pool = state.get("candidate_branches", []) + expected.get("open_unknowns", [])
            if not _has_named_overlap(cause_val, open_pool):
                report.evidence_gaps.append("open_unknowns_not_supported")
            else:
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
