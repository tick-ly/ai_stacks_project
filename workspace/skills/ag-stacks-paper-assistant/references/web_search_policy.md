# Web Search Policy for Papers

## Purpose

Use web retrieval to supplement local Stacks knowledge, not replace it.

## Preferred Sources

1. arXiv API
2. Publisher landing pages
3. Author homepages

## Freshness and Validity

- Prefer recent papers when user asks for latest developments.
- Keep at least one foundational source when discussing core concepts.
- Avoid relying on a single source for broad claims.

## Extraction Rules

When parsing paper metadata, capture:

- title
- authors
- year (if present)
- abstract snippet (short)
- canonical URL

## Failure Handling

If no reliable papers are found:

- report that clearly
- continue with Stacks-grounded answer
- suggest user can provide specific papers for deep comparison

## SSL Fallback Handling

- Default: strict SSL verification.
- Preferred fix order:
  1. system trust store
  2. certifi bundle
  3. explicit `--ca-bundle`
  4. unverified SSL fallback only as last resort
- If fallback is used, explicitly mention this in the final answer and treat paper evidence with extra caution.
