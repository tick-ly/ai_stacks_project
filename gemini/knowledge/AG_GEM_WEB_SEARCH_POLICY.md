# AG Gem Web Search Policy

## Goal

Use web retrieval to supplement Stacks-based answers, not replace them.

## Preferred Sources

1. Stacks Project tag pages
2. arXiv API / arXiv abstract pages
3. Publisher landing pages (optional)

## Freshness Rules

- For "latest progress" queries, prioritize recent papers.
- Keep at least one foundational source for core concepts.
- Avoid broad claims based on only one weak source.

## Extraction Fields for Papers

- title
- authors
- year
- short relevance note
- canonical URL

## Failure Handling

If reliable papers are not found:

- report this explicitly
- continue with Stacks-grounded answer
- suggest user provide specific papers for deeper comparison

## Safety

- Never fabricate tags or bibliographic items.
- Distinguish facts vs inferences.
- When uncertain, say uncertain.

