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

## E. Freshness Behavior

- For "最新进展" queries:
  - Expected: recent papers + at least one foundational anchor.

## F. Degradation Behavior (Agent v3 Alignment)

- Simulate papers/web failure (very niche topic + strict constraints):
  - Expected: still returns Stacks-grounded answer.
  - Expected: includes short warning that papers/web are unavailable/unreliable.
  - Expected: no fabricated `[P*]` citations.

- Simulate Stacks failure (ask with no local Stacks access):
  - Expected: still returns web-grounded answer.
  - Expected: includes certainty downgrade note for foundational claims.

## G. Source Coverage Check

- Query with strong discussion intent (e.g., intuition/comparison questions):
  - Expected: may include `MathOverflow` / `Math StackExchange` references.
- Query with formal theorem request:
  - Expected: does not rely only on MO/MSE for theorem truth.

## H. Category Constraint Check

- Ask for generic topic and inspect paper choices:
  - Expected: mostly from AG-adjacent categories under default constraint
  - `math.AG / math.AC / math.RT / math.NT / math.KT / math.RA / math.AT`
