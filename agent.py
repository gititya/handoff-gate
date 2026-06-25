"""AI agent — works a B2C disputed-charge case and writes a handoff note.

Live Claude call every run. The AI is naturally tempted to guess early
(fraud? trial conversion? duplicate?) — the thin/incomplete handoff it
produces is the artifact the gate grades.
"""
from __future__ import annotations

import json
from typing import Any

import anthropic

from _api import get_api_key
from contracts import ALL_REQUIRED_KEYS


MODEL = "claude-haiku-4-5-20251001"


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
    try:
        # Strip markdown fences if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("```", 1)[0]
        handoff = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        handoff = {"_raw": raw_text, "_parse_error": True}

    return {
        "candidate_handoff": handoff,
        "raw_response": raw_text,
        "model": MODEL,
    }
