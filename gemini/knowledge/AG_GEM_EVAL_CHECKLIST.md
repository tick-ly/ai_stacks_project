# AG Gem Evaluation Checklist

Use this checklist to test whether the Gem behaves like the target skill and remains stable across multiple turns.

## A. Relevance Routing

- Input unrelated query:
  - `如何学做蛋糕？`
  - Expected: `low` relevance behavior, no forced AG answer

- Input AG query:
  - `什么是平坦态射？`
  - Expected: `medium/high` route with citations

## B. Citation Quality

- Does answer cite Stacks tags for foundational facts?
- Are paper/web citations formatted and link-valid?
- Are key theorem-level claims cited?
- Are unsupported `[P*]` citations absent when web evidence is weak?

## C. Hallucination Resistance

- Ask for obscure theorem:
  - Expected: uncertainty disclosure if not verified
- Check whether fake tags are avoided
- Check whether fake paper metadata is avoided

## D. Output Shape

- Includes relevance verdict line
- Main explanation is structured and scoped
- References section present at end
- `CONTINUE_STATE` appears when topic is unfinished

## E. Freshness Behavior

- For `最新进展` queries:
  - Expected: recent papers + at least one foundational anchor

## F. Degradation Behavior

- Simulate papers/web failure:
  - Expected: still returns Stacks-grounded answer
  - Expected: includes short warning
  - Expected: no fabricated `[P*]`

- Simulate Stacks failure:
  - Expected: still returns web-grounded answer
  - Expected: includes certainty downgrade note

## G. Multi-Turn Continuation

- Turn 1:
  - ask for a broad topic such as `系统讲解 flat morphism`
  - Expected: only one closed unit is completed
  - Expected: answer explicitly states current slot focus, such as `定 + 例`
  - Expected: no attempt to write the entire lecture in one turn

- Turn 2:
  - say `继续`
  - Expected: resumes from `CONTINUE_STATE.next`
  - Expected: resumes from `slots_next` instead of restarting from `定`
  - Expected: at most two recap sentences
  - Expected: existing citation IDs stay stable

- Turn 3:
  - say `继续并讲病态例子`
  - Expected: fills remaining open loop instead of restarting whole answer

## H. Slot Coverage Check

- After several turns on the same topic, inspect whether the answer set covers:
  - `定`
  - `判`
  - `例`
  - `反`
  - `联`
  - `用`
- Expected: the six slots are gradually completed across turns, not jammed into one turn.

## I. Source Coverage Check

- Query with discussion intent:
  - Expected: may include `MathOverflow` / `Math StackExchange`

- Query with formal theorem request:
  - Expected: does not rely only on MO/MSE for theorem truth

## J. Category Constraint Check

- Inspect paper choices under default behavior:
  - Expected: mostly AG-adjacent categories
  - `math.AG / math.AC / math.RT / math.NT / math.KT / math.RA / math.AT`
