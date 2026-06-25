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

### Phase 0.5 — Anchor case ✅ DONE (2026-06-25)
Confirmed anchor cases from the live pack (no regeneration):
- **Hero:** `call_61772f4783` — trial-conversion / `resolved`, `root_cause_evidence_seen=True`, `final_cause` pinned → strict arm (confirms gate demands cause + confidence).
- **Contrast:** `call_3835c4f220` — fraud-flagged, `final_cause=""`, evidence open → lenient arm + `borderline` flag (gate must NOT demand confirmed cause, must demand open-state honesty).

### Phase 1 — Hero demo ✅ DONE (2026-06-25)
End-to-end hero demo built and verified. Branch `feat/phase-1-hero-demo`, PR #1 open (`gititya/handoff_agent/pull/1`). Commit `d30d845`.

**Files shipped:** `engine.py` · `contracts.py` · `router.py` · `agent.py` · `grade.py` · `gate.py` · `demo.py` · `pyproject.toml`

**Verified runs:**
- `call_61772f4783 --skip-judge`: ~10s, BLOCKED (13 missing fields), corrected note generated, RELEASED ✓
- `call_3835c4f220 --skip-judge`: ~9s, BLOCKED, lenient + BORDERLINE, corrected note uses "unexplained/fraud-flagged" + explicit `open_state_reason`, RELEASED ✓
- `call_61772f4783` (MLX judge): ~44s, BLOCKED (judge passed, field-presence check caught it — both layers add value), corrected, RELEASED ✓

**Model rule:** Sonnet built, Opus reviews (next step: `/model opus` → `/review`).

### Phase 2 — Contract B + human→eng hop ⬜ NOT STARTED
Author + lock Contract B; add its router branch. Same gate, different checklist.
