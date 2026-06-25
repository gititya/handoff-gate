# BUILDS.md — Handoff Quality Gate

**Repo:** `gititya/handoff_agent` · **Working dir:** `handoff-engine` · **Status:** Phase 0 locked, Phase 1 not started

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

## Next action
Open PR for `feat/phase-3-rollup`, Opus review. Phase 2 (Contract B) blocked on generating B2C product-bug cases upstream in `support-call-generator`.
