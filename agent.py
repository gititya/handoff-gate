"""AI agent — works a B2C disputed-charge case and writes a handoff note.

Live Claude call every run. The AI is naturally tempted to guess early
(fraud? trial conversion? duplicate?) — the thin/incomplete handoff it
produces is the artifact the gate grades.
"""
from __future__ import annotations

import json
from typing import Any

from _api import get_api_key
from contracts import ALL_REQUIRED_KEYS, ALL_REQUIRED_KEYS_B


MODEL = "claude-haiku-4-5-20251001"
ENGINEERING_OUTPUT_KEYS = ALL_REQUIRED_KEYS_B + ["open_unknowns"]


def build_transcript_text(turns: list[dict[str, Any]]) -> str:
    lines = []
    for t in turns:
        speaker = t.get("speaker", "unknown").upper()
        lines.append(f"[{speaker}] {t['text']}")
    return "\n".join(lines)


# The agent fills the SAME field names the gate checks (single source of truth
# in contracts.py) so completeness is graded on content, not key-name luck.
# The prompt stays undirected on quality — a rushed agent still leaves the hard
# fields blank or omitted, which is the real signal the gate catches.
SYSTEM_PROMPT = f"""\
You are a billing support AI agent handling a B2C subscription dispute.
The customer contacted support about a charge they don't recognize.
You've reviewed the conversation and now need to write a quick handoff
note for the human agent taking over.

Return ONLY a JSON object using these keys:
{json.dumps(ALL_REQUIRED_KEYS)}

Fill in what you can from the conversation. You don't need to be
exhaustive — just get the key points across so the human can pick it up.
If you don't have something, leave that key out."""


def work_case(fixture: dict[str, Any]) -> dict[str, Any]:
    """Have Claude work the case and produce a candidate handoff note."""
    transcript = build_transcript_text(fixture["transcript_turns"])

    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key())
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here is the support conversation transcript:\n\n"
                    f"{transcript}\n\n"
                    f"Write the handoff note for the human billing agent."
                ),
            }
        ],
    )

    raw_text = response.content[0].text
    return {
        "candidate_handoff": _parse_handoff(raw_text),
        "raw_response": raw_text,
        "model": MODEL,
    }


def _parse_handoff(raw_text: str) -> dict[str, Any]:
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        return {"_raw": raw_text, "_parse_error": True}


# Flow 2: a human support agent (aided by the copilot) escalates a B2B product
# bug to engineering. Prompt stays undirected on thoroughness — a rushed agent
# still drops the system-level detail engineering needs, which the gate catches.
SYSTEM_PROMPT_ENGINEERING = f"""\
You are a support agent escalating a B2B product issue to the engineering team.
You've worked the case as far as support tools allow and now write a quick
handoff note for engineering.

Return ONLY a JSON object using these keys:
{json.dumps(ENGINEERING_OUTPUT_KEYS)}

Fill in what you can from the conversation and the case state. You don't need to
be exhaustive — just get engineering what they need to pick it up. If you don't
have something, leave that key out. If the cause is still open, put the remaining
branches in open_unknowns."""


def work_engineering_handoff(
    transcript_turns: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Have Claude write a candidate human→engineering handoff (Contract B).

    Given the transcript + the copilot's reconstructed state (facts / ruled-out /
    final_cause), produce a thin engineering escalation note the gate then grades.
    """
    transcript = build_transcript_text(transcript_turns)
    state_summary = {
        "facts": state.get("facts", []),
        "ruled_out_branches": state.get("ruled_out_branches", []),
        "candidate_branches": state.get("candidate_branches", []),
        "final_cause": state.get("final_cause", ""),
        "next_check": state.get("next_check", ""),
    }

    import anthropic

    client = anthropic.Anthropic(api_key=get_api_key())
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT_ENGINEERING,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Support conversation transcript:\n\n{transcript}\n\n"
                    f"Reconstructed case state (from the co-pilot):\n"
                    f"{json.dumps(state_summary, indent=2)}\n\n"
                    f"Write the handoff note for the engineering team."
                ),
            }
        ],
    )

    raw_text = response.content[0].text
    return {
        "candidate_handoff": _parse_handoff(raw_text),
        "raw_response": raw_text,
        "model": MODEL,
    }
