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

### Phase 2 — Contract B + human→eng hop ⬜ DEFERRED (blocked on data)
**Contract B is a B2C PRODUCT-BUG handoff, not billing** (Contracts.md 69–86). No B2C product-bug data exists: the generator pack is B2C-billing-only, and the `real-time_support_Updated` fixtures are **B2B** (webhook/API/workspace) — explicitly off-limits per CLAUDE.md. Two earlier wrong turns (reading the generator's billing-escalation block as Contract B; then sourcing B2B fixtures) were rejected. Contract B waits until B2C product-bug cases + a `human_to_engineering` answer key are generated upstream. See memory `contract-b-answer-key-debt`.

### Phase 3 — Weekly roll-up ✅ DONE (2026-06-25)
`rollup.py` batches the gate over the 10 B2C cases (Contract A). Branch `feat/phase-3-rollup`. Reports pass rate + top recurring gap + borderline count; saves `outputs/rollup_*.json`.
- **Grading fix (load-bearing):** the agent now fills the SAME field names the gate checks — `agent.py` imports `ALL_REQUIRED_KEYS` from `contracts.py` (single source of truth) so completeness is graded on content, not key-name luck. Before the fix the roll-up was noise (0/10, 11–13 phantom gaps from key-name mismatch). After: tight, real signal.
- **Real finding:** recurring gap = `account_id` (10/10) + `subscription_id` (9/10) — internal system IDs that live in the account record, not the customer transcript the AI sees. AI writes readable prose handoffs but drops the structured identifiers; the gate catches it and fills from the reconstruction. This also makes Phase 1's named gaps trustworthy (hero case now blocks on the 2 real IDs, not 13 phantom fields).
