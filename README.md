# Handoff Quality Gate

A deterministic gate that sits between support tiers and refuses to let a low-quality handoff move up. It intercepts the handoff note, checks it against a fixed contract, and **holds it until it's good enough** — it does not just score it.

The decision is mechanical and reproducible. LLMs only ever sit at the edges (writing notes, an optional soft judge, a deferred prose→fields extractor). **No LLM is in the pass/block decision path** — that's what makes every block auditable: the reason is always a fixed field check, not a model's opinion.

## Two flows

| Flow | Hop | Contract | Question it enforces |
|------|-----|----------|----------------------|
| 1 | AI bot → human (B2C billing) | A | Did the human get the account + the charge + the claim? |
| 2 | Human → engineering (B2B product bug) | B | Did engineering get an *honest, grounded* escalation — not a cold dump or a confident guess? |

## How a note is judged (Contract B)

Leniency is **derived from the evidence**, never a metadata label — "given the evidence that arrived, was a confident cause reachable?"

- **Cause was proven → strict.** The note must state `likely_cause` + `confidence`, and the cause must actually match the case evidence.
- **Cause still open → lenient.** An honest *warm* escalation must still **name the open branches** (in `open_unknowns`, `candidate_branches`, or even in prose). A *cold* one that says nothing about what's open **blocks**.

### Two things the gate checks

1. **Completeness** — required fields are present. Missing identity/charge/claim always blocks.
2. **Grounding** (`evidence_gaps`) — the note's claims actually overlap the case evidence. An `evidence_handles`, `support_ruled_out`, `likely_cause`, or `open_unknowns` that the case doesn't support gets `*_not_supported` and **blocks**. This catches a *confident, well-formatted, wrong* handoff — not just a thin one. (Token-overlap heuristic; a deterministic stopgap until the LLM-extractor seam lands.)

Prose-only open branches **pass** but carry a `structure_warning` → routed to a human to tidy into a list. Never blocked for format alone.

## When the gate blocks

- **Correct it** — `trusted_sources` mode fills missing fields from the system of record and **refuses to invent** what isn't there. (`oracle` mode reads the sealed answer key — eval-lab only, never a production claim.)
- **Override it** — a blocked note can be released with a *recorded reason* (`sla_risk`, `vip_customer`, `active_incident`, …), logged as `override_required`. An override is **not a pass** — it records why the risk moved. This is the real-support escape hatch: sometimes you must escalate before root cause.

## Run it

```bash
# Unit tests — the deterministic proof of every rule
python3 -m pytest tests/ -q

# Flow 2 live roll-up over the B2B anchors (clean transcripts)
python3 b2b_rollup.py

# Adversarial run — agent gets a hostile transcript (evidence withheld,
# wrong-cause distractor, or a cold dump). The gate should block these.
python3 b2b_rollup.py --profile hostile
```

A clean run is *not* expected to be 100% — the grounding guard blocks live notes that drift from the evidence. The hostile run should block all three. That's the honest signal.

## Layout

- `contracts.py` — the contracts, leniency derivation, completeness + grounding checks.
- `gate.py` — intercept-and-hold, correction modes, override lane, release.
- `agent.py` — the live LLM that writes the candidate note (edge, not decision).
- `b2b_rollup.py` — Flow 2 batch over `contract_b_anchors/`, clean + hostile profiles.
- `rollup.py` — Flow 1 (Contract A) roll-up.
- `docs/llm-extractor-deferral.md` — why the prose→fields extractor is deferred and data-gated.

See `AGENTS.md` / `SKILL.md` for build state and locked design decisions.
