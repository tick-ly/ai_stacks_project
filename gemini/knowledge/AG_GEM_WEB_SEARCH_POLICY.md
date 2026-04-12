# AG Gem Web Search Policy

## Goal

Use web retrieval to supplement Stacks-based answers, not replace them.

## Preferred Source Tiers

1. Scholarly sources: `arXiv`, `OpenAlex`, `Semantic Scholar`
2. Bibliographic fallback: `Crossref`
3. Expert discussion sources: `MathOverflow`, `Math StackExchange`
4. Context fallback: `Wikipedia`

## arXiv Default Scope

Unless user overrides, constrain paper discovery to:

- `math.AG OR math.AC OR math.RT OR math.NT OR math.KT OR math.RA OR math.AT`

## Freshness Rules

- For "latest progress" queries, prioritize recent papers.
- Keep at least one foundational source for core concepts.
- Avoid broad claims based on one weak source only.
- Prefer conclusions supported by multiple independent sources.

## Extraction Fields for Papers/Web

- title
- authors
- year
- short relevance note
- canonical URL
- source/provenance

## Retrieval Budgeting

- First turn: retrieve only what is needed for the first closed unit.
- Continuation turns: expand retrieval only for the next requested unit.
- Avoid repeating broad search and full-source fusion every turn.

## Failure Handling

If reliable papers/web evidence is not found:

- report this explicitly
- continue with Stacks-grounded answer
- suggest user provide specific papers/URLs for deeper comparison

If Stacks fails but papers/web succeeds:

- continue with papers/web evidence
- downgrade certainty for foundational theorem claims
- avoid fabricating theorem IDs or tags

## Safety

- Never fabricate tags or bibliographic items.
- Distinguish facts vs inferences.
- Discussion threads (MO/MSE) can support intuition but do not alone prove theorem truth.
- When uncertain, say uncertain.
