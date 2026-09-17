# Minimum useful transfer to engineering

Approved by Adi, 13 September 2026. This standard is for a receiving engineer to start the next investigation, not a demand that support diagnose the cause first.

## Required context

1. Locate the case: account/workspace or case reference and affected scope. The configured destination is engineering; the gate does not invent a team.
2. Describe the failure: what the customer tried, what they expected and what happened. Include the affected operation, job or record and time/window when available. Mark missing detail explicitly.
3. Explain impact and urgency: who or what is blocked, whether it continues, and why delay matters. Do not invent affected-user counts.
4. Preserve evidence and limits: links/handles for observations and checks with their results. If support cannot check, record the missing access and its source. Customer reports remain reports, not proof of a backend cause.
5. Ask for a specific next investigation: what record, job or component should be inspected and what question that would answer. “Please investigate” alone is not enough.

No universal requirement for a root cause, successful reproduction, logs support cannot access, or invented ruled-out causes. A screenshot, timestamp or request ID is useful where it locates the failure; do not demand every artifact for every case. Missing essential context normally holds the transfer with the gap named.

## Supported no-access path

An empty support_ruled_out list can pass when diagnostic_limit records reason, required_access, next_check and evidence_handle. It must match separately supplied support context in state.diagnostic_limit; the handle must exist in state.facts and next_check must match specific_ask. This prevents the candidate note granting itself an exception. The application supplying that support context must do so from trusted rep/tool input, not copy the AI's assertion. Other required fields and open-state checks still apply.

Example: import job 123 stalls at 87%, delaying financial reporting. Support's queue access is denied. Request: inspect job 123 for a failed or delayed queue event. Nothing is claimed ruled out. This is a useful investigation transfer, not a diagnosis or a repair.

## Urgent exception

Record released_by, recipient (team or on-call role), reason explaining why waiting is worse, and reason_code. Missing fields stay visible; the outcome remains an exception, not a clean pass. VIP status alone is not an allowed reason. No recipient acknowledgment is required by this local gate. The record does not prove delivery, acceptance or that a person read the case. Caller-supplied identities are recorded, not authenticated by this library.

## Mechanical proof limits

Billing Contract A checks completeness. Engineering Contract B checks required fields plus limited word overlap with supplied evidence. The gate does not reliably judge all paraphrases, vague requests or contradictory prose. The explicit structured minimum and authored counterexamples make the contract inspectable; they are not production or human-usability validation.
