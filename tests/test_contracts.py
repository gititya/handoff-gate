"""Unit tests for Contract B + the evidence-derived leniency rule.

Self-contained: synthetic fixtures, no API/MLX, no cross-repo paths.
Run: cd handoff-engine && python -m pytest tests/ -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, "/Users/aditya/Documents/Projects/support/customer-support-ai-os")
sys.path.insert(0, "/Users/aditya/Documents/Projects/support/support-state-core/src")

from contracts import (  # noqa: E402
    check_handoff,
    check_handoff_b,
    derive_leniency,
    ALWAYS_REQUIRED_KEYS_B,
    from_handoff_note,
)
from engine import reconstruct_fixture  # noqa: E402
from gate import run_gate, support_outcome  # noqa: E402
from b2b_rollup import (  # noqa: E402
    build_agent_state,
    build_state,
    build_transcript_turns,
    grade_anchor,
    load_anchor,
)
from support_ontology import (  # noqa: E402
    HandoffNote,
    IssueType,
    Risk,
    RiskAssessment,
    SignalSource,
)
from support_ontology.handoff_note import BranchRef, EvidenceBackedClaim  # noqa: E402


# --- fixtures ---------------------------------------------------------------

def _fixture(*, with_cause: bool):
    """Minimal B2B fixture. with_cause=True pins the cause (strict arm)."""
    event = {
        "facts": ["billing:entitled", "provisioning:not_ready"],
        "ruled_out_branches": ["payment_failure"],
        "candidate_branches": [
            "provisioning_state_mismatch",
            "entitlement_cache_delay",
            "stale_entitlement_cache",
            "upstream_service_incident",
        ],
        "next_check": "Inspect provisioning job.",
    }
    if with_cause:
        event["final_cause"] = "provisioning_state_mismatch"
    return {"case_id": "synthetic", "context_events": [event]}


def _complete_handoff(*, open_state: bool):
    h = {
        "customer_account_identity": "Enterprise workspace",
        "affected_scope": "All workspace users",
        "system_discrepancy": "Billing entitled but provisioning not ready",
        "evidence_handles": ["billing:entitled", "provisioning:not_ready"],
        "specific_ask": "Inspect provisioning job and entitlement cache",
        "support_ruled_out": ["payment_failure"],
        "impact_urgency": "High",
        "likely_cause": "provisioning_state_mismatch" if not open_state else "Undetermined",
        "confidence": "high" if not open_state else "low (open)",
    }
    if open_state:
        h["open_unknowns"] = ["stale_entitlement_cache", "upstream_service_incident"]
    return h


# --- leniency derivation ----------------------------------------------------

def test_leniency_strict_when_cause_pinned():
    state = reconstruct_fixture(_fixture(with_cause=True))
    assert state["root_cause_evidence_seen"] is True
    assert derive_leniency(state).mode == "strict"


def test_leniency_lenient_when_cause_open():
    state = reconstruct_fixture(_fixture(with_cause=False))
    assert state["final_cause"] == ""
    assert derive_leniency(state).mode == "lenient"


# --- Contract B: strict arm -------------------------------------------------

def test_strict_complete_passes():
    state = reconstruct_fixture(_fixture(with_cause=True))
    h = _complete_handoff(open_state=False)
    assert check_handoff_b(h, h, state).passed


def test_strict_missing_cause_blocks():
    state = reconstruct_fixture(_fixture(with_cause=True))
    h = _complete_handoff(open_state=False)
    h.pop("likely_cause")
    h.pop("confidence")
    rep = check_handoff_b(h, h, state)
    assert not rep.passed
    assert "likely_cause" in rep.missing_other


# --- Contract B: lenient arm (honest-open-state requirement) -----------------

def test_lenient_complete_passes():
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    assert check_handoff_b(h, h, state).passed


def test_lenient_silent_about_open_state_blocks():
    """The key honest-open-state rule: an open escalation must name open_unknowns."""
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h.pop("open_unknowns")
    h.pop("likely_cause")
    h.pop("confidence")
    rep = check_handoff_b(h, h, state)
    assert not rep.passed
    assert rep.thin_but_silent is True


def test_lenient_open_state_in_prose_passes_with_warning():
    """Middle path: open branches named in likely_cause prose (no open_unknowns
    list) is an honest WARM escalation — it passes, but carries a structure
    warning. This is the exact false-block the adversarial review flagged."""
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h.pop("open_unknowns")
    h["likely_cause"] = "Undetermined — stale_entitlement_cache vs upstream_service_incident both remain open"
    rep = check_handoff_b(h, h, state)
    assert rep.passed is True
    assert rep.structure_warning is True
    assert rep.thin_but_silent is False


def test_lenient_open_state_as_A_or_B_prose_passes_with_warning():
    """'stale_cache or upstream_incident' is how the live agent actually phrases
    open branches — the most natural enumeration. Must pass with a warning, not
    block. (Regression: the ' or ' marker was missing and false-blocked it.)"""
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h.pop("open_unknowns")
    h["likely_cause"] = "stale_entitlement_cache or upstream_service_incident"
    rep = check_handoff_b(h, h, state)
    assert rep.passed is True
    assert rep.structure_warning is True


def test_lenient_open_state_in_candidate_branches_passes_with_warning():
    """The live engineering agent may copy the state's candidate_branches key.
    That is a structure problem, not a cold escalation, when the branches match
    the reconstructed open state."""
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h.pop("open_unknowns")
    h.pop("likely_cause")
    h["candidate_branches"] = ["stale_entitlement_cache", "upstream_service_incident"]
    rep = check_handoff_b(h, h, state)
    assert rep.passed is True
    assert rep.structure_warning is True


def test_lenient_cold_no_open_named_blocks():
    """Cold escalation: no open_unknowns AND likely_cause names a definite cause
    with no open-state markers — the open state is not stated anywhere, so block."""
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h.pop("open_unknowns")
    h["likely_cause"] = "provisioning_state_mismatch"
    rep = check_handoff_b(h, h, state)
    assert rep.passed is False
    assert rep.thin_but_silent is True


def test_missing_always_required_blocks():
    state = reconstruct_fixture(_fixture(with_cause=True))
    h = _complete_handoff(open_state=False)
    h.pop("system_discrepancy")
    rep = check_handoff_b(h, h, state)
    assert not rep.passed
    assert "system_discrepancy" in rep.missing_always


def test_always_required_keys_are_the_five_identity_fields():
    assert set(ALWAYS_REQUIRED_KEYS_B) == {
        "customer_account_identity", "affected_scope", "system_discrepancy",
        "evidence_handles", "specific_ask",
    }


# --- trusted-source correction + override lane ------------------------------

def _contract_a_expected():
    return {
        "customer_account_identity": "Maya R., verified",
        "account_id": "acct_123",
        "subscription_id": "sub_123",
        "charge": {"amount": "$19.99", "date": "2026-06-18"},
        "customer_claim": "Does not recognize the charge",
        "desired_outcome": "Cancel and review refund",
        "checks_with_results": ["Identity verified"],
        "ruled_out_branches": ["duplicate charge"],
        "likely_cause": "trial conversion",
        "confidence": "high",
        "risk_urgency": "Medium",
        "next_step": "Cancel renewal",
        "what_not_to_promise": "Do not promise instant refund",
    }


def _note_from_contract_a(expected):
    facts = [
        EvidenceBackedClaim(claim=key, value=value, evidence_handles=[f"expected:{key}"])
        for key, value in expected.items()
        if key not in {"customer_account_identity", "customer_claim", "charge", "likely_cause", "confidence"}
    ]
    return HandoffNote(
        identity=EvidenceBackedClaim(
            claim="customer_account_identity",
            value=expected["customer_account_identity"],
            evidence_handles=["expected:identity"],
        ),
        issue_type=IssueType.BILLING,
        claim=EvidenceBackedClaim(
            claim="customer_claim",
            value=expected["customer_claim"],
            evidence_handles=["expected:claim"],
            source=SignalSource.CUSTOMER_STATED,
        ),
        charge_ref=EvidenceBackedClaim(
            claim="charge",
            value=expected["charge"],
            evidence_handles=["expected:charge"],
        ),
        confirmed_facts=facts,
        ruled_out=[BranchRef(summary=item) for item in expected["ruled_out_branches"]],
        likely_cause=expected["likely_cause"],
        confidence=expected["confidence"],
        risk=RiskAssessment(level=Risk.MEDIUM),
        handoff_reason=expected["next_step"],
        gated_summary="Customer reports an unrecognized charge and asks for review.",
    )


def _note_from_contract_b(expected, *, open_state):
    facts = [
        EvidenceBackedClaim(claim=key, value=value, evidence_handles=[f"expected:{key}"])
        for key, value in expected.items()
        if key not in {"customer_account_identity", "system_discrepancy", "support_ruled_out", "likely_cause", "confidence", "open_unknowns"}
    ]
    return HandoffNote(
        identity=EvidenceBackedClaim(
            claim="customer_account_identity",
            value=expected["customer_account_identity"],
            evidence_handles=["expected:identity"],
        ),
        issue_type=IssueType.PRODUCT_BUG,
        claim=EvidenceBackedClaim(
            claim="system_discrepancy",
            value=expected["system_discrepancy"],
            evidence_handles=["expected:system_discrepancy"],
        ),
        confirmed_facts=facts,
        open_unknowns=expected.get("open_unknowns", []),
        ruled_out=[BranchRef(summary=item) for item in expected["support_ruled_out"]],
        likely_cause=expected["likely_cause"],
        confidence=expected["confidence"],
        risk=RiskAssessment(level=Risk.HIGH if open_state else Risk.MEDIUM),
        handoff_reason=expected["specific_ask"],
        gated_summary="Support is escalating the product issue with evidence handles.",
    )


def _contract_a_state(trusted_sources):
    return {
        "case_id": "billing",
        "facts": [],
        "unknowns": [],
        "candidate_branches": [],
        "ruled_out_branches": ["duplicate charge"],
        "final_cause": "trial conversion",
        "root_cause_evidence_seen": True,
        "_fixture": {"trusted_sources": {"ai_to_human": trusted_sources}},
    }


def test_trusted_source_correction_fills_only_available_fields():
    expected = _contract_a_expected()
    candidate = dict(expected)
    candidate.pop("account_id")
    candidate.pop("subscription_id")
    state = _contract_a_state({"account_id": "acct_123", "subscription_id": "sub_123"})

    package = run_gate(
        "billing", candidate, expected, state, None,
        check_fn=check_handoff, correction_mode="trusted_sources",
    )

    assert package.blocked is True
    assert package.released is True
    assert package.corrected["account_id"] == "acct_123"
    assert package.corrected["subscription_id"] == "sub_123"
    assert package.unfillable_missing_fields == []
    assert package.outcome == "pass_clean"


def test_trusted_source_correction_refuses_to_invent_missing_fields():
    expected = _contract_a_expected()
    candidate = dict(expected)
    candidate.pop("account_id")
    candidate.pop("subscription_id")
    state = _contract_a_state({"account_id": "acct_123"})

    package = run_gate(
        "billing", candidate, expected, state, None,
        check_fn=check_handoff, correction_mode="trusted_sources",
    )

    assert package.blocked is True
    assert package.released is False
    assert package.corrected["account_id"] == "acct_123"
    assert "subscription_id" in package.unfillable_missing_fields
    assert package.outcome == "blocked"


def test_contract_a_handoff_note_adapter_preserves_gate_verdict_bytes():
    expected = _contract_a_expected()
    state = _contract_a_state({"account_id": "acct_123", "subscription_id": "sub_123"})
    direct = check_handoff(expected, expected, state)
    adapted = check_handoff(from_handoff_note(_note_from_contract_a(expected)), expected, state)

    assert adapted == direct
    assert adapted.missing_fields == direct.missing_fields


def test_contract_b_handoff_note_adapter_preserves_gate_verdict_bytes():
    state = reconstruct_fixture(_fixture(with_cause=False))
    expected = _complete_handoff(open_state=True)
    direct = check_handoff_b(expected, expected, state)
    adapted = check_handoff_b(
        from_handoff_note(_note_from_contract_b(expected, open_state=True), contract="B"),
        expected,
        state,
    )

    assert adapted == direct
    assert adapted.missing_fields == direct.missing_fields


def test_thin_handoff_note_blocks_before_release():
    expected = _contract_a_expected()
    state = _contract_a_state({"account_id": "acct_123"})
    note = _note_from_contract_a(expected)
    candidate = from_handoff_note(note)
    candidate["subscription_id"] = ""

    package = run_gate(
        "billing", candidate, expected, state, None,
        check_fn=check_handoff, correction_mode="trusted_sources",
    )

    assert package.released is False
    assert "subscription_id" in package.gap_report.missing_fields


def test_override_required_releases_only_with_recorded_reason():
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h.pop("evidence_handles")

    package = run_gate(
        "b2b", h, _complete_handoff(open_state=True), state, None,
        check_fn=check_handoff_b, correction_mode="trusted_sources",
        override_reason="customer_impact",
    )

    assert package.blocked is True
    assert package.released is True
    assert package.override_reason == "customer_impact"
    assert package.outcome == "override_required"


# --- Contract B evidence realism -------------------------------------------

def test_contract_b_blocks_unsupported_evidence_handles():
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h["evidence_handles"] = ["browser_console_screenshot"]

    rep = check_handoff_b(h, _complete_handoff(open_state=True), state)

    assert rep.passed is False
    assert "evidence_handles_not_supported" in rep.evidence_gaps


def test_contract_b_blocks_checklist_shaped_garbage_open_branches():
    state = reconstruct_fixture(_fixture(with_cause=False))
    h = _complete_handoff(open_state=True)
    h.pop("open_unknowns")
    h["likely_cause"] = "backend issue or browser issue"

    rep = check_handoff_b(h, _complete_handoff(open_state=True), state)

    assert rep.passed is False
    assert "open_unknowns_not_supported" in rep.evidence_gaps


def test_support_outcome_counts_rollup_categories():
    rows = [
        support_outcome(released=True, human_review_flag=False, blocked=False),
        support_outcome(released=True, human_review_flag=True, blocked=False),
        support_outcome(released=False, human_review_flag=False, blocked=True),
        support_outcome(released=True, human_review_flag=False, blocked=True, override_reason="sla_risk"),
    ]

    assert rows == ["pass_clean", "pass_prose_flagged", "blocked", "override_required"]


# --- Flow 2 live-rollup support plumbing ------------------------------------

def _anchor_doc(*, strict: bool):
    likely_cause = (
        "webhook_auth_rotation — legacy worker is using the old secret"
        if strict
        else "Undetermined — stale_cache vs upstream_incident remain open"
    )
    return {
        "case_id": "anchor",
        "support_reality": "tool_access_limitation",
        "leniency_arm": "strict" if strict else "lenient",
        "expected_handoff": {
            "human_to_engineering": {
                "customer_account_identity": "Enterprise workspace",
                "affected_scope": "Webhook deliveries for one service",
                "system_discrepancy": "Customer sees failed callbacks while quota is under limit",
                "evidence_handles": ["quota:under_limit", "webhook_auth:legacy_secret"],
                "support_ruled_out": ["quota_exhaustion"],
                "likely_cause": likely_cause,
                "confidence": "high" if strict else "low (open)",
                "open_unknowns": [] if strict else ["stale_cache", "upstream_incident"],
                "impact_urgency": "High",
                "specific_ask": "Inspect webhook auth and replay one failed callback",
            }
        },
    }


def test_b2b_rollup_builds_strict_state_from_anchor():
    state = build_state(_anchor_doc(strict=True))

    assert state["root_cause_evidence_seen"] is True
    assert state["final_cause"] == "webhook_auth_rotation"
    assert state["facts"] == ["quota:under_limit", "webhook_auth:legacy_secret"]


def test_b2b_rollup_builds_lenient_support_context():
    anchor = _anchor_doc(strict=False)
    turns = build_transcript_turns(anchor)
    text = "\n".join(turn["text"] for turn in turns)

    assert "tool_access_limitation" in text
    assert "stale_cache, upstream_incident" in text
    assert "Inspect webhook auth" in text


def test_b2b_rollup_grades_generated_handoff_with_injected_agent():
    def fake_agent(transcript_turns, state):
        expected = load_anchor("level2_tool_access_limitation")["expected_handoff"]["human_to_engineering"]
        return {
            "candidate_handoff": expected,
            "raw_response": "{}",
            "model": "fake",
        }

    row = grade_anchor("level2_tool_access_limitation", handoff_fn=fake_agent)

    assert row["flow"] == "human_to_engineering"
    assert row["contract"] == "B"
    assert row["outcome"] == "pass_clean"
    assert row["missing_fields"] == []


def test_evidence_starved_profile_withholds_gold_evidence_from_agent():
    anchor = load_anchor("level2_tool_access_limitation")
    transcript = "\n".join(t["text"] for t in build_transcript_turns(anchor, profile="evidence_starved"))
    agent_state = build_agent_state(anchor, profile="evidence_starved")
    expected = anchor["expected_handoff"]["human_to_engineering"]

    for handle in expected["evidence_handles"]:
        assert handle not in transcript
        assert handle not in agent_state["facts"]
    assert agent_state["candidate_branches"] == []
    assert agent_state["ruled_out_branches"] == []


def test_evidence_starved_profile_withholds_gold_open_unknowns_from_agent_state():
    anchor = load_anchor("level2_tool_access_limitation")
    agent_state = build_agent_state(anchor, profile="evidence_starved")
    expected = anchor["expected_handoff"]["human_to_engineering"]

    for unknown in expected["open_unknowns"]:
        assert unknown not in agent_state["candidate_branches"]
        assert unknown not in agent_state["unknowns"]


def test_distractor_profile_contains_wrong_cause_but_gate_truth_keeps_real_cause():
    anchor = load_anchor("level3_misrouted_ratelimit_actually_webhook_auth")
    transcript = "\n".join(t["text"] for t in build_transcript_turns(anchor, profile="distractor_wrong_cause"))
    agent_state = build_agent_state(anchor, profile="distractor_wrong_cause")
    gate_state = build_state(anchor)

    assert "quota_exhaustion" in transcript
    assert agent_state["final_cause"] == "quota_exhaustion"
    assert gate_state["final_cause"] == "webhook_auth_rotation"


def test_cold_dump_profile_has_no_structured_diagnosis_for_agent():
    anchor = load_anchor("level2_unresolved_workspace_handoff")
    agent_state = build_agent_state(anchor, profile="cold_dump")
    transcript = "\n".join(t["text"] for t in build_transcript_turns(anchor, profile="cold_dump"))

    assert agent_state["facts"] == ["customer reports urgent access failure"]
    assert agent_state["candidate_branches"] == []
    assert agent_state["ruled_out_branches"] == []
    assert "auth:works" not in transcript
    assert "entitlement_cache_status" not in transcript


def test_hostile_grade_still_uses_full_gate_truth():
    def fake_agent(transcript_turns, state):
        assert state["candidate_branches"] == []
        return {
            "candidate_handoff": {
                "customer_account_identity": "B2B workspace",
                "affected_scope": "Import stuck",
                "system_discrepancy": "Import stalled",
                "evidence_handles": ["unsupported support note"],
                "specific_ask": "Please investigate",
                "support_ruled_out": ["unsupported branch"],
                "impact_urgency": "High",
                "likely_cause": "backend issue or browser issue",
                "confidence": "low",
            },
            "raw_response": "{}",
            "model": "fake",
        }

    row = grade_anchor(
        "level2_tool_access_limitation",
        handoff_fn=fake_agent,
        profile="evidence_starved",
    )

    assert row["profile"] == "evidence_starved"
    assert row["outcome"] == "blocked"
    assert "evidence_handles_not_supported" in row["missing_fields"]
