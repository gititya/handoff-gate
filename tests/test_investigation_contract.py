"""Synthetic tests for the app-independent investigation contract."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from investigation_contract import CONTRACT_VERSION, validate_investigation


def _record(*, outcome="not_resolved"):
    evidence = [
        {
            "event_id": "question-1",
            "kind": "customer_question",
            "session_id": "session-1",
            "product_id": "product-1",
            "text": "The export is blank.",
        },
        {
            "event_id": "step-1-observed",
            "kind": "guidance_step_observed",
            "session_id": "session-1",
            "product_id": "product-1",
            "step_id": "check-export",
            "target_id": "export-queue",
            "run_id": "run-1",
            "predicate": "queue has no completed job",
            "journey_id": "journey-1",
        },
    ]
    if outcome == "not_resolved":
        evidence.append(
            {
                "event_id": "confirmation-1",
                "kind": "customer_confirmation",
                "session_id": "session-1",
                "product_id": "product-1",
                "answer": "no",
                "run_id": "run-1",
            }
        )
    evidence.append({
        "event_id": "decision-0",
        "kind": "support_decision",
        "session_id": "session-1",
        "product_id": "product-1",
        "current_risk": "medium",
        "risk_signals": [{
            "signal_id": "customer_blocked",
            "risk": "medium",
            "reason": "Customer is blocked",
            "resolved": False,
        }],
        "confirmed_facts": [],
    })
    return {
        "schema_version": CONTRACT_VERSION,
        "session_id": "session-1",
        "product_id": "product-1",
        "customer_request": {
            "text": "The export is blank.",
            "evidence_ref": "question-1",
        },
        "current_goal": {
            "text": "Find why the export is blank",
            "source": "customer",
        },
        "steps": [
            {
                "step_id": "check-export",
                "target_id": "export-queue",
                "run_id": "run-1",
                "status": "observed",
                "evidence_refs": ["step-1-observed"],
                "result": "queue has no completed job",
            }
        ],
        "knowledge": [{"pin": "product-guide:exports", "source_ref": "kb:exports-v2"}],
        "customer_outcome": outcome,
        "confirmation_ref": "confirmation-1" if outcome == "not_resolved" else None,
        "guidance_run_id": "run-1" if outcome == "not_resolved" else None,
        "handoff_reason": "A support rep should inspect the export queue.",
        "risk": {"level": "medium", "signals": [{
            "signal_id": "customer_blocked",
            "risk": "medium",
            "reason": "Customer is blocked",
            "resolved": False,
        }]},
        "unknowns": ["Whether the queue worker recovered"],
        "identity": {"status": "not_supplied"},
        "confirmed_facts": [],
        "evidence": evidence,
        "recipient": {
            "kind": "local_support_review",
            "external_delivery": "not_requested",
        },
        "core_decision_ref": "decision-0",
    }


def test_valid_investigation_passes_without_mutation():
    record = _record()
    original = deepcopy(record)
    assert validate_investigation(record) == []
    assert record == original


def test_not_asked_allows_urgent_handoff_without_steps():
    record = _record(outcome="not_asked")
    record["steps"] = []
    record["handoff_reason"] = "Customer requested a human during an active incident."
    assert validate_investigation(record) == []


def test_not_resolved_requires_customer_no_confirmation():
    record = _record()
    record["evidence"] = [event for event in record["evidence"] if event["kind"] != "customer_confirmation"]
    errors = validate_investigation(record)
    assert any("customer_confirmation" in error for error in errors)


def test_customer_request_reference_must_match_question_text():
    record = _record()
    record["customer_request"]["text"] = "The report is missing."
    errors = validate_investigation(record)
    assert any("exactly match" in error for error in errors)


def test_wrong_reference_and_duplicate_evidence_are_rejected():
    record = _record()
    record["steps"][0]["evidence_refs"] = ["missing-event"]
    record["evidence"].append(dict(record["evidence"][0]))
    errors = validate_investigation(record)
    assert any("does not resolve" in error for error in errors)
    assert any("duplicate evidence" in error for error in errors)


def test_observed_step_requires_runtime_observation_and_matching_predicate():
    record = _record()
    record["steps"][0]["evidence_refs"] = ["question-1"]
    errors = validate_investigation(record)
    assert any("guidance_step_observed" in error for error in errors)

    record = _record()
    record["steps"][0]["result"] = "a different result"
    errors = validate_investigation(record)
    assert any("predicate" in error for error in errors)


def test_event_origin_must_match_record_session_and_product():
    record = _record()
    record["evidence"][0]["session_id"] = "other-session"
    errors = validate_investigation(record)
    assert any("record origin" in error for error in errors)


def test_high_risk_is_preserved_and_does_not_get_downgraded():
    record = _record()
    record["risk"] = {"level": "high", "signals": [{
        "signal_id": "account_takeover",
        "risk": "high",
        "reason": "Active account takeover concern",
        "resolved": False,
    }]}
    decision = next(event for event in record["evidence"] if event["kind"] == "support_decision")
    decision["current_risk"] = "high"
    decision["risk_signals"] = record["risk"]["signals"]
    original = deepcopy(record["risk"])
    assert validate_investigation(record) == []
    assert record["risk"] == original


def test_supplied_identity_requires_its_verified_evidence_handle():
    record = _record()
    record["identity"] = {"status": "supplied", "value": "customer-1"}
    errors = validate_investigation(record)
    assert any("identity.evidence_handle" in error for error in errors)

    record["identity"]["evidence_handle"] = "fact-identity-1"
    record["confirmed_facts"] = [{
        "claim": "customer_account_identity",
        "value": "customer-1",
        "evidence_handle": "fact-identity-1",
    }]
    decision = next(event for event in record["evidence"] if event["kind"] == "support_decision")
    decision["confirmed_facts"] = record["confirmed_facts"]
    assert validate_investigation(record) == []


def test_invalid_or_null_records_return_errors_instead_of_raising():
    assert validate_investigation(None)
    assert validate_investigation([])
    errors = validate_investigation({"schema_version": CONTRACT_VERSION})
    assert any("missing required field" in error for error in errors)


def test_knowledge_requires_a_source_pin_and_does_not_use_defaults():
    record = _record()
    record["knowledge"] = [{}]
    errors = validate_investigation(record)
    assert any("pin or source_ref" in error for error in errors)


def test_malformed_enum_and_reference_values_fail_closed_without_raising():
    record = _record()
    record["current_goal"]["source"] = []
    record["customer_outcome"] = {}
    record["risk"]["level"] = []
    record["identity"]["status"] = {}
    record["steps"][0]["status"] = []
    record["knowledge"] = [{"pin": "kb:exports", "evidence_ref": []}]
    record["core_decision_ref"] = []
    errors = validate_investigation(record)
    assert len(errors) >= 6


def test_risk_signals_require_structured_core_entries():
    record = _record(outcome="not_asked")
    record["risk"]["signals"] = [None, [], {
        "signal_id": [],
        "risk": {},
        "reason": [],
        "source": "untrusted",
    }]
    decision = next(event for event in record["evidence"] if event["kind"] == "support_decision")
    decision["risk_signals"] = record["risk"]["signals"]
    errors = validate_investigation(record)
    assert any("risk.signals[0] must be an object" in error for error in errors)
    assert any("risk.signals[2].source has an invalid value" in error for error in errors)


def test_supplied_identity_rejects_malformed_or_missing_confirmed_fact():
    record = _record(outcome="not_asked")
    record["identity"] = {
        "status": "supplied",
        "value": "customer-1",
        "evidence_handle": "fact-identity-1",
    }
    record["confirmed_facts"] = [None, []]
    errors = validate_investigation(record)
    assert any("confirmed_facts[0]" in error for error in errors)
    assert any("customer_account_identity fact" in error for error in errors)

    record["confirmed_facts"] = [{
        "claim": "customer_account_identity",
        "value": "another-customer",
        "evidence_handle": "fact-other",
    }]
    errors = validate_investigation(record)
    assert any("customer_account_identity fact" in error for error in errors)


def test_repeated_step_ids_are_allowed_across_runs_but_not_within_a_run():
    record = _record(outcome="not_asked")
    second_event = dict(record["evidence"][1])
    second_event.update(event_id="step-2-observed", run_id="run-2")
    record["evidence"].append(second_event)
    second_step = dict(record["steps"][0], run_id="run-2", evidence_refs=["step-2-observed"])
    record["steps"].append(second_step)
    assert validate_investigation(record) == []

    record["steps"].append(dict(second_step, evidence_refs=["step-2-observed"]))
    errors = validate_investigation(record)
    assert any("duplicate step identity" in error for error in errors)


def test_observed_step_run_id_must_match_runtime_event():
    record = _record(outcome="not_asked")
    record["steps"][0]["run_id"] = "run-other"
    errors = validate_investigation(record)
    assert any("guidance_step_observed" in error for error in errors)


def test_not_resolved_selects_latest_confirmation_for_the_run():
    record = _record()
    record["evidence"].append({
        "event_id": "confirmation-old",
        "kind": "customer_confirmation",
        "session_id": "session-1",
        "product_id": "product-1",
        "answer": "no",
        "run_id": "run-1",
    })
    record["confirmation_ref"] = "confirmation-1"
    errors = validate_investigation(record)
    assert any("latest customer_confirmation" in error for error in errors)


def test_knowledge_evidence_must_be_selected_and_match_source_fields():
    record = _record(outcome="not_asked")
    record["evidence"].append({
        "event_id": "knowledge-1",
        "kind": "knowledge_selected",
        "session_id": "session-1",
        "product_id": "product-1",
        "article_id": "article-1",
        "revision": "r1",
        "content_hash": "hash-1",
        "source_url": "https://example.test/article-1",
    })
    record["knowledge"] = [{
        "article_id": "article-2",
        "revision": "r1",
        "content_hash": "hash-1",
        "source_url": "https://example.test/article-1",
        "evidence_ref": "knowledge-1",
    }]
    errors = validate_investigation(record)
    assert any("does not match its knowledge evidence" in error for error in errors)


def test_core_decision_provenance_must_match_preserved_risk_and_facts():
    record = _record(outcome="not_asked")
    record["confirmed_facts"] = []
    record["evidence"].append({
        "event_id": "decision-1",
        "kind": "support_decision",
        "session_id": "session-1",
        "product_id": "product-1",
        "current_risk": "medium",
        "risk_signals": record["risk"]["signals"],
        "confirmed_facts": [],
    })
    record["core_decision_ref"] = "decision-1"
    assert validate_investigation(record) == []

    record["evidence"][-1]["current_risk"] = "low"
    errors = validate_investigation(record)
    assert any("current_risk" in error for error in errors)
