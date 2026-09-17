"""Regression checks for observed portfolio-review gaps; no model calls."""
from copy import deepcopy
from test_contracts import _contract_a_expected, _contract_a_state, _complete_handoff, _fixture
from contracts import check_handoff_b
from engine import reconstruct_fixture
from gate import run_gate


def test_answer_key_does_not_fill_missing_operational_record():
    expected = _contract_a_expected()
    candidate = dict(expected)
    candidate.pop("account_id")
    state = _contract_a_state({})
    state.pop("_fixture")
    result = run_gate("missing-source", candidate, expected, state, None)
    assert not result.released
    assert "account_id" not in result.final_handoff


def test_one_supported_handle_does_not_hide_an_invented_handle():
    state = reconstruct_fixture(_fixture(with_cause=False))
    expected = _complete_handoff(open_state=True)
    candidate = deepcopy(expected)
    candidate["evidence_handles"].append("invented_xyz_record")
    assert "evidence_handles_not_supported" in check_handoff_b(candidate, expected, state).evidence_gaps


def test_one_supported_unknown_does_not_hide_an_invented_branch():
    state = reconstruct_fixture(_fixture(with_cause=False))
    expected = _complete_handoff(open_state=True)
    candidate = deepcopy(expected)
    candidate["open_unknowns"].append("invented_xyz_explanation")
    assert "open_unknowns_not_supported" in check_handoff_b(candidate, expected, state).evidence_gaps


def test_unknown_cause_is_allowed_but_unknown_account_is_not_complete():
    expected = _contract_a_expected()
    state = _contract_a_state({})
    state.update(final_cause="", root_cause_evidence_seen=False)
    candidate = dict(expected, likely_cause="unknown", confidence="low")
    assert run_gate("open-cause", candidate, expected, state, None).released
    candidate["account_id"] = "unknown"
    assert not run_gate("unknown-account", candidate, expected, state, None).released


import pytest

@pytest.mark.parametrize("field", ["override_by", "override_recipient", "override_justification"])
def test_urgent_override_requires_accountability(field):
    args = dict(override_reason="active_incident", override_by="rep-7",
                override_recipient="incident on-call", override_justification="Ongoing loss cannot wait")
    args[field] = ""
    with pytest.raises(ValueError):
        run_gate("urgent", {}, {}, {}, None, **args)


def test_urgent_override_records_accountability_without_receipt():
    result = run_gate("urgent", {}, {}, {}, None, override_reason="active_incident",
                      override_by="rep-7", override_recipient="incident on-call",
                      override_justification="Ongoing loss cannot wait")
    assert result.released and result.blocked
    assert result.urgent_override == {"released_by":"rep-7", "recipient":"incident on-call",
        "reason":"Ongoing loss cannot wait", "reason_code":"active_incident"}
    assert result.gap_report.missing_fields


def test_vip_alone_does_not_allow_override():
    with pytest.raises(ValueError):
        run_gate("vip", {}, {}, {}, None, override_reason="vip_customer",
                 override_by="rep-7", override_recipient="support", override_justification="VIP account")


def limited_case():
    state = reconstruct_fixture(_fixture(with_cause=False))
    expected = _complete_handoff(open_state=True)
    candidate = deepcopy(expected)
    candidate["support_ruled_out"] = []
    limit = {"reason":"Support cannot inspect the processing queue", "required_access":"queue inspector",
             "next_check":"Inspect import job 123 for a failed or delayed queue event",
             "evidence_handle":"support queue access denied for job 123"}
    state["facts"].append(limit["evidence_handle"])
    state["diagnostic_limit"] = limit
    candidate["diagnostic_limit"] = deepcopy(limit)
    candidate["specific_ask"] = limit["next_check"]
    return candidate, expected, state


def test_honest_no_access_transfer_passes_without_invented_checks():
    candidate, expected, state = limited_case()
    assert check_handoff_b(candidate, expected, state).passed


def test_claiming_lack_of_access_without_supporting_record_does_not_pass():
    candidate, expected, state = limited_case()
    state.pop("diagnostic_limit")
    assert not check_handoff_b(candidate, expected, state).passed


def test_generic_ask_is_not_a_useful_limited_access_transfer():
    candidate, expected, state = limited_case()
    candidate["specific_ask"] = "Please investigate"
    candidate["diagnostic_limit"]["next_check"] = "Please investigate"
    state["diagnostic_limit"] = deepcopy(candidate["diagnostic_limit"])
    assert not check_handoff_b(candidate, expected, state).passed


def test_no_access_does_not_excuse_missing_impact_or_evidence():
    for key in ("impact_urgency", "evidence_handles", "affected_scope"):
        candidate, expected, state = limited_case()
        candidate[key] = ""
        assert not check_handoff_b(candidate, expected, state).passed


def test_engineering_writer_receives_the_supplied_diagnostic_limit(monkeypatch):
    import sys
    from types import SimpleNamespace
    import agent
    candidate, expected, state = limited_case()
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(text="{}")])
    monkeypatch.setattr(agent, "get_api_key", lambda: "test-placeholder")
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **kw: SimpleNamespace(messages=SimpleNamespace(create=create))))
    agent.work_engineering_handoff([], state)
    import json
    assert json.dumps(state["diagnostic_limit"], indent=2).splitlines()[1].strip() in captured["messages"][0]["content"]
    assert "never invent ruled-out causes" in captured["system"]
