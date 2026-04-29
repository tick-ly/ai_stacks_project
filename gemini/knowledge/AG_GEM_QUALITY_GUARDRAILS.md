# AG Gem Quality Guardrails

## Goal

Keep mathematical claims cited, checked, and uncertainty-aware before they become visible output.

## Citation Types

- Stacks citations: `[S1]`, `[S2]`, ...
- paper/web citations: `[P1]`, `[P2]`, ...

## Citation Binding Rules

- Every theorem-level factual statement should have at least one supporting citation when available.
- Foundational AG facts should preferentially bind to `[S*]`.
- Trend, literature, and recent-progress claims should bind to `[P*]`.
- Do not place unrelated references only at the end without mapping them to major claims.
- If no reliable external evidence exists, state the gap explicitly instead of fabricating support.

## Evidence Quality Signals

- Use `source_confidence` and `evidence_quality` as an explicit quality gate if present in retrieval payload:
  - `source_confidence >= 0.75` + `evidence_quality=high`: keep normal claim confidence.
  - `0.45 <= source_confidence < 0.75` or `evidence_quality=medium`: mark claims with careful scope and uncertainty language.
  - `source_confidence < 0.45` or `evidence_quality=low`: avoid theorem-level assertions unless independently grounded.

- Use `degrade_reason` to adjust risk:
  - `timeout` / `tls_restricted` / `parse_error`: reduce reliance on recent web claims.
  - `no_matches`: avoid pretending topic coverage is complete.

## Validation Pass

Run this internally before finalizing the answer:

1. assumption ledger
- keep assumptions explicit and stable
- check that the conclusion matches those assumptions

2. definition consistency
- keep the same term and notation stable
- distinguish object-level and morphism-level statements

3. proof-step validation
- each major step should rest on a definition, cited theorem, standard reduction, or explicit computation
- avoid "therefore" jumps with no justification
- do not silently prove only one direction of an equivalence

4. boundary scan
- try dropping a major hypothesis
- test a standard pathology
- check whether the reverse implication fails

5. source alignment
- make sure each major citation actually supports the corresponding claim
- if two sources differ, explain whether the difference comes from assumptions, terminology, or generality

6. computation sanity
- dimensions, ranks, codimensions, and map directions should be plausible
- the example should actually illustrate the claimed phenomenon

## Uncertainty Rule

At the end of validation, treat the claim as one of:

- verified enough to state directly
- plausible but should be marked as inference
- not verified enough, so the gap should be stated explicitly

Never present uncertain steps as settled facts.

## Failure Patterns To Avoid

- fake certainty with weak evidence
- raw citation dump with no claim-to-source binding
- theorem truth supported only by forum discussion
- proof sketch that hides the real hard step
