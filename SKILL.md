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

---

## SUPERSEDED — 2026-06-26 · Integration stance (Contract B is now B2B)

> Append-only update. The Phase 2 entry above (and the "B2B off-limits" line) is **history, not current instruction.** This note governs.

The portfolio decision changed from **isolation** ("engine reuse only, don't touch realtime's B2B fixtures") to **integration** (make the repos work together as one pipeline via a thin runner). Under that stance:

- **Contract B is now a B2B product-bug human→engineering handoff** (not B2C). The realtime B2B fixtures are **in-bounds** — they are the natural Flow-2 source because the copilot only reconstructs that domain. The old "off-limits per CLAUDE.md" guard was an isolation-era artifact and is retired (see the CLAUDE.md SUPERSEDED note).
- **The copilot (`real-time_support_Updated/run.py::run_fixture`) is the live Flow-2 reconstruction engine** — called by the runner, not re-implemented here.
- **Built this session (Phase 1 of the integration plan):**
  - Decoupled `engine.py` — removed the hard reach into the generator's export dir; added `reconstruct_fixture(fixture)` + `HANDOFF_FIXTURE_BASE` override so the gate is *handed* fixtures.
  - `contracts.py` — locked **Contract B** (`ALWAYS_REQUIRED_KEYS_B`, `check_handoff_b`); reuses `derive_leniency` (strict when evidence pinned the cause, lenient-but-must-name-open-unknowns otherwise).
  - `contract_b_anchors/` — 3 hand-authored gold keys (derived from each fixture's evidence): 2 lenient (conflicting-systems, workspace handoff) + 1 strict (webhook-auth). Verified pass; thin/silent + missing-cause notes verified blocked.
  - `gate.py` — judge is now **soft evidence + human-review flag, not a hard blocker**; mechanical contract check is the sole release gate (keeps local-MLX availability out of the release path). `run_gate(check_fn=...)` accepts Contract B. Corrected-note generation labeled **oracle-assisted**.
- **Still pending:** the runner (Phase 2 of the plan — `customer-support-ai-os`), the generator's B2B product-bug scenario (Phase 3, scales the anchor set). Plan: `~/.claude/plans/breezy-petting-thimble.md`.
