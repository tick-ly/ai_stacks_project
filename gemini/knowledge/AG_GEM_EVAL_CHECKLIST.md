# AG Gem Evaluation Checklist

Use this checklist to quickly test whether Gem behavior matches the target skill.

## A. Relevance Routing

- Input unrelated query (e.g., "如何学做蛋糕？"):
  - Expected: `low` relevance behavior, no forced AG answer.
- Input AG query (e.g., "什么是平坦态射？"):
  - Expected: `medium/high` route with citations.

## B. Citation Quality

- Does answer cite Stacks tags for foundational facts?
- Are paper citations formatted and link-valid?
- Are key theorem-level claims cited?

## C. Hallucination Resistance

- Ask for obscure theorem:
  - Expected: uncertainty disclosure if not verified.
- Check whether fake tags are avoided.

## D. Output Shape

- Includes relevance verdict line.
- Main explanation is structured and scoped.
- References section present at end.

## E. Freshness Behavior

- For "最新进展" queries:
  - Expected: recent papers + at least one foundational anchor.

