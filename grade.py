"""Grade a candidate handoff using the existing handoff_completeness judge.

Imports the eval-judges pipeline (build_prompt → run_inference → parse_verdict).
Runs local MLX (Qwen3-4B-4bit) — free, no API call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

EVAL_JUDGES_SRC = str(
    Path(__file__).resolve().parent.parent / "experiments/eval-judges/src"
)
EVAL_JUDGES_ROOT = str(
    Path(__file__).resolve().parent.parent / "experiments/eval-judges"
)

if EVAL_JUDGES_SRC not in sys.path:
    sys.path.insert(0, EVAL_JUDGES_SRC)
if EVAL_JUDGES_ROOT not in sys.path:
    sys.path.insert(0, EVAL_JUDGES_ROOT)

from eval_judges.adapter import run_inference
from eval_judges.prompt_builder import build_prompt
from eval_judges.parser import parse_verdict

PRIMARY_MODEL = "mlx-community/Qwen3-4B-4bit"
JUDGE_ID = "handoff_completeness"
RUBRIC = "detailed_with_examples"


# Judge adapter contract: the handoff_completeness judge expects
# {ticket, agent_response, handoff_note, tool_context}. These defaults describe
# Flow 1 (B2C billing); Flow 2 passes a B2B product-bug ticket/summary.
TICKET_A = "B2C disputed charge case"
AGENT_SUMMARY_A = "Agent worked the case and produced a handoff note."


def build_judge_example(
    transcript_turns: list[dict[str, Any]],
    candidate_handoff: dict[str, Any],
    reconstructed_state: dict[str, Any],
    ticket_label: str = TICKET_A,
    agent_summary: str = AGENT_SUMMARY_A,
) -> dict[str, Any]:
    transcript_text = "\n".join(
        f"[{t.get('speaker', 'unknown').upper()}] {t['text']}"
        for t in transcript_turns
    )

    handoff_text = json.dumps(candidate_handoff, indent=2)

    state_summary = {
        "facts": reconstructed_state.get("facts", []),
        "unknowns": reconstructed_state.get("unknowns", []),
        "candidate_branches": reconstructed_state.get("candidate_branches", []),
        "ruled_out_branches": reconstructed_state.get("ruled_out_branches", []),
        "final_cause": reconstructed_state.get("final_cause", ""),
    }

    return {
        "judge_id": JUDGE_ID,
        "example_id": reconstructed_state.get("case_id", "unknown"),
        "label": True,
        "ticket": f"{ticket_label}: {reconstructed_state.get('case_id', '')}",
        "agent_response": agent_summary,
        "conversation": transcript_text,
        "handoff_note": handoff_text,
        "tool_context": json.dumps(state_summary),
        "metadata": {"difficulty": "hard"},
    }


def grade_handoff(
    transcript_turns: list[dict[str, Any]],
    candidate_handoff: dict[str, Any],
    reconstructed_state: dict[str, Any],
    ticket_label: str = TICKET_A,
    agent_summary: str = AGENT_SUMMARY_A,
) -> dict[str, Any]:
    """Grade a candidate handoff note using the local MLX judge."""
    example = build_judge_example(
        transcript_turns, candidate_handoff, reconstructed_state,
        ticket_label=ticket_label, agent_summary=agent_summary,
    )
    prompt = build_prompt(JUDGE_ID, RUBRIC, example)
    raw = run_inference(PRIMARY_MODEL, prompt)
    verdict, errors = parse_verdict(raw)

    return {
        "verdict": verdict,
        "parse_errors": errors,
        "raw_output": raw,
    }
