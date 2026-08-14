# CLAUDE.md — Handoff Quality Gate (handoff_agent)

This repo is the case-quality organ of **Support Product**. The product map lives at
`customer-support-ai-os/system-map.json`; read it before assuming this repo stands alone.

Coding-agent context for this repo. Read `SKILL.md` for current phase state before doing anything. The authoritative design docs live in the Obsidian vault under `Customer support/handoff agent/` — `Handoff Quality Gate — Execution Plan.md` (the build sequence) and `Handoff Quality Gate — Contracts.md` (the locked Contract A, the load-bearing artifact).

## What this repo is
The **bridge** that turns three existing repos into a live handoff quality gate. It is **connective tissue**, not a from-scratch system. ~80% already stands. Build only:
- **Step 2 — destination router:** destination (AI→human / human→eng) + issue type → picks the right contract.
- **Step 4 — gate decision + corrected note:** pass → release; fail → **intercept and hold**, name missing fields, write the corrected note from the reconstruction + `expected_handoff`, then release.
- **Step 5 — weekly roll-up:** pass rate + top recurring gap over a batch.

## The pipeline (and what NOT to rebuild)
```
support-call-generator ──► support-copilot ──► eval-judges ──► [THIS REPO: router + gate + corrected note + rollup]
(case + expected_handoff)   (reconstruct the case)        (grade handoff)
```
- **`support-call-generator`** — pull the existing `exports/b2c_handoff_gate_seed` pack (10 hard B2C disputed-charge cases + `expected_handoff` answer key). Do NOT regenerate it.
- **`support-copilot`** — **ENGINE REUSE ONLY.** Vendor its reconstruction loop (incremental Live Support State + evidence-timed final-cause gating + premature-answer penalty), parametrizing `CANONICAL_LABELS` and the fixture source. Do NOT import its B2B domain layer (`fixtures/`) and do NOT add a B2C mode to that repo.
- **`experiments/eval-judges`** — the `handoff_completeness` judge is built and passing. Reuse it (input: `{ticket, agent_response, handoff_note}`; runs local MLX Qwen3-4B). It is Step 3, not a new build.

## Locked Phase 0 decisions (do not re-litigate)
- **Hero demo:** B2C, AI→human hop, disputed/unrecognized-charge issue type. One issue type only — no taxonomy.
- **Leniency on field 6 (likely cause + confidence) is derived from the reconstructed evidence**, never from a metadata label — "given the evidence that arrived, was a confident cause reachable?" This keeps the gate vendor-neutral (runs on any transcript). `resolution_type` is used only for routing, never grading.
- **Completeness, not effort.** A cut-short case isn't penalised for a missing cause, but the note must be explicit about the open state. Thin-but-honest passes; thin-and-silent fails. "Should the AI have dug more?" is a different judge's job.
- **Borderline guard:** when reconstruction is unsure evidence was sufficient → default lenient but raise a `borderline` flag for human review. Never silently grant leniency.
- Identity + the charge + the claim are ALWAYS required, regardless of how the case ended.

## Define "block" concretely
"Block" = a real **intercept-and-hold** at a simulated workflow boundary (a mock "release to the human's co-pilot" step) — a handoff package not released until corrected. NOT a report or a score. The intercept-and-hold is what makes it a gate.

## Scope guards (refuse scope creep)
Not a chatbot / responding agent / generic dashboard. One issue type for the hero demo. Honest framing: "a known metric, done live and deep," never "nobody does this." Proof-of-work on synthetic data — claim "I built the components," never production parity.

## Working rules
- Read files before editing. Minimal changes. No over-engineering / future-proofing.
- No TypeScript by default (this is a Python project).
- Ask before destroying (git reset, deletes, force push). No secrets/PII committed.
- Branch off `main`, never push to `main` directly — use a PR. Confirm before commit/push.
- Model rule: Sonnet builds, Opus reviews, Codex cross-checks.

---

## SUPERSEDED — 2026-06-26 · B2B is in-bounds; Contract B is B2B (integration stance)

> Append-only. Two earlier statements above are now **history, not instruction**, retained for provenance:
> 1. *"ENGINE REUSE ONLY … Do NOT import its B2B domain layer (`fixtures/`)"* — superseded.
> 2. The implication that Contract B is B2C — superseded.

The portfolio moved from an **isolation** stance to an **integration** stance (user-approved, 2026-06-26): the repos are being connected into one pipeline by a thin deterministic runner in `customer-support-ai-os`. Under integration:

- **The realtime B2B fixtures are IN-BOUNDS.** They are the natural Flow-2 (product-bug) source because the copilot only reconstructs that domain.
- **Contract B is a B2B product-bug human→engineering handoff** (see `contracts.py::check_handoff_b`, anchors in `contract_b_anchors/`).
- **The copilot is called, not re-implemented.** Flow-2 reconstruction is `support-copilot/run.py::run_fixture` (subprocess via the runner). The vendored `engine.py` replay stays for Flow-1 billing / fast deterministic checks.
- **The judge is soft evidence, not a hard blocker** (mechanical contract check is the release gate).
- Still true and unchanged: PR-only (never push to `main`), confirm before commit/push, no secrets/PII, honest "I built the components" framing. Authoritative plan: `~/.claude/plans/breezy-petting-thimble.md`.
