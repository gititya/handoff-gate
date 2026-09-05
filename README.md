# Handoff Gate

**A handoff that is polite, confident, and missing the account, the charge, or the claim is not a handoff. The gate holds it and says exactly what is missing.**

## Two flows

| Flow | Hop | Contract | Question it enforces |
|------|-----|----------|----------------------|
| 1 | AI bot → human (B2C billing) | A | Did the human get the account + the charge + the claim? |
| 2 | Human → engineering (B2B product bug) | B | Did engineering get an *honest, grounded* escalation—not a cold dump or a confident guess? |

The rollups use synthetic B2C and B2B cases. Contract A uses 10 B2C seed cases; Contract B uses 11 B2B anchor cases.

A deterministic (rule-based) gate that sits between support tiers and refuses to let a low-quality handoff move up. It intercepts the handoff note, checks it against a fixed contract, and **holds it until it's good enough** — it does not just score it.

In the prototype, Voice Support creates the B2C note, this repo checks it, and the SHA-pinned
harness replays the accepted H1 case. Its evidence is intentionally mixed: clean cases release
and hostile cases block.

The decision is mechanical and reproducible. LLMs only ever sit at the edges (writing notes, an optional soft judge, a deferred prose→fields extractor). **No LLM is in the pass/block decision path** — that's what makes every block auditable: the reason is always a fixed field check, not a model's opinion.

**What each contract actually checks (honest scope):** Contract A (completeness check) — the
Flow 1 / front-door showcase path — enforces **completeness with evidence-derived leniency**: required fields must
be present, and an open case must name its unknowns. It does **not** verify that field contents
are true against product records. The grounding checks (`*_not_supported`) currently exist on
**Contract B only**, as the disclosed token-overlap stopgap described below. The note→contract
adapter never authors a field on the note's behalf: a note missing its promise constraints is
held for one, not defaulted.

## How a note is judged (Contract B / truth check)

Leniency is **derived from the evidence**, never a metadata label — "given the evidence that arrived, was a confident cause reachable?"

- **Cause was proven → strict.** The note must state `likely_cause` + `confidence`, and the cause must actually match the case evidence.
- **Cause still open → lenient.** An honest *warm* escalation must still **name the open branches** (in `open_unknowns`, `candidate_branches`, or even in prose). A *cold* one that says nothing about what's open **blocks**.

### Two things the gate checks

1. **Completeness** — required fields are present. Missing identity/charge/claim always blocks.
2. **Grounding** (`evidence_gaps`) — the note's claims actually overlap the case evidence. An `evidence_handles`, `support_ruled_out`, `likely_cause`, or `open_unknowns` that the case doesn't support gets `*_not_supported` and **blocks**. This catches a *confident, well-formatted, wrong* handoff — not just a thin one. (Token-overlap heuristic; a rule-based stopgap until the LLM-extractor seam lands.)

Prose-only open branches **pass** but carry a `structure_warning` → routed to a human to tidy into a list. Never blocked for format alone.

## When the gate blocks

- **Correct it (default)** — `trusted_sources` fills only the missing **system-of-record facts** (account/identity/charge) from the records and **refuses to invent** anything else. It **never fabricates a diagnosis**: if `likely_cause`, evidence, or open branches are missing, the handoff stays held. (`oracle` mode reads the sealed answer key — **eval-lab only**, must be requested explicitly, never the default.)
- **Override it (manual release, reason recorded)** — a blocked note can be released with a *recorded reason* (`sla_risk`, `vip_customer`, `active_incident`, …), logged as `override_required`. An override is **not a pass** — it records why the risk moved. This is the real-support escape hatch: sometimes you must escalate before root cause.

## Run it

```bash
# Unit tests — the deterministic proof of every rule
python3 -m pytest tests/ -q

# Flow 2 model-written roll-up. Default = audit: every anchor on a clean transcript
# PLUS the hostile set, reported as ONE honest number.
python3 b2b_rollup.py

# Just the adversarial set (agent gets evidence withheld / wrong-cause
# distractor / cold dump). The gate should block all three.
python3 b2b_rollup.py --profile hostile
```

The headline is not a perfect pass rate by design: the hostile cases block, and the grounding guard blocks model-written notes that drift from the evidence. A perfect pass rate here would mean the gate is not doing its job.

## What "done / honest" means here

There are no real customers or call data, so success is **not** "is it real" — it's "can a skeptical reviewer find a place where a number is inflated or a value is faked?" The bar is a fixed set of invariants:

- Grading reads evidence, never a difficulty/resolution metadata label.
- Correction fills system-of-record facts only — it never invents a diagnosis.
- The headline number comes from a run where the agent **can** fail (audit/hostile), not a spoon-fed one.
- The repo does not include an aggregated false-block rate. `docs/llm-extractor-deferral.md` states how that rate would be measured if real prose-only cases accumulate.
- Fixtures are labeled as synthetic; a block is an implemented intercept-and-hold inside the prototype, not just a score.

The grounding check is rule-based word-overlap — a labeled **stopgap**. A semantic extractor was
considered and intentionally not built. It is not pending work; only real accumulated prose-only
cases plus a new scope decision can reopen it.

## Layout

- `contracts.py` — the contracts, leniency derivation, completeness + grounding checks.
- `gate.py` — intercept-and-hold, correction modes, override lane, release.
- `agent.py` — the optional model writer for the candidate note (edge, not decision).
- `b2b_rollup.py` — Flow 2 batch over `contract_b_anchors/`, clean + hostile profiles.
- `rollup.py` — Flow 1 (Contract A) roll-up.
- `docs/llm-extractor-deferral.md` — why the prose→fields extractor is deferred and data-gated.

See `AGENTS.md` / `SKILL.md` for build state and locked design decisions.
