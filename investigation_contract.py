"""Validation for the app-independent support investigation handoff.

The contract is deliberately a validator rather than a model.  Callers keep
the record they supplied and use the returned errors to hold an unsafe or
incomplete handoff.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CONTRACT_VERSION = "support-investigation/1.0"

_OUTCOMES = {"not_resolved", "unsure", "not_asked"}
_GOAL_SOURCES = {"model_interpretation", "customer"}
_STEP_STATUSES = {"observed", "attempted"}
_IDENTITY_STATUSES = {"not_supplied", "withheld", "supplied"}
_RISK_LEVELS = {"low", "medium", "high"}
_RISK_SIGNAL_SOURCES = {"evidence_or_rule", "model_assessment"}
_RECIPIENT = {
    "kind": "local_support_review",
    "external_delivery": "not_requested",
}


def _text(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")
        return False
    return True


def _mapping(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, Mapping):
        errors.append(f"{path} must be an object")
        return False
    return True


def _string_list(value: Any, path: str, errors: list[str]) -> bool:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return False
    for index, item in enumerate(value):
        _text(item, f"{path}[{index}]", errors)
    return True


def _required(record: Mapping[str, Any], key: str, errors: list[str]) -> Any:
    if key not in record:
        errors.append(f"missing required field: {key}")
        return None
    return record[key]


def _origin_matches(event: Mapping[str, Any], session_id: str, product_id: str,
                    path: str, errors: list[str]) -> None:
    for key, expected in (("session_id", session_id), ("product_id", product_id)):
        if key in event and event[key] != expected:
            errors.append(f"{path}.{key} does not match record origin")


def _event_value(event: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in event:
            return event[key]
    return None


def validate_investigation(record: Any) -> list[str]:
    """Return deterministic validation errors for an investigation record.

    The function never changes ``record`` and returns errors for null or
    malformed input instead of raising.  Unknown fields are retained for
    forward-compatible event metadata.
    """

    errors: list[str] = []
    if not isinstance(record, Mapping):
        return ["record must be an object"]

    required_fields = (
        "schema_version", "session_id", "product_id", "customer_request",
        "current_goal", "steps", "knowledge", "customer_outcome",
        "handoff_reason", "risk", "unknowns", "identity", "evidence",
        "recipient", "core_decision_ref",
    )
    values = {key: _required(record, key, errors) for key in required_fields}

    if "schema_version" in record and record["schema_version"] != CONTRACT_VERSION:
        errors.append(f"schema_version must be {CONTRACT_VERSION!r}")
    session_id = values["session_id"] if _text(values["session_id"], "session_id", errors) else ""
    product_id = values["product_id"] if _text(values["product_id"], "product_id", errors) else ""

    request = values["customer_request"]
    request_ok = _mapping(request, "customer_request", errors)
    request_text = request_ref = ""
    if request_ok:
        request_text_value = request.get("text")
        request_ref_value = request.get("evidence_ref")
        if _text(request_text_value, "customer_request.text", errors):
            request_text = request_text_value
        if _text(request_ref_value, "customer_request.evidence_ref", errors):
            request_ref = request_ref_value

    goal = values["current_goal"]
    if _mapping(goal, "current_goal", errors):
        _text(goal.get("text"), "current_goal.text", errors)
        source = goal.get("source")
        if not isinstance(source, str) or source not in _GOAL_SOURCES:
            errors.append("current_goal.source must be 'model_interpretation' or 'customer'")

    outcome = values["customer_outcome"]
    if not isinstance(outcome, str) or outcome not in _OUTCOMES:
        errors.append("customer_outcome has an invalid value")
    _text(values["handoff_reason"], "handoff_reason", errors)
    _string_list(values["unknowns"], "unknowns", errors)

    risk = values["risk"]
    if _mapping(risk, "risk", errors):
        if not isinstance(risk.get("level"), str) or risk.get("level") not in _RISK_LEVELS:
            errors.append("risk.level has an invalid value")
        signals = risk.get("signals")
        if not isinstance(signals, list):
            errors.append("risk.signals must be a list")
        else:
            for index, signal in enumerate(signals):
                path = f"risk.signals[{index}]"
                if not _mapping(signal, path, errors):
                    continue
                if "signal_id" in signal:
                    _text(signal.get("signal_id"), f"{path}.signal_id", errors)
                if "risk" in signal:
                    signal_risk = signal.get("risk")
                    if not isinstance(signal_risk, str) or signal_risk not in _RISK_LEVELS:
                        errors.append(f"{path}.risk has an invalid value")
                if "reason" in signal:
                    _text(signal.get("reason"), f"{path}.reason", errors)
                if "source" in signal:
                    source = signal.get("source")
                    if not isinstance(source, str) or source not in _RISK_SIGNAL_SOURCES:
                        errors.append(f"{path}.source has an invalid value")

    identity = values["identity"]
    if _mapping(identity, "identity", errors):
        status = identity.get("status")
        if not isinstance(status, str) or status not in _IDENTITY_STATUSES:
            errors.append("identity.status has an invalid value")
        value = identity.get("value")
        if status == "supplied":
            _text(value, "identity.value", errors)
            _text(identity.get("evidence_handle"), "identity.evidence_handle", errors)
        elif value is not None:
            errors.append("identity.value must be omitted unless identity.status is 'supplied'")
        elif identity.get("evidence_handle") is not None:
            errors.append(
                "identity.evidence_handle must be omitted unless identity.status is 'supplied'"
            )

    recipient = values["recipient"]
    if not _mapping(recipient, "recipient", errors) or dict(recipient) != _RECIPIENT:
        errors.append("recipient must be local_support_review with external_delivery not_requested")

    evidence = values["evidence"]
    evidence_items = evidence if isinstance(evidence, list) else []
    events: dict[str, Mapping[str, Any]] = {}
    if isinstance(evidence, list):
        for index, event in enumerate(evidence):
            path = f"evidence[{index}]"
            if not _mapping(event, path, errors):
                continue
            event_id = event.get("event_id")
            if not _text(event_id, f"{path}.event_id", errors):
                continue
            if event_id in events:
                errors.append(f"duplicate evidence event_id: {event_id}")
                continue
            events[event_id] = event
            _text(event.get("kind"), f"{path}.kind", errors)
            _origin_matches(event, session_id, product_id, path, errors)
    else:
        errors.append("evidence must be a list")

    if request_ref and request_ref in events:
        event = events[request_ref]
        if event.get("kind") != "customer_question":
            errors.append("customer_request.evidence_ref must reference a customer_question event")
        if event.get("text") != request_text:
            errors.append("customer_request.text must exactly match its customer_question evidence")
    elif request_ref:
        errors.append("customer_request.evidence_ref does not resolve to evidence")

    steps = values["steps"]
    step_keys: set[tuple[str | None, str]] = set()
    if isinstance(steps, list):
        for index, step in enumerate(steps):
            path = f"steps[{index}]"
            if not _mapping(step, path, errors):
                continue
            step_id = step.get("step_id")
            if not _text(step_id, f"{path}.step_id", errors):
                continue
            run_id = step.get("run_id")
            if run_id is not None and not _text(run_id, f"{path}.run_id", errors):
                run_id = None
            step_key = (run_id, step_id)
            if step_key in step_keys:
                errors.append(f"duplicate step identity: run_id={run_id!r}, step_id={step_id!r}")
            step_keys.add(step_key)
            _text(step.get("target_id"), f"{path}.target_id", errors)
            if not isinstance(step.get("status"), str) or step.get("status") not in _STEP_STATUSES:
                errors.append(f"{path}.status has an invalid value")
            refs = step.get("evidence_refs")
            if not isinstance(refs, list):
                errors.append(f"{path}.evidence_refs must be a list")
                refs = []
            for ref_index, ref in enumerate(refs):
                if not _text(ref, f"{path}.evidence_refs[{ref_index}]", errors):
                    continue
                if ref not in events:
                    errors.append(f"{path}.evidence_refs[{ref_index}] does not resolve to evidence")
            _text(step.get("result"), f"{path}.result", errors)

            if step.get("status") == "observed":
                matching = [
                    events[ref] for ref in refs
                    if isinstance(ref, str)
                    and ref in events
                    and events[ref].get("kind") == "guidance_step_observed"
                    and events[ref].get("step_id") == step_id
                    and events[ref].get("target_id") == step.get("target_id")
                    and (run_id is None or events[ref].get("run_id") == run_id)
                ]
                if not matching:
                    errors.append(
                        f"{path} must cite guidance_step_observed evidence with matching step_id and target_id"
                    )
                elif all(event.get("predicate") != step.get("result") for event in matching):
                    errors.append(f"{path}.result must match the observed event predicate")
    else:
        errors.append("steps must be a list")

    knowledge = values["knowledge"]
    if isinstance(knowledge, list):
        for index, item in enumerate(knowledge):
            path = f"knowledge[{index}]"
            if not _mapping(item, path, errors):
                continue
            refs = [
                item.get(key)
                for key in ("pin", "source_ref", "article_id", "source_url")
                if item.get(key) is not None
            ]
            if not refs or not any(isinstance(ref, str) and ref.strip() for ref in refs):
                errors.append(f"{path} must include a non-empty pin or source_ref")
            if "evidence_ref" in item:
                evidence_ref = item["evidence_ref"]
                if not _text(evidence_ref, f"{path}.evidence_ref", errors):
                    continue
                event = events.get(evidence_ref)
                if event is None:
                    errors.append(f"{path}.evidence_ref does not resolve to evidence")
                elif event.get("kind") != "knowledge_selected":
                    errors.append(f"{path}.evidence_ref must reference a knowledge_selected event")
                else:
                    for key in (
                        "pin", "source_ref", "article_id", "revision",
                        "content_hash", "product_id", "source_url",
                    ):
                        if key in item and item[key] is not None and event.get(key) != item[key]:
                            errors.append(f"{path}.{key} does not match its knowledge evidence")
    else:
        errors.append("knowledge must be a list")

    confirmed_facts: list[Mapping[str, Any]] | None = None
    if "confirmed_facts" in record:
        raw_confirmed_facts = record["confirmed_facts"]
        if not isinstance(raw_confirmed_facts, list):
            errors.append("confirmed_facts must be a list")
        else:
            confirmed_facts = []
            for index, fact in enumerate(raw_confirmed_facts):
                if not _mapping(fact, f"confirmed_facts[{index}]", errors):
                    continue
                confirmed_facts.append(fact)
                if "evidence_handle" in fact:
                    _text(
                        fact["evidence_handle"],
                        f"confirmed_facts[{index}].evidence_handle",
                        errors,
                    )

    if isinstance(identity, Mapping) and identity.get("status") == "supplied":
        identity_value = identity.get("value")
        identity_handle = identity.get("evidence_handle")
        matching_fact = next(
            (
                fact for fact in (confirmed_facts or [])
                if fact.get("claim") == "customer_account_identity"
                and fact.get("value") == identity_value
                and fact.get("evidence_handle") == identity_handle
            ),
            None,
        )
        if matching_fact is None:
            errors.append(
                "supplied identity must match a confirmed_facts customer_account_identity fact"
            )

    if outcome == "not_resolved":
        confirmation_ref = record.get("confirmation_ref")
        guidance_run_id = record.get("guidance_run_id")
        confirmation_event = None
        if not _text(confirmation_ref, "confirmation_ref", errors):
            confirmation_ref = None
        if not _text(guidance_run_id, "guidance_run_id", errors):
            guidance_run_id = None
        if confirmation_ref is not None:
            confirmation_event = events.get(confirmation_ref)
            if confirmation_event is None:
                errors.append("confirmation_ref does not resolve to customer_confirmation evidence")
            elif confirmation_event.get("kind") != "customer_confirmation":
                errors.append("confirmation_ref must reference a customer_confirmation event")
        if confirmation_event is not None and guidance_run_id is not None:
            if confirmation_event.get("run_id") != guidance_run_id:
                errors.append("customer confirmation run_id must match guidance_run_id")
            if str(_event_value(confirmation_event, ("answer", "value"))).strip().lower() != "no":
                errors.append("not_resolved requires selected customer_confirmation answer 'no'")
            same_run_confirmations = [
                (index, event) for index, event in enumerate(evidence_items)
                if isinstance(event, Mapping)
                and event.get("kind") == "customer_confirmation"
                and event.get("run_id") == guidance_run_id
            ]
            if same_run_confirmations and same_run_confirmations[-1][1].get("event_id") != confirmation_ref:
                errors.append("confirmation_ref must select the latest customer_confirmation for guidance_run_id")
            confirmation_index = next(
                (index for index, event in enumerate(evidence_items)
                 if isinstance(event, Mapping) and event.get("event_id") == confirmation_ref),
                None,
            )
            observed_indices = [
                index for index, event in enumerate(evidence_items)
                if isinstance(event, Mapping)
                and event.get("kind") == "guidance_step_observed"
                and event.get("run_id") == guidance_run_id
            ]
            if confirmation_index is not None and observed_indices and confirmation_index <= max(observed_indices):
                errors.append("customer confirmation must follow observed steps for guidance_run_id")

    core_decision_ref = values["core_decision_ref"]
    if _text(core_decision_ref, "core_decision_ref", errors):
        decision_event = events.get(core_decision_ref)
        if decision_event is None:
            errors.append("core_decision_ref does not resolve to evidence")
        elif decision_event.get("kind") != "support_decision":
            errors.append("core_decision_ref must reference a support_decision event")
        elif isinstance(risk, Mapping):
            if decision_event.get("current_risk") != risk.get("level"):
                errors.append("support_decision.current_risk must match risk.level")
            if decision_event.get("risk_signals") != risk.get("signals"):
                errors.append("support_decision.risk_signals must match risk.signals")
            if decision_event.get("confirmed_facts") != record.get("confirmed_facts"):
                errors.append("support_decision.confirmed_facts must match confirmed_facts")

    return errors


__all__ = ["CONTRACT_VERSION", "validate_investigation"]
