# AG Gem Retrieval Template

Use the following skeleton internally when organizing an algebraic-geometry explanation:

- `定`: what the object is
- `判`: how it is recognized
- `例`: what the standard examples are
- `反`: where the definition fails if assumptions are weakened
- `联`: how it relates to nearby concepts
- `用`: what it is used for

## Translation Rule

Before retrieving, translate the user's vague request into a structural need:

- "它是什么" -> definition / notation / minimal example
- "怎么证明或怎么判断" -> criteria / equivalent characterizations / local tests
- "边界在哪里" -> counterexamples / pathologies / dropped assumptions
- "和别的概念什么关系" -> implication map / equivalence conditions / non-implications
- "为什么这里要用它" -> use cases / trigger conditions / tool interactions

## Recommended Expansion Order

For `study` mode, prefer this order unless the user asks otherwise:

1. scope and motivation
2. formal definition
3. criterion or relation
4. example or local model
5. boundary / pathology / non-example
6. use or why the concept matters

For `proof` mode, prefer:

1. statement and assumptions
2. proof roadmap
3. key lemma or mechanism
4. where the hard point lives
5. what remains for the next turn if unfinished

## Visible Writing Rule

The skeleton is for planning, not for dumping raw labels.

Prefer visible section titles such as:

- `定义与动机`
- `关键判据`
- `例子与反例`
- `与相邻概念的关系`
- `为什么这里必须用它`

## Minimum Closed Unit

One turn should feel like a usable mini-note, not a teaser.

Unless the user explicitly asks for brevity, a high-relevance explanation should normally contain:

- a clear scope line
- at least one formal statement or precise definition
- at least one example, comparison, or pathology
- at least one relation or use-case
- references that support the main claims
