# Web Search Policy for Papers

## Purpose

Use web retrieval to supplement local Stacks knowledge, not replace it.

## Preferred Source Tiers

1. Scholarly APIs (primary): `arXiv`, `OpenAlex`, `Semantic Scholar`
2. Bibliographic fallback: `Crossref`
3. Expert community discussions: `MathOverflow`, `Math StackExchange` (for intuition/path references, not theorem truth by themselves)
4. Context fallback: `Wikipedia` (only for terminology/context, not theorem truth)

## Freshness and Validity

- Prefer recent papers when user asks for latest developments.
- Keep at least one foundational source when discussing core concepts.
- Avoid relying on a single source for broad claims.
- Prefer evidence appearing in multiple sources (dedupe/provenance overlap).

## Extraction Rules

When parsing paper metadata, capture:

- title
- authors
- year (if present)
- abstract snippet (short)
- canonical URL
- source/provenance

## Failure Handling

If no reliable papers are found:

- report that clearly
- continue with Stacks-grounded answer
- suggest user can provide specific papers for deep comparison

If Stacks retrieval fails but web retrieval is available:

- continue with web evidence
- mark foundational claims as lower confidence unless verified by trusted sources
- avoid theorem-number-level claims without direct source confirmation

## SSL Fallback Handling

- Default: strict SSL verification.
- Preferred fix order:
  1. explicit `--ca-bundle`
  2. environment `SSL_CERT_FILE`
  3. system trust store
  4. certifi bundle
  5. unverified SSL fallback only as last resort
- If fallback is used, explicitly mention this in the final answer and treat paper evidence with extra caution.
