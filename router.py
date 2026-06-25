"""Destination router — Step 2.

Routes to the right contract based on destination + issue type.
Phase 1: only AI→human + disputed_charge → Contract A.
Phase 2 adds human→engineering → Contract B.
"""
from __future__ import annotations

from typing import Any


def route(fixture: dict[str, Any]) -> dict[str, Any]:
    scenario = fixture.get("scenario", "")
    resolution = fixture.get("resolution_type", "")

    destination = "ai_to_human"
    issue_type = "disputed_charge" if "billing" in scenario else "unknown"

    # Phase 2: escalated cases also fire human→engineering (Contract B)
    contract_b_applicable = resolution == "escalated"

    return {
        "destination": destination,
        "issue_type": issue_type,
        "contract": "A",
        "contract_b_applicable": contract_b_applicable,
    }
