# BUILDS.md — Handoff Quality Gate

```yaml
status: "in-progress"
current_state: "Phases 0–1 + 3 shipped. AI→human gate (Contract A) runs end-to-end: reconstruct → route → grade → intercept-and-hold → corrected note → release, plus a weekly roll-up over the 10-case batch."
next_action: "Decide Phase 2: generate B2C product-bug cases upstream so Contract B (human→eng) can be built — it is blocked, not buildable today."
things_to_know:
  - "Contract B is a B2C PRODUCT-BUG hop, not billing; no B2C product-bug data exists yet (generator is billing-only, realtime fixtures are B2B/off-limits)."
  - "Roll-up's real finding: AI handoffs drop structured account/subscription IDs (not present in the transcript it reads); the gate catches + fills them."
  - "Phase 4 (non-technical presentation polish) not started."
updated_at: "2026-06-25"
updated_by: "claude"
```

**Repo:** `gititya/handoff_agent` · **Working dir:** `handoff-engine` · **Status:** Phases 0–1 + 3 shipped; Phase 2 deferred (data blocker); Phase 4 not started

## What this is
The **Handoff Quality Gate** — the capstone of the customer-support AI portfolio. A vendor-neutral checkpoint that, at the moment a support case is handed off (AI→human), reconstructs the case, grades the handoff note against the right checklist, and **blocks it with a corrected version if incomplete**. A quality machine, not a responding machine. It never talks to the customer.

Hero demo: B2C disputed-charge case, AI→human hop. Proof-of-work on synthetic data — not a production product.

## This repo is connective tissue (~80% already exists elsewhere)
| Dependency (`~/Documents/Projects/`) | Role | State |
|---|---|---|
| `support-call-generator` | case factory + `expected_handoff` answer key | ✅ ready (`exports/b2c_handoff_gate_seed`, 10 hard cases) |
| `real-time_support_Updated` | reconstruction **engine** (reuse only, no B2C mode) | ✅ ready |
| `experiments/eval-judges` | `handoff_completeness` judge | ✅ passing on baseline |

The new build here = the bridge: **router (Step 2) + gate decision & corrected-note (Step 4) + weekly roll-up (Step 5)**.

## Status by phase
- **Phase 0 — Lock contracts** ✅ DONE. Contract A locked + verified 1:1 against the seed pack. Key decision: field-6 leniency is **derived from reconstructed evidence**, not a metadata label; gate measures **completeness, not effort**; borderline → lenient-but-flagged. Contract B (human→eng) deferred to Phase 2. Contracts live in the Obsidian vault (`Customer support/handoff agent/Handoff Quality Gate — Contracts.md`).
- **Phase 0.5 — Anchor case** ✅ DONE (2026-06-25). Hero: `call_61772f4783` (strict arm). Contrast: `call_3835c4f220` (lenient + borderline).
- **Phase 1 — Hero demo** ✅ DONE (2026-06-25). End-to-end in <50s (skip-judge) or ~44s (MLX judge). Intercept-and-hold verified on both anchor cases. PR #1 open. Branch: `feat/phase-1-hero-demo`. Commit: `d30d845`.
- **Phase 3 — Weekly roll-up** ✅ DONE (2026-06-25). `rollup.py` over the 10 B2C cases: pass rate + top recurring gap (`account_id`/`subscription_id` — structured IDs the AI drops). Branch `feat/phase-3-rollup`. Fixed a grading flaw: agent now fills the same field names the gate checks (single source of truth), so completeness is real, not key-name noise.
- **Phase 2 — Contract B (human→eng)** ⬜ DEFERRED. It's a B2C *product-bug* hop; no B2C product-bug data exists yet (generator is billing-only; realtime fixtures are B2B/off-limits). Blocked until that data is generated upstream.
- **Phase 4** ⬜ presentation pass.

## What's NOT done (call-outs)
- **Phase 2 — Contract B (human→eng)** ⬜ DEFERRED, blocked on data. It's a B2C *product-bug* hop; no B2C product-bug cases or `human_to_engineering` answer key exist. Needs upstream generation in `support-call-generator`. The realtime B2B fixtures are NOT a valid source (off-limits per CLAUDE.md).
- **Phase 4 — presentation pass** ⬜ not started. Make the demo + roll-up output legible to a non-technical reviewer (before/after handoff, named gap, weekly pattern). Taste-dependent; awaiting direction.
- **Roll-up depth** — single batch over 10 cases, Contract A only; no time-series / multi-week trend (synthetic, one batch).
- **Judge in the roll-up** — defaults OFF for speed; `--with-judge` exists but not the default signal. Field-presence check is the primary gate.
- **Review pass** — Phase 3 was built on Opus directly (user-approved), bypassing the usual "Sonnet builds, Opus reviews" split; no separate `/review` run yet.

## Next action
Decide Phase 2: commission B2C product-bug case generation upstream so Contract B can be built. Everything else for the AI→human hop is shipped.

---

## SUPERSEDED — 2026-06-26 · Contract B is now B2B (integration stance)

> Append-only. The "Phase 2 deferred / B2B off-limits / commission B2C product-bug data" lines above are **history.** This note governs.

Stance moved from isolation to **integration**: the repos are being wired into one pipeline (thin runner). Consequences:
- **Contract B re-spec'd as B2B product-bug (human→engineering).** Realtime's B2B fixtures are now the valid source; the copilot reconstructs them live. The "off-limits" guard is retired.
- **Phase 1 of the integration plan is done in this repo:** decoupled `engine.py`, locked Contract B (`check_handoff_b`) in `contracts.py`, 3 hand-authored gold anchors in `contract_b_anchors/`, judge demoted to soft-flag (mechanical check is the sole blocker), oracle-assist labeled in `gate.py`. All verified deterministically.
- **Pending:** the runner (`customer-support-ai-os`), then the generator B2B scenario to scale beyond the 3 anchors. Full plan: `~/.claude/plans/breezy-petting-thimble.md`.

## SUPERSEDED — 2026-06-26 · Contract B lenient arm middle-path + extractor deferral

> Append-only. Refines the Contract B note above after a GPT-5.5 adversarial review.

The lenient arm was false-blocking honest **warm** escalations that named the open branches in `likely_cause` prose but left `open_unknowns` empty (it graded format, not substance). Fix: `check_handoff_b` accepts open branches from **either** the dedicated list **or** prose, and **soft-flags** prose-only (`GapReport.structure_warning`, routes to human, never blocks); cold escalations still block. The LLM-extractor that would replace the deterministic prose-scan stopgap is **deferred and data-gated** — analytics (`customer-support-ai-os/outputs/gate_analytics.jsonl`) count prose-only passes; build the extractor only when they accumulate. Rationale: `docs/llm-extractor-deferral.md`.

---

## 2026-06-26 — Realism hardening branch

```yaml
status: "in-progress"
current_state: "Branch codex/harden-support-realism adds support-realism hardening: trusted-source correction mode, Contract B evidence support checks, override-required lane, support-language rollup outcomes, and 8 ugly B2B anchors."
next_action: "Have Opus do an adversarial support-realism review of the branch, then decide which review points to apply before PR."
things_to_know:
  - "The deterministic mechanical gate remains the only hard blocker; no LLM extractor was added."
  - "Oracle correction remains lab-only; trusted-source correction refuses to invent unavailable fields."
  - "pytest is not installed in this shell, so verification used compileall plus direct deterministic test invocation."
updated_at: "2026-06-26"
updated_by: "codex"
```

---

## 2026-06-26 — Flow 2 hostile harness

```yaml
status: "in-progress"
current_state: "Branch codex/harden-support-realism now has a hostile Flow 2 harness: clean baseline still exists, but --profile hostile starves/misleads the live engineering handoff agent while the deterministic gate grades against full anchor truth."
next_action: "Ask Opus to review whether the hostile failures are realistic enough, or whether the source transcripts should move upstream into support-call-generator."
things_to_know:
  - "Latest hostile artifact: outputs/b2b_rollup_20260626_160547.json."
  - "Hostile Flow 2 result: 0/3 passed, 3/3 blocked; failures covered missing evidence, unsupported ruled-out/open branches, and wrong likely cause."
  - "This fixes the spoon-feeding harness issue without changing the deterministic gate thesis."
updated_at: "2026-06-26"
updated_by: "codex"
```

---

## 2026-06-26 — Flow 2 live batch runner

```yaml
status: "in-progress"
current_state: "Branch codex/harden-support-realism now runs Flow 2 live at batch scale: b2b_rollup.py turns every B2B anchor into a live generated engineering handoff and gates it with Contract B."
next_action: "Have Opus review whether the 11/11 live Flow 2 pass rate is too friendly, especially whether anchor prompts over-feed the expected evidence."
things_to_know:
  - "Latest live Flow 2 artifact: outputs/b2b_rollup_20260626_154710.json."
  - "Live Flow 2 result: 11/11 warm engineering handoffs accepted, 0 blocked, 0 human-review warnings after the open_unknowns prompt fix."
  - "The hard gate remains deterministic; the LLM only writes the candidate handoff."
updated_at: "2026-06-26"
updated_by: "codex"
```

---

## 2026-06-26 — Closeout (honest defaults)

```yaml
status: "done"
current_state: "Handoff Quality Gate complete on main. Contract A (AI->human) + Contract B (human->engineering) with evidence-derived leniency, deterministic mechanical gate as sole hard blocker, LLMs only at edges. PR #5 (realism hardening) and PR #6 (honest defaults) merged."
next_action: "None required. Optional, deferred: extend grounding to Contract A; aggregate gate_analytics.jsonl to drive the extractor build-trigger. Future features are parked in vault feature-expansion.md."
things_to_know:
  - "Correction defaults to trusted_sources: fills system-of-record facts only, never invents a diagnosis. Oracle (answer-key) is explicit eval-lab only."
  - "b2b_rollup.py defaults to the audit profile (clean + hostile). Latest live audit: 11/14 (11 clean warm + 3 hostile blocked) — headline is intentionally not 100%."
  - "26 unit tests pass on main. Grounding + hostile harness are Contract B only (Flow 1 is presence-only) — disclosed in README."
  - "Word-match grounding is a labeled stopgap; the LLM-extractor remains deferred and data-gated."
updated_at: "2026-06-26"
updated_by: "claude"
```
