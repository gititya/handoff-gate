"""Replay the authored policy examples without model calls or delivery."""
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from contracts import check_handoff_b
from test_batch_review import limited_case


def main():
    rows = []
    for name, expected_pass in [
        ("honest_access_limit", True),
        ("no_record_of_access_limit", False),
        ("generic_investigation_request", False),
        ("missing_impact", False),
        ("invented_extra_evidence", False),
    ]:
        candidate, expected, state = limited_case()
        if name == "no_record_of_access_limit":
            state.pop("diagnostic_limit")
        elif name == "generic_investigation_request":
            candidate["specific_ask"] = "Please investigate"
        elif name == "missing_impact":
            candidate["impact_urgency"] = ""
        elif name == "invented_extra_evidence":
            candidate["evidence_handles"].append("invented_xyz_record")
        result = check_handoff_b(candidate, expected, state)
        rows.append(dict(case=name, expected_pass=expected_pass, actual_pass=result.passed,
                         missing_fields=result.missing_fields, evidence_gaps=result.evidence_gaps,
                         note=deepcopy(candidate)))
    valid = [r for r in rows if r["expected_pass"]]
    invalid = [r for r in rows if not r["expected_pass"]]
    report = dict(kind="authored_development_examples_not_independent_eval", cases=rows,
                  acceptable_notes_held=sum(not r["actual_pass"] for r in valid), acceptable_notes=len(valid),
                  bad_notes_accepted=sum(r["actual_pass"] for r in invalid), bad_notes=len(invalid),
                  limit="These examples test the agreed rules; they do not estimate real-world accuracy.")
    print(json.dumps(report, indent=2))
    assert all(r["actual_pass"] == r["expected_pass"] for r in rows)


if __name__ == "__main__":
    main()
