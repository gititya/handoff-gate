# LLM extractor — deferred, data-gated build decision

_Decision date: 2026-06-26. Status: DEFERRED (build only on data)._

## The architecture (honest framing)

- **Deterministic decision spine.** The mechanical contract field-check is the
  **sole hard release blocker**. It is deterministic, always available, and its
  pass/block is reproducible and auditable. This is the governance thesis.
- **LLMs only at the seams**, never in the decision:
  - _generation_ — `agent.py` writes the structured handoff note.
  - _judge_ — `eval-judges` gives **soft evidence**: it can flag → route-to-human,
    but it **never blocks** release. Local MLX is never a mandatory dependency in
    the release path.
  - _extraction_ (this doc) — a future seam that reads messy prose and reports
    whether the required substance is present, so the contract grades **substance,
    not format**. **Not built yet.**
- **Oracle-assisted correction is eval-lab only.** `gate.py` hands the answer key
  to the correction prompt — legitimate for an evaluation lab, NOT a claim of
  production self-correction. Labeled as such in `gate.py`.

## Why the extractor is deferred

The friction that raised the question (adversarial review, 2026-06-26): Contract
B's lenient arm false-blocked an honest **warm** escalation because the open
branches were named in `likely_cause` prose instead of the dedicated
`open_unknowns` list. That is an **extraction** failure (the substance was there;
a rigid field-check couldn't see it), not a **decision** failure.

Putting an LLM in the **decision** seat would collapse the thesis — the contract
and the judge would become the same thing, and release would stop being
reproducible. So the decision stays deterministic. The fix shipped instead:

1. **Middle path** in `check_handoff_b` — accept named open branches from either
   `open_unknowns` **or** prose (`_names_open_state_in_prose`, a deterministic
   token-scan **stopgap**), and **soft-flag** prose-only via `structure_warning`
   (routes to human, never blocks).
2. **Analytics** — every gate run logs a three-way outcome (below) so the extractor
   build decision is made from data, not anecdote.

## Build trigger (the data gate)

`support_os/analytics.py` appends one row per gate run to
`customer-support-ai-os/outputs/gate_analytics.jsonl`:

| outcome | meaning |
|---|---|
| `pass_clean` | released, well-structured — nothing to learn |
| `pass_prose_flagged` | released, but substance was in prose (a `structure_warning`) — **the extraction-brittleness signal**: a pure field-check would have false-blocked it |
| `blocked` | mechanical gate held the handoff (real gap, or cold escalation) |

**Build the LLM extractor when `pass_prose_flagged` accumulates past a meaningful
threshold across runs** (i.e. the token-scan stopgap is frequently the only thing
saving honest notes from a false block). Until then, the deterministic stopgap +
soft-flag is sufficient and cheaper. Review the rollup's `Prose-flagged: N/total`
line and the analytics file periodically.

If instead the failures are `blocked` cases where two reasonable reviewers
genuinely **disagree** whether the note should pass, that is decision-ambiguity —
a different (and higher) bar before any LLM touches the decision path.
