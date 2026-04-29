# AG Gem Evaluation Checklist

Use this checklist to quickly test whether Gem behavior matches the target skill.

## A. Relevance Routing

- Input unrelated query (e.g., "如何学做蛋糕？"):
  - Expected: `low` relevance behavior, no forced AG answer.
- Input AG query (e.g., "什么是平坦态射？"):
  - Expected: `medium/high` route with citations.

## B. Citation Quality

- Does answer cite Stacks tags for foundational facts?
- Are paper/web citations formatted and link-valid?
- Are key theorem-level claims cited?

## C. Hallucination Resistance

- Ask for obscure theorem:
  - Expected: uncertainty disclosure if not verified.
- Check whether fake tags are avoided.
- Check whether fake paper metadata is avoided when web evidence is weak.

## D. Output Shape

- Includes relevance verdict line.
- Main explanation is structured and scoped.
- References section present at end.

## E. Continuation Hygiene

- Ask a large teaching question and stop the model mid-topic:
  - Expected: answer ends with a natural-language next-step hint.
  - Expected: no raw control block.
  - Expected: the answer already forms one closed batch, not a teaser fragment.
- Check the output text:
  - Expected: no `CONTINUE_STATE`
  - Expected: no `slots_done`
  - Expected: no `slots_next`
  - Expected: no `refs_kept`
  - Expected: no `locked_terms`

## F. Depth / Length Behavior

- Input a high-relevance teaching query (e.g., "详细讲解 flat morphism 的定义、判据和典型反例"):
  - Expected: not just a short summary.
  - Expected: contains at least three substantial content parts among definition, criterion, example, pathology, relation, use.
  - Expected: feels like a mini-lecture or usable note.
- Failure pattern:
  - `Relevance + Slot Focus + 两段短文 + References` should be treated as too short for `study/high` unless the user asked for brevity.
  - chapter-like AG requests that only cover a tiny slice without a stable next anchor should be treated as failures.

## G. Freshness Behavior

- For "最新进展" queries:
  - Expected: recent papers + at least one foundational anchor.

## H. Literature Explanation Quality

- Input a literature-focused prompt (e.g., "比较 DAG 中 cotangent complex 的几条代表性文献并给阅读顺序"):
  - Expected: not only titles/metadata.
  - Expected: each major paper is explained by problem, method, contribution, and limitation.
  - Expected: contains cross-paper synthesis, not isolated summaries.
- If evidence is insufficient for 3-paper comparison:
  - Expected: state the evidence gap explicitly instead of fabricating detail.

## I. Validation Layer Quality

- Input a proof-heavy question:
  - Expected: assumptions are stated clearly.
  - Expected: main proof steps are justified rather than skipped.
  - Expected: likely failure modes or missing hypotheses are noted when relevant.
- Input a delicate equivalence claim:
  - Expected: does not silently prove only one direction.
  - Expected: marks uncertain parts as inference instead of fact.

## J. Degradation Behavior (Agent v4 Alignment)

- Simulate papers/web failure (very niche topic + strict constraints):
  - Expected: still returns Stacks-grounded answer.
  - Expected: includes short warning that papers/web are unavailable/unreliable.
  - Expected: no fabricated `[P*]` citations.

- Simulate Stacks failure (ask with no local Stacks access):
  - Expected: still returns web-grounded answer.
  - Expected: includes certainty downgrade note for foundational claims.

## J2. Freshness / Survey Handling

- Ask for latest/survey/comparison oriented prompts:
  - expected: papers/web branch shows recency-aware behavior (more recent candidates promoted).
  - expected: if recency intent is absent, no forced recency bias should appear.

## K2. Error-Code Contract

- Simulate script-level failures in each stage:
  - expected: response includes warning objects with standard `code` values (for example `STACKS_RETRIEVAL_ERROR`, `PAPERS_RETRIEVAL_ERROR`).
  - expected: output routing changes based on structured error signals instead of ad hoc text.
- expected: every warning includes `degrade_reason` and that value belongs to:
  - `tls_restricted`
  - `timeout`
  - `parse_error`
  - `no_matches`
  - `error`
- expected: degraded outputs also expose `degradations` + `source_confidence` + `evidence_quality`.

## K. Source Coverage Check

- Query with strong discussion intent (e.g., intuition/comparison questions):
  - Expected: may include `MathOverflow` / `Math StackExchange` references.
- Query with formal theorem request:
  - Expected: does not rely only on MO/MSE for theorem truth.

## L. Category Constraint Check

- Ask for generic topic and inspect paper choices:
  - Expected: mostly from AG-adjacent categories under default constraint
  - `math.AG / math.AC / math.RT / math.NT / math.KT / math.RA / math.AT`

## M. Stress Test Pack

For higher-confidence evaluation, do not stop at smoke tests.
Run the dedicated pack under:

- `gemini/tests/PROOF_STRESS_TESTS.md`
- `gemini/tests/RESEARCH_STRESS_TESTS.md`
- `gemini/tests/PATHOLOGY_COUNTEREXAMPLE_STRESS_TESTS.md`

Use `gemini/tests/SCORECARD_TEMPLATE.md` to record outcomes.

Red-line failures in the stress pack should override good smoke-test behavior.
