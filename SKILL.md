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
End-to-end hero demo built and verified. Branch `feat/phase-1-hero-demo`, PR #1 open (`gititya/handoff-engine/pull/1`). Commit `d30d845`.

**Files shipped:** `engine.py` · `contracts.py` · `router.py` · `agent.py` · `grade.py` · `gate.py` · `demo.py` · `pyproject.toml`

**Verified runs:**
- `call_61772f4783 --skip-judge`: ~10s, BLOCKED (13 missing fields), corrected note generated, RELEASED ✓
- `call_3835c4f220 --skip-judge`: ~9s, BLOCKED, lenient + BORDERLINE, corrected note uses "unexplained/fraud-flagged" + explicit `open_state_reason`, RELEASED ✓
- `call_61772f4783` (MLX judge): ~44s, BLOCKED (judge passed, field-presence check caught it — both layers add value), corrected, RELEASED ✓

**Model rule:** Sonnet built, Opus reviews (next step: `/model opus` → `/review`).

### Phase 2 — Contract B + human→eng hop ⬜ DEFERRED (blocked on data)
**Contract B is a B2C PRODUCT-BUG handoff, not billing** (Contracts.md 69–86). No B2C product-bug data exists: the generator pack is B2C-billing-only, and the `support-copilot` fixtures are **B2B** (webhook/API/workspace) — explicitly off-limits per CLAUDE.md. Two earlier wrong turns (reading the generator's billing-escalation block as Contract B; then sourcing B2B fixtures) were rejected. Contract B waits until B2C product-bug cases + a `human_to_engineering` answer key are generated upstream. See memory `contract-b-answer-key-debt`.

### Phase 3 — Weekly roll-up ✅ DONE (2026-06-25)
`rollup.py` batches the gate over the 10 B2C cases (Contract A). Branch `feat/phase-3-rollup`. Reports pass rate + top recurring gap + borderline count; saves `outputs/rollup_*.json`.
- **Grading fix (load-bearing):** the agent now fills the SAME field names the gate checks — `agent.py` imports `ALL_REQUIRED_KEYS` from `contracts.py` (single source of truth) so completeness is graded on content, not key-name luck. Before the fix the roll-up was noise (0/10, 11–13 phantom gaps from key-name mismatch). After: tight, real signal.
- **Real finding:** recurring gap = `account_id` (10/10) + `subscription_id` (9/10) — internal system IDs that live in the account record, not the customer transcript the AI sees. AI writes readable prose handoffs but drops the structured identifiers; the gate catches it and fills from the reconstruction. This also makes Phase 1's named gaps trustworthy (hero case now blocks on the 2 real IDs, not 13 phantom fields).

---

## SUPERSEDED — 2026-06-26 · Integration stance (Contract B is now B2B)

> Append-only update. The Phase 2 entry above (and the "B2B off-limits" line) is **history, not current instruction.** This note governs.

The portfolio decision changed from **isolation** ("engine reuse only, don't touch realtime's B2B fixtures") to **integration** (make the repos work together as one pipeline via a thin runner). Under that stance:

- **Contract B is now a B2B product-bug human→engineering handoff** (not B2C). The realtime B2B fixtures are **in-bounds** — they are the natural Flow-2 source because the copilot only reconstructs that domain. The old "off-limits per CLAUDE.md" guard was an isolation-era artifact and is retired (see the CLAUDE.md SUPERSEDED note).
- **The copilot (`support-copilot/run.py::run_fixture`) is the live Flow-2 reconstruction engine** — called by the runner, not re-implemented here.
- **Built this session (Phase 1 of the integration plan):**
  - Decoupled `engine.py` — removed the hard reach into the generator's export dir; added `reconstruct_fixture(fixture)` + `HANDOFF_FIXTURE_BASE` override so the gate is *handed* fixtures.
  - `contracts.py` — locked **Contract B** (`ALWAYS_REQUIRED_KEYS_B`, `check_handoff_b`); reuses `derive_leniency` (strict when evidence pinned the cause, lenient-but-must-name-open-unknowns otherwise).
  - `contract_b_anchors/` — 3 hand-authored gold keys (derived from each fixture's evidence): 2 lenient (conflicting-systems, workspace handoff) + 1 strict (webhook-auth). Verified pass; thin/silent + missing-cause notes verified blocked.
  - `gate.py` — judge is now **soft evidence + human-review flag, not a hard blocker**; mechanical contract check is the sole release gate (keeps local-MLX availability out of the release path). `run_gate(check_fn=...)` accepts Contract B. Corrected-note generation labeled **oracle-assisted**.
- **Still pending:** the runner (Phase 2 of the plan — `customer-support-ai-os`), the generator's B2B product-bug scenario (Phase 3, scales the anchor set). Plan: `~/.claude/plans/breezy-petting-thimble.md`.

- **2026-06-26 · Contract B lenient arm — middle path + LLM-extractor deferred.** Adversarial review (GPT-5.5) found the lenient arm false-blocked honest *warm* escalations when open branches were named in `likely_cause` prose but `open_unknowns` was empty (grading format, not substance). `check_handoff_b` now accepts open branches from **either** `open_unknowns` **or** prose (`_names_open_state_in_prose`, a deterministic stopgap), and **soft-flags** prose-only via `GapReport.structure_warning` (routes to human, never blocks); cold escalations still block. The LLM-extractor seam that would replace the stopgap is **deferred and data-gated** — build it only when prose-only passes accumulate (analytics in `customer-support-ai-os/outputs/gate_analytics.jsonl`). Rationale + build trigger: `docs/llm-extractor-deferral.md`.

---

## 2026-06-26 · Realism hardening pass — Codex branch

Branch `codex/harden-support-realism` hardens the gate without changing the deterministic pass/block thesis:
- `gate.py` adds trusted-source correction mode for Contract A, explicit override reasons (`sla_risk`, `vip_customer`, `active_incident`, `missing_tool_access`, `engineering_owned_diagnostic`, `customer_impact`), support outcome labels, and lazy Anthropic import so deterministic gate tests do not require the API package. Oracle correction remains labeled lab-only.
- `contracts.py` strengthens Contract B evidence checks: evidence handles, ruled-out branches, strict causes, and open unknowns must be supported by reconstructed/expected evidence; prose-only open branches still pass only when they name real open branches, otherwise checklist-shaped garbage blocks.
- `contract_b_anchors/` now includes 8 additional ugly B2B anchors for incomplete logs, wrong first diagnosis, known-issue suspicion, missing repro/SLA pressure, tool-access limitation, active incident, conflicting evidence, and VIP pressure.
- `rollup.py` reports support-language outcomes (`pass_clean`, `pass_prose_flagged`, `blocked`, `override_required`) and operational gap labels.

Verification: `python3 -m pytest tests/ -q` could not run because `pytest` is not installed in this shell; `python3 -m compileall .` passed, and all `tests/test_contracts.py` test functions passed via direct Python invocation.

---

## 2026-06-26 · Flow 2 live batch runner — Codex branch

Branch `codex/harden-support-realism` now includes a live Contract B batch path:
- `b2b_rollup.py` runs the human→engineering flow across every `contract_b_anchors/` case: anchor support context → live `work_engineering_handoff` call → deterministic `check_handoff_b` gate → support-language rollup artifact.
- `agent.py` now asks the engineering handoff agent to include `open_unknowns` when the cause is still open, and imports the Anthropic SDK lazily so deterministic tests do not require API dependencies.
- `contracts.py` accepts `candidate_branches` as a structure-warning alias for `open_unknowns` when the branches match the reconstructed open state; generic unsupported branches still block.
- Live run: `.venv/bin/python b2b_rollup.py` produced `outputs/b2b_rollup_20260626_154710.json`, `11/11` warm handoffs accepted, `0` blocked, `0` human-review warnings after the prompt/schema fix.

Verification: direct invocation of all `tests/test_contracts.py` test functions passed; `.venv/bin/python -m compileall agent.py b2b_rollup.py contracts.py tests/test_contracts.py` passed; `git diff --check` passed.

---

## 2026-06-26 · Flow 2 hostile harness — Codex branch

`b2b_rollup.py` now supports agent-facing profiles so Flow 2 can test non-spoon-fed handoffs:
- `clean` preserves the previous gold-evidence baseline.
- `evidence_starved` withholds exact evidence handles / ruled-out branches / open unknowns from the agent.
- `distractor_wrong_cause` tempts a strict case toward a plausible but wrong cause while the gate keeps the true final cause.
- `cold_dump` gives mostly complaint + urgency with no structured diagnosis.
- `hostile` runs the fixed 3-case set: `level2_tool_access_limitation` / `level3_misrouted_ratelimit_actually_webhook_auth` / `level2_unresolved_workspace_handoff`.

Live hostile run: `.venv/bin/python b2b_rollup.py --profile hostile` produced `outputs/b2b_rollup_20260626_160547.json`, `0/3` pass, `3/3` blocked. The intended support failures surfaced: missing evidence handles, unsupported ruled-out branches, unsupported open branches, and wrong likely cause (`likely_cause_not_supported`). This addresses the Opus critique that the earlier `11/11` live Flow 2 run was overfed by the harness.

Verification: direct invocation of all `tests/test_contracts.py` test functions passed after adding hostile profile tests.

---

## 2026-06-26 · Closeout — honest defaults (PR #5, #6 merged to main)

Build is **done**. Two PRs merged to `main`:
- **PR #5** (`codex/harden-support-realism`): evidence grounding (`evidence_gaps`), `trusted_sources` correction, override lane (`override_required`), 8 ugly B2B anchors + hostile harness, README.
- **PR #6** (`chore/honesty-defaults`): `run_gate` defaults to `trusted_sources` (fills only system-of-record facts, **never invents a diagnosis**; oracle/answer-key is explicit eval-lab only); `b2b_rollup.py` defaults to `audit` (clean + hostile in one headline).

Final state: 26 unit tests pass on `main`. Live audit = `11/14` (11 clean warm + 3 hostile blocked). Flow 1 still releases (identity filled from records). Honesty bar written in README ("What done/honest means here").

Known, accepted limitations (disclosed, not hidden): grounding + hostile harness are **Contract B only** — Flow 1/Contract A is presence-only; `gate_analytics.jsonl` is logged but not yet aggregated (extractor build-trigger is manual for now). Both are deferrable, not blockers. The word-match grounding stays a labeled stopgap (smartening it = the deferred LLM-extractor).
