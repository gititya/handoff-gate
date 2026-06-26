"""Unit tests for Contract B + the evidence-derived leniency rule.

Self-contained: synthetic fixtures, no API/MLX, no cross-repo paths.
Run: cd handoff-engine && python -m pytest tests/ -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contracts import (  # noqa: E402
    check_handoff_b,
    derive_leniency,
    ALWAYS_REQUIRED_KEYS_B,
)
from engine import reconstruct_fixture  # noqa: E402


# --- fixtures ---------------------------------------------------------------

def _fixture(*, with_cause: bool):
    """Minimal B2B fixture. with_cause=True pins the cause (strict arm)."""
    event = {
        "facts": ["billing:entitled", "provisioning:not_ready"],
        "ruled_out_branches": ["payment_failure"],
        "candidate_branches": ["provisioning_state_mismatch", "entitlement_cache_delay"],
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
        h["open_unknowns"] = ["provisioning_job_status"]
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
