# SKILL.md — Handoff Quality Gate (session/phase state)

Session-level memory for the coding agent. Append-only. Newest phase state at the bottom.

## Current phase: Phase 0 LOCKED → Phase 0.5 next

### Phase 0 — Lock contracts ✅ DONE (2026-06-25)
Contract A (AI→human, B2C disputed charge) was redlined and **verified 1:1 against the live seed pack** (`support-call-generator/exports/b2c_handoff_gate_seed`, 10 hard cases). The locked contract lives in the Obsidian vault: `Customer support/handoff agent/Handoff Quality Gate — Contracts.md`.

Decisions locked (carry into Phase 1):
1. **Field-6 leniency derives from reconstructed evidence, not a label.** Strict when evidence pins a cause; lenient when genuinely open (fraud / contradictory / key fact never arrived); borderline → default lenient but **raise a `borderline` flag**. `resolution_type` is for routing only.
2. **Completeness, not effort.** Cut-short cases aren't penalised for a missing cause, but the note must be explicit about the open state (thin-but-honest passes; thin-and-silent fails). Effort-judging belongs to a different judge.
3. Identity + charge + claim are ALWAYS required.
4. One issue type only (no taxonomy). Contract B (human→eng) deferred to Phase 2.

**Phase 1 carry-forward:** the gate's field-6 leniency MUST read the engine's evidence-sufficiency / final-cause-gating output (Step 1), and emit `borderline` when uncertain. Verified data facts: all 9 Contract A fields map 1:1 to `expected_handoff.ai_to_human`; the two fraud `handoff` cases carry `likely_cause="unexplained / fraud-flagged"`, `confidence="low"` (must PASS).

### Phase 0.5 — Anchor case ⬜ NEXT
Pull the existing pack (do NOT regenerate). Review one hard seed case as the demo anchor (candidate: a fraud-flagged `handoff` case, e.g. `call_3835c4f220` / `call_495b70f18b`). Confirm planted truth + `expected_handoff` are right.

### Phase 1 — Hero demo ⬜ NOT STARTED
Smallest runnable slice, one case, end-to-end (~90s): LLM works case → vendored engine reconstructs → LLM writes handoff → gate grades vs Contract A → if incomplete, **intercept-and-hold** + corrected note. Output: side-by-side thin vs corrected handoff with the gap named. Vendor the engine (no edits to `real-time_support_Updated`); wire the `handoff_completeness` judge; build router + gate. Sonnet builds, Opus reviews.
