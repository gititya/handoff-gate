"""Vendored reconstruction engine from real-time_support_Updated.

Domain-agnostic state machine that replays context_events from a
support_process_fixture.v1 case to build an authoritative reconstructed
state. Exposes final_cause + root_cause_evidence_seen for the gate's
evidence-derived leniency rule.

Stripped of B2B CANONICAL_LABELS and process_turn keyword matching.
Does NOT import or edit real-time_support_Updated.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_BASE = Path(__file__).resolve().parent.parent / (
    "support-call-generator/exports/b2c_handoff_gate_seed"
    "/process_fixture/realtime_support"
)


def load_fixture(case_id: str) -> dict[str, Any]:
    path = FIXTURE_BASE / f"{case_id}.json"
    return json.loads(path.read_text())


# --- state primitives (vendored from run.py) ---

def new_state(case_id: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "version": 0,
        "facts": [],
        "unknowns": [],
        "candidate_branches": [],
        "ruled_out_branches": [],
        "next_check": "",
        "handoff_notes": [],
        "final_cause": "",
        "root_cause_evidence_seen": False,
    }


def add_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def remove_item(items: list[str], value: str) -> None:
    while value in items:
        items.remove(value)


def add_fact(state: dict[str, Any], fact: str) -> None:
    add_unique(state["facts"], fact)


def add_unknown(state: dict[str, Any], unknown: str) -> None:
    if unknown not in state["facts"]:
        add_unique(state["unknowns"], unknown)


def resolve_unknown(state: dict[str, Any], unknown: str) -> None:
    remove_item(state["unknowns"], unknown)


def add_branch(state: dict[str, Any], branch: str) -> None:
    if branch not in state["ruled_out_branches"]:
        add_unique(state["candidate_branches"], branch)


def rule_out_branch(state: dict[str, Any], branch: str) -> None:
    remove_item(state["candidate_branches"], branch)
    add_unique(state["ruled_out_branches"], branch)


def set_next_check(state: dict[str, Any], value: str) -> None:
    state["next_check"] = value


def reconcile_state(
    state: dict[str, Any],
    context_events: list[dict[str, Any]] | None = None,
) -> None:
    for event in context_events or []:
        if event.get("relevant", True) is False:
            continue
        for unknown in event.get("resolved_unknowns", []):
            resolve_unknown(state, unknown)
        for branch in event.get("ruled_out_branches", []):
            rule_out_branch(state, branch)

    for branch in list(state["ruled_out_branches"]):
        remove_item(state["candidate_branches"], branch)

    final_cause = state.get("final_cause")
    if final_cause:
        remove_item(state["ruled_out_branches"], final_cause)
        add_branch(state, final_cause)


def refresh_handoff(state: dict[str, Any]) -> None:
    notes = []
    if state["facts"]:
        notes.append("Known: " + "; ".join(state["facts"][-4:]))
    if state["unknowns"]:
        notes.append("Unknowns: " + "; ".join(state["unknowns"][:4]))
    if state["candidate_branches"]:
        notes.append("Branches: " + "; ".join(state["candidate_branches"][:4]))
    if state["next_check"]:
        notes.append("Next check: " + state["next_check"])
    state["handoff_notes"] = notes


def apply_context_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    if event.get("relevant") is False:
        return
    state["version"] += 1
    for fact in event.get("facts", []):
        add_fact(state, fact)
    for unknown in event.get("unknowns", []):
        add_unknown(state, unknown)
    for unknown in event.get("resolved_unknowns", []):
        resolve_unknown(state, unknown)
    for branch in event.get("candidate_branches", []):
        add_branch(state, branch)
    for branch in event.get("ruled_out_branches", []):
        rule_out_branch(state, branch)
    if event.get("next_check"):
        set_next_check(state, event["next_check"])
    if event.get("final_cause"):
        state["final_cause"] = event["final_cause"]
        state["root_cause_evidence_seen"] = True
        add_branch(state, event["final_cause"])
    reconcile_state(state, [event])
    refresh_handoff(state)


# --- reconstruction entry point ---

def reconstruct(case_id: str) -> dict[str, Any]:
    """Replay context_events from the B2C fixture to build the
    authoritative reconstructed state. Deterministic, no LLM."""
    fixture = load_fixture(case_id)
    state = new_state(case_id)

    for event in fixture.get("context_events", []):
        apply_context_event(state, event)

    state["_fixture"] = fixture
    return state
