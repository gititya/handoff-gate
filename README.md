One of the core escalation philosophies I've held in my work in Support is that a customer should not have to repeat their complaint, past conversation & history just because their case moved to another person/team.
This holds more weight today, with LLMs, as companies start rolling out various levels of support - Help Center, LLM chatbots, (multiple levels) of human reps.

I built Handoff Quality Gate to check whether a support transfer gives the receiving person enough to continue. It can hold an incomplete note, explain what is missing and recheck it after correction. It does more than produce a quality score: it controls whether the note is released inside the prototype.

## What it does

The gate takes a handoff note and the available case information, chooses the relevant checklist and returns a decision:

- **Release:** the note meets the checks.

- **Hold:** required information is missing or a checked claim is unsupported.

- **Release with a review flag:** the note is usable but some information needs tidying.

- **Urgent exception:** the case moves despite gaps, with the reason and responsibility recorded.

It is not a customer facing check nor is it intended to replace the person(s) investigating the case.


> **Where it fits now**
> This is the same Handoff Gate used by the [Voice Support experiment](https://github.com/gititya/voice-support-case-study). Voice handles the customer interaction; this component checks the investigation before transfer. It also supports a human rep preparing a case for engineering. These are two uses of the same repository, not separate gates.
>
> Its actual application in the aforementioned experiment is not listed here; it'll be part of that experiment.

## In-Scope to this repo

I've considered two different support journeys and scope as part of experiment:

| Transfer                                     | What matters                                                                                                                                     |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| AI to a human rep: *a billing issue*         | Identify the account and charge, explain the customer's claim, preserve checks and unknowns, and state the next step and promise limits.         |
| Human rep to engineering: *a product defect* | Identify the affected task and scope, describe the failure and impact, include evidence and access limits, and request a specific investigation. |

These are two example checklists. Billing details are not universal requirements for every support handoff.

## An unresolved case can still be a useful transfer

Support does not need to prove the cause before asking engineering for help. Sometimes the next diagnostic step requires access the rep does not have.

> Import job 123 is stuck at 87%, blocking financial reporting. Support cannot inspect the processing queue. Please check whether this job failed or is delayed.

That gives the receiving person a specific task they can act on. “Please investigate” alone does not.

The no-access path requires the limitation to match supplied support records. It still needs the affected scope, impact and evidence. It must not invent completed checks or ruled-out causes to satisfy the checklist.

## What happens when information is missing?

Suppose a billing handoff explains the charge and the customer's complaint but leaves out the account identifier. The gate holds it and names the missing field.

If an explicitly supplied account record contains the identifier, the gate can fill that detail and recheck. If the record is absent, the note stays held. A test answer key is not a substitute for a customer record, and correction must not invent a diagnosis.

An unknown cause is acceptable when the evidence does not establish one. An “unknown” account identifier still does not identify the account.

## Urgent transfers

An incomplete urgent case can move without waiting for the entire list to be checked off. The release must record:

1. Who chose to release it.

2. Why waiting is worse.

3. Which team or on-call role should receive it.

Missing facts stay visible. This records a release decision; it does not wait for acknowledgment or prove that a helpdesk received the case.

## What is tested

The checks cover useful unresolved notes, missing required details, invented evidence, limited diagnostic access and urgent exceptions. The local urgent-release record is also checked by [Support Evals](https://github.com/gititya/support-evals): a missing releaser fails even when a later release has all the fields.

These are authored development cases and local component checks. They do not measure how often a real receiving team would find a transfer useful.

## Run the local checks

From the repository, with its Python dependencies available:

```bash
python3 -m pytest tests/ -q
```

The tests do not require a model call or send cases to a helpdesk.

## Limits

Completeness is not truth. The billing checklist does not verify every filled-in fact against the customer's systems. Parts of the engineering check compare words with supplied evidence; matching words do not guarantee the same meaning or catch every contradiction.

The application must supply trustworthy records. The gate does not authenticate the releasing person or independently verify their access. AI can write a handoff, so its mistakes can still affect the outcome even when fixed rules perform the checks.

The purpose is to make a useful transfer explicit: preserve what is known, allow honest uncertainty and give the next person a clear reason to pick up the case.
