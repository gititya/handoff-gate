# Support investigation contract

Version: `support-investigation/1.0`

This contract is the app-independent package a support system can give to a
local support reviewer. It records the customer request, the current goal,
bounded diagnostic work, known sources, risk, open unknowns, and the customer
outcome. It does not require billing fields, account numbers, or a confirmed
cause. Contract A and Contract B remain the owners of their existing
destination-specific handoff checks.

## Record

Every field below is required. The validator does not fill missing fields or
change the record.

| Field | Shape and rule |
| --- | --- |
| `schema_version` | Must equal `support-investigation/1.0`. |
| `session_id` | Non-empty session identifier. |
| `product_id` | Non-empty registered product identifier. |
| `customer_request` | Object with non-empty `text` and `evidence_ref`. The reference must point to a `customer_question` event whose `text` is an exact match. |
| `current_goal` | Object with non-empty `text` and `source` equal to `customer` or `model_interpretation`. |
| `steps` | List of diagnostic steps. Each has a non-empty `step_id`, `target_id` and `result`, `status` (`observed` or `attempted`), and evidence references. An optional `run_id` lets the same step repeat in separate runtime journeys; the `(run_id, step_id)` pair must be unique. |
| `knowledge` | List of objects with a non-empty `pin`, `source_ref`, `article_id`, or `source_url`. These are source identifiers, not session evidence IDs. An optional `evidence_ref` must resolve to a matching `knowledge_selected` event. |
| `customer_outcome` | `not_resolved`, `unsure`, or `not_asked`. `not_resolved` additionally requires `confirmation_ref` and `guidance_run_id`; the selected latest confirmation for that run must have `answer: "no"` and follow observed steps in that run. |
| `handoff_reason` | Non-empty explanation for the local review. |
| `risk` | Object with `level` (`low`, `medium`, or `high`) and a preserved list of structured Core signal entries. `signal_id`, `risk`, and `reason`, when present, are checked; `source`, when present, is `evidence_or_rule` or `model_assessment`. The validator never lowers or flattens a high-risk record. |
| `unknowns` | List of open-unknown strings. An empty list is valid. |
| `identity` | `status` is `not_supplied`, `withheld`, or `supplied`. `supplied` requires a non-empty `value` and `evidence_handle` matching a `confirmed_facts` `customer_account_identity` fact; withheld identities do not carry a value. |
| `evidence` | Session-history event list with unique event IDs and non-empty kinds. Declared session or product origins must match the record. |
| `recipient` | Exactly `{ "kind": "local_support_review", "external_delivery": "not_requested" }`. |
| `core_decision_ref` | Required reference to a `support_decision` event whose risk and fact fields match this record. |

The optional `confirmed_facts` list carries the Core fact objects that support
the investigation. Fact metadata is preserved for the local reviewer; when a
fact includes `evidence_handle`, that handle must be non-empty.

The `core_decision_ref` points to the server's `support_decision` event. That
event's `current_risk`, `risk_signals`, and `confirmed_facts` must equal the
corresponding record fields. This is an origin consistency check; it does not
claim cryptographic proof.

## Evidence and step proof

An evidence reference is an event ID in the same record. Every
`customer_request.evidence_ref` and step `evidence_refs` entry must resolve.
Event metadata may contain additional fields, but an event that declares
`session_id` or `product_id` must match the record origin. This rejects copied
events from another support session.

An observed step is a server-observed fact. It must cite a
`guidance_step_observed` event with matching `step_id` and `target_id`, and the
step's `result` must equal that event's `predicate`. If the step carries a
`run_id`, the event must carry the same run ID.

```json
{
  "event_id": "step-1-observed",
  "kind": "guidance_step_observed",
  "session_id": "session-1",
  "product_id": "product-1",
  "step_id": "check-export",
  "target_id": "export-queue",
  "predicate": "queue has no completed job"
}
```

An attempted step may cite resolved evidence, but an attempt is not promoted
to an observed fact. A `customer_confirmation` event with `answer: "no"`
supports the `not_resolved` outcome. `not_asked` permits an urgent or
human-request transfer with no completed diagnostic steps.

## Safety boundary

The contract records evidence and routing state. It does not authorize an
external delivery, invent product knowledge, assert a cause, or expose an
identity that was withheld. `validate_investigation` returns a list of errors
and never raises for null or malformed input. Callers should hold the package
when the list is non-empty and preserve high-risk signals for the local
reviewer.
